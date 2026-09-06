"""Money conservation and recovery regressions from the e-wallet audit."""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select
from tests.unit.test_ewallet_orchestrator import ewallet_dependencies
from app.models.db_models import EWalletTransactionRecord as Tx, GatewayEventRecord, ClaimRecord
from app.services.ewallet_policy import POLICY_VERSION, intake_options
from app.services.change_calculator import calculate_change
from app.services.claim_service import ClaimService
from app.services.dispense_orchestrator import DispenseResult
from app.services.gateway_inbox import GatewayInboxWorker
from app.core.errors import EWalletTransactionError


async def cash_in(o, amount=105, policy=POLICY_VERSION):
    return await o.start_transaction(provider="gcash", direction="cash-in", amount=amount,
        mobile_number="09171234567", account_name="Test User", policy_version=policy)


def verified_transfer(gateway, tx, status="succeeded"):
    gateway.get_batch_transfer.return_value = {"id": "btr_1", "transfers": [{
        "id": "tr_1", "reference_number": tx["transaction_id"], "amount": tx["transfer_amount"]*100,
        "currency": "PHP", "status": status,
        "destination_account": {"number": "09171234567", "bic": "GXCHPHM2XXX"}}]}


@pytest.mark.asyncio
async def test_invalid_transaction_never_operates_hardware(ewallet_dependencies):
    o, _, _, _ = ewallet_dependencies
    with pytest.raises(EWalletTransactionError):
        await o.accept_bill("missing")
    o._bill_acceptor.accept_bill.assert_not_called()


@pytest.mark.asyncio
async def test_concurrent_cash_preserves_both_credits_and_submits_once(ewallet_dependencies):
    o, gateway, _, _ = ewallet_dependencies
    tx = await cash_in(o)
    await asyncio.gather(o.record_cash_insert(tx["transaction_id"], 100), o.record_cash_insert(tx["transaction_id"], 5))
    result = await o.get_transaction(tx["transaction_id"])
    assert result["inserted_amount"] == 105
    assert result["state"] == "DISBURSEMENT_PENDING"
    assert result["can_cancel"] is False
    gateway.create_disbursement.assert_awaited_once()


@pytest.mark.asyncio
async def test_excess_above_twenty_is_rejected_without_credit(ewallet_dependencies):
    o, gateway, _, _ = ewallet_dependencies
    tx = await cash_in(o)
    await o.record_cash_insert(tx["transaction_id"], 100)
    with pytest.raises(EWalletTransactionError):
        await o.record_cash_insert(tx["transaction_id"], 50)
    assert (await o.get_transaction(tx["transaction_id"]))["inserted_amount"] == 100
    gateway.create_disbursement.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("excess", [1, 19, 20])
async def test_change_waits_for_verified_wallet_credit(ewallet_dependencies, excess):
    o, gateway, dispenser, _ = ewallet_dependencies
    tx = await cash_in(o, amount=100-excess)
    result = await o.record_cash_insert(tx["transaction_id"], 100)
    assert result["change_due"] == excess
    dispenser.execute_dispense.assert_not_called()
    dispenser.execute_dispense = AsyncMock(return_value=DispenseResult(success=True,total_dispensed=excess))
    verified_transfer(gateway, tx)
    result = await o._verify_and_complete_cash_in(tx["transaction_id"])
    assert result["state"] == "COMPLETE"
    assert result["inserted_amount"] == result["wallet_credited"]+result["fee"]+result["change_dispensed"]
    kwargs = dispenser.execute_dispense.await_args.kwargs
    assert kwargs["source_kind"] == "EWALLET_CHANGE"
    assert not dispenser.execute_dispense.await_args.args[0].bill_items


@pytest.mark.asyncio
async def test_early_confirm_preserves_deadline(ewallet_dependencies):
    o, _, _, _ = ewallet_dependencies
    tx = await cash_in(o)
    with pytest.raises(EWalletTransactionError):
        await o.confirm_cash_in(tx["transaction_id"])
    assert (await o.get_transaction(tx["transaction_id"]))["deadline"] == tx["deadline"]


@pytest.mark.asyncio
async def test_abandonment_records_retained_cash_without_claim(ewallet_dependencies):
    o, gateway, _, _ = ewallet_dependencies
    tx = await cash_in(o)
    await o.record_cash_insert(tx["transaction_id"], 50)
    now = datetime.utcnow()
    await o._save(tx["transaction_id"], deadline=now-timedelta(seconds=1), heartbeat_at=now)
    await o.expire_transaction(tx["transaction_id"], now)
    result = await o.get_transaction(tx["transaction_id"])
    assert result["state"] == "ABANDONED_RETAINED"
    assert result["retained_amount"] == 50
    assert result["claim_ticket_code"] is None
    assert not o.has_active_transaction
    gateway.create_disbursement.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["heartbeat", "legacy", "tamper"])
async def test_faults_and_legacy_cash_never_become_retained(ewallet_dependencies, failure):
    o, _, _, _ = ewallet_dependencies
    tx = await cash_in(o, policy=None if failure == "legacy" else POLICY_VERSION)
    await o.record_cash_insert(tx["transaction_id"], 50)
    now = datetime.utcnow()
    await o._save(tx["transaction_id"], deadline=now-timedelta(seconds=1),
                  heartbeat_at=now-timedelta(seconds=60) if failure == "heartbeat" else now)
    if failure == "tamper": o._status.update_security(tamper_active=True)
    await o.expire_transaction(tx["transaction_id"], now)
    result = await o.get_transaction(tx["transaction_id"])
    assert result["state"] == "CLAIM_REQUIRED"
    assert result["retained_amount"] == 0


@pytest.mark.asyncio
async def test_old_cleanup_does_not_release_current_owner(ewallet_dependencies):
    o, _, _, _ = ewallet_dependencies
    old = await cash_in(o)
    await o.cancel_transaction(old["transaction_id"])
    current = await cash_in(o)
    await o._clear_active(old["transaction_id"])
    assert o._active_transaction_id == current["transaction_id"]


@pytest.mark.asyncio
async def test_partial_cash_recovers_to_obligation(ewallet_dependencies):
    o, _, _, _ = ewallet_dependencies
    tx = await cash_in(o)
    await o.record_cash_insert(tx["transaction_id"], 50)
    await o.recover_pending_transactions()
    result = await o.get_transaction(tx["transaction_id"])
    assert result["state"] == "CLAIM_REQUIRED"
    assert result["retained_amount"] == 0


@pytest.mark.asyncio
async def test_lost_submission_response_reuses_identity(ewallet_dependencies):
    o, gateway, _, _ = ewallet_dependencies
    tx = await cash_in(o, 100)
    gateway.create_disbursement.side_effect = RuntimeError("response lost")
    result = await o.record_cash_insert(tx["transaction_id"], 100)
    assert result["state"] == "SUBMISSION_UNKNOWN"
    assert not result["claim_ticket_code"]
    await o.reconcile_pending()
    assert len({call.kwargs["idempotency_key"] for call in gateway.create_disbursement.await_args_list}) == 1


@pytest.mark.asyncio
async def test_verification_network_error_remains_retryable(ewallet_dependencies):
    o, gateway, _, _ = ewallet_dependencies
    tx = await cash_in(o, 100)
    await o.record_cash_insert(tx["transaction_id"], 100)
    gateway.get_batch_transfer.side_effect = RuntimeError("offline")
    with pytest.raises(RuntimeError):
        await o._verify_and_complete_cash_in(tx["transaction_id"])
    assert (await o.get_transaction(tx["transaction_id"]))["state"] == "DISBURSEMENT_PENDING"


@pytest.mark.asyncio
async def test_failed_wallet_refunds_fee_and_all_cash(ewallet_dependencies):
    o, gateway, _, factory = ewallet_dependencies
    o._claim_service = ClaimService(factory, o._ws)
    tx = await cash_in(o)
    await o.record_cash_insert(tx["transaction_id"], 100)
    await o.record_cash_insert(tx["transaction_id"], 20)
    verified_transfer(gateway, tx, "failed")
    result = await o._verify_and_complete_cash_in(tx["transaction_id"])
    assert result["shortfall"] == 120
    assert result["refunded_fee"] == 15


@pytest.mark.asyncio
async def test_expired_processing_lease_is_reclaimed_after_restart(ewallet_dependencies):
    o, _, _, factory = ewallet_dependencies
    async with factory() as session:
        session.add(GatewayEventRecord(id="lease",event_type="payment.paid",payload={},status="PROCESSING",
            lease_expires_at=datetime.utcnow()+timedelta(minutes=1)))
        await session.commit()
    worker = GatewayInboxWorker(factory, o, o._settings)
    await worker._recover_expired_leases()
    async with factory() as session:
        row = await session.get(GatewayEventRecord, "lease")
        row.lease_expires_at = datetime.utcnow()-timedelta(seconds=1)
        await session.commit()
    await worker._recover_expired_leases()
    assert await worker._lease_next() == "lease"


def test_exact_solver_finds_solution_missed_by_greedy():
    plan = calculate_change(60, {"PHP_50": 1, "PHP_20": 3}, {})
    assert len(plan.items) == 1 and plan.items[0].count == 3


def test_unsafe_coin_paths_are_disabled():
    options, _ = intake_options(100, {}, [20, 50, 100])
    assert 100 in options["bills"]
    assert options["coins_enabled"] is False


def test_safe_bill_path_respects_finite_storage_slots():
    options, _ = intake_options(100, {}, {20: 1}, allow_coins=False)
    assert options == {"bills": [], "coins_enabled": False}
    options, _ = intake_options(100, {}, {20: 5}, allow_coins=False)
    assert options["bills"] == [20]


@pytest.mark.asyncio
async def test_manual_bill_reconciliation_credits_exactly_once(ewallet_dependencies):
    from app.models.db_models import EWalletIntake
    o, _, _, factory = ewallet_dependencies
    o._claim_service = ClaimService(factory, o._ws)
    tx = await cash_in(o)
    async with factory() as session:
        session.add(EWalletIntake(id="uncertain", transaction_id=tx["transaction_id"], medium="BILL", denomination="PHP_100", value=100))
        await session.commit()
    await o._mark_claim_required(tx["transaction_id"], "INTAKE_UNCERTAIN", "Inspect bill", True)
    result = await o.reconcile_intake("uncertain", True, "Admin saw retained bill")
    assert result["inserted_amount"] == 100
    assert result["shortfall"] == 100
    result = await o.reconcile_intake("uncertain", True, "Repeated request")
    assert result["inserted_amount"] == 100


@pytest.mark.asyncio
async def test_fault_drains_final_coins_before_claim(ewallet_dependencies):
    from types import SimpleNamespace
    from app.models.db_models import EWalletCoinSession
    o, _, _, factory = ewallet_dependencies
    o._claim_service = ClaimService(factory, o._ws)
    o._coin_controller = AsyncMock()
    o._coin_controller.coin_session_status.return_value = SimpleNamespace(sid=1, session_state="CLOSED", count_1=0, count_5=1, count_10=0, count_20=0)
    tx = await cash_in(o)
    async with factory() as session:
        session.add(EWalletCoinSession(transaction_id=tx["transaction_id"], sid=1, counts={}))
        await session.commit()
    result = await o._mark_claim_required(tx["transaction_id"], "DISCONNECTED", "Session interrupted", True)
    assert result["inserted_amount"] == result["shortfall"] == 5
    assert result["retained_amount"] == 0


@pytest.mark.asyncio
async def test_qr_continue_cannot_extend_five_minute_deadline(ewallet_dependencies):
    o, _, _, _ = ewallet_dependencies
    tx = await o.start_transaction(provider="gcash", direction="cash-out", amount=100)
    result = await o.touch(tx["transaction_id"], continue_session=True)
    assert result["deadline"] == tx["deadline"]


@pytest.mark.asyncio
async def test_completed_transaction_cannot_transition_back_to_intake(ewallet_dependencies):
    o, gateway, _, _ = ewallet_dependencies
    tx = await cash_in(o, 100)
    await o.record_cash_insert(tx["transaction_id"], 100)
    verified_transfer(gateway, tx)
    await o._verify_and_complete_cash_in(tx["transaction_id"])
    with pytest.raises(EWalletTransactionError, match="Invalid transition"):
        await o._save(tx["transaction_id"], state="ACCEPTING_CASH")


@pytest.mark.asyncio
async def test_creation_retry_cannot_change_recipient(ewallet_dependencies):
    o, _, _, _ = ewallet_dependencies
    args = dict(provider="gcash", direction="cash-in", amount=100, mobile_number="09171234567", account_name="Test User", request_key="same-request-key")
    original = await o.start_transaction(**args)
    assert (await o.start_transaction(**args))["transaction_id"] == original["transaction_id"]
    with pytest.raises(EWalletTransactionError, match="different transaction details"):
        await o.start_transaction(**{**args, "mobile_number": "09171234568"})
