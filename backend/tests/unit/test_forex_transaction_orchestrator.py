"""Forex accounting tests use real SQLite, inventory, claims, and payout journals."""
import asyncio
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import Settings
from app.core.constants import BillDenom, BILL_DENOM_VALUES
from app.core.errors import HardwareError
from app.models.db_models import (Base, ForexQuoteRecord, ForexSession, ForexIntake,
    TransactionRecord, InventoryBalance, InventoryHold, ForexClaimItem, PhysicalOperation)
from app.models.forex import ExchangeRateCache
from app.services.bill_acceptor import BillAcceptResult
from app.services.claim_service import ClaimService
from app.services.dispense_orchestrator import DispenseOrchestrator
from app.services.forex_rate_service import ForexRateService
from app.services.forex_transaction_orchestrator import ForexTransactionOrchestrator, now
from app.services.inventory_service import InventoryService
from app.services.machine_status import MachineStatus
from app.services.operation_mode import OperationModeManager


@pytest.fixture
async def fx(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "forex.db"))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(environment="test", dispense_ui_delay=0, forex_fee_eur_to_php=5,
                        forex_fee_php_to_eur=5)
    status = MachineStatus(settings)
    inventory = InventoryService(factory, status)
    await inventory.initialize()
    async with factory() as session:
        for row in (await session.execute(select(InventoryBalance))).scalars():
            row.count = 100 if row.location != "BILL_STORAGE" else 0
        await session.commit()
    await inventory.refresh_runtime()
    ws = AsyncMock()
    rates = ForexRateService(settings, ws, status, factory)
    rates._cache = ExchangeRateCache(rates={"USD":60, "EUR":64}, fetched_at=now(), expires_at=now()+timedelta(hours=24))
    rates._is_online = True
    rates._check_connectivity = AsyncMock()
    acceptor = MagicMock()
    acceptor.wait_for_bill = AsyncMock(return_value=True)
    acceptor.accept_bill = AsyncMock()
    bill, coin = AsyncMock(), AsyncMock()
    async def pay(denom, count, **kwargs):
        return SimpleNamespace(dispensed=count)
    bill.dispense.side_effect = coin.coin_dispense.side_effect = pay
    dispenser = DispenseOrchestrator(bill, coin, status, ws, inventory, factory)
    claims = ClaimService(factory, ws)
    mode = OperationModeManager()
    def make():
        return ForexTransactionOrchestrator(acceptor, dispenser, status, ws, rates, factory,
            operation_mode=mode, claim_service=claims, inventory_service=inventory)
    o = make()
    async def start(service="php-to-usd", amount=10, key=None):
        quote = await rates.create_quote(service, amount)
        return await o.start_transaction(quote_id=quote.quote_id, idempotency_key=key or str(uuid.uuid4()))
    async def insert(denom):
        denomination = BillDenom(denom)
        value = BILL_DENOM_VALUES[denomination]
        async def accept(**kwargs):
            try:
                await kwargs["on_authenticated"](denomination, value)
            except Exception as exc:
                return BillAcceptResult(error=str(exc))
            await kwargs["custom_store_and_record"](denomination, value)
            return BillAcceptResult(success=True, denomination=denomination, value=value, retention="RETAINED")
        acceptor.accept_bill.side_effect = accept
        return await o.handle_bill_inserted()
    ctx = SimpleNamespace(o=o, factory=factory, rates=rates, inventory=inventory, status=status,
        acceptor=acceptor, bill=bill, coin=coin, claims=claims, mode=mode, make=make, start=start, insert=insert)
    with patch("app.services.dispense_orchestrator.get_settings", return_value=settings):
        yield ctx
    if o._timer:
        o._timer.cancel()
        await asyncio.gather(o._timer, return_exceptions=True)
    await engine.dispose()


@pytest.mark.parametrize("service,amount,bills,output", [
    ("usd-to-php",10,["USD_10"],570), ("eur-to-php",5,["EUR_5"],304),
    ("php-to-usd",10,["PHP_500","PHP_100","PHP_50"],10),
    ("php-to-eur",5,["PHP_200","PHP_100","PHP_50"],5),
])
async def test_four_flows(fx, service, amount, bills, output):
    state = await fx.start(service, amount)
    for bill in bills:
        state = await fx.insert(bill)
    assert state["state"] == "WAITING_FOR_CONFIRMATION"
    result = await fx.o.confirm_transaction()
    assert result["state"] == "COMPLETE"
    assert result["dispensed_amount"] == output
    assert result["payout_legs"]["EXCHANGE"]["confirmed"] == output
    assert not fx.mode.has_active_transaction


async def test_php_change_claim_is_php_and_no_fee_refund(fx):
    await fx.start()
    for bill in ["PHP_500","PHP_100","PHP_50"]: await fx.insert(bill)
    async def pay(denom, count, **kwargs):
        if denom.value.startswith("PHP"):
            raise HardwareError("JAM", "Change jam", dispensed=0)
        return SimpleNamespace(dispensed=count)
    fx.bill.dispense.side_effect = pay
    fx.coin.coin_dispense.side_effect = HardwareError("JAM", "Change jam", dispensed=0)
    result = await fx.o.confirm_transaction()
    assert [(i["kind"], i["currency"], i["amount"]) for i in result["claim"]["items"]] == [("PHP_CHANGE","PHP",20)]
    await fx.o.recover_pending_transactions()
    assert (await fx.claims.get_forex(transaction_id=result["transaction_id"]))["items"] == result["claim"]["items"]


async def test_exchange_failure_refunds_full_fee(fx):
    await fx.start()
    for bill in ["PHP_500","PHP_100","PHP_50"]: await fx.insert(bill)
    fx.bill.dispense.side_effect = HardwareError("JAM", "Output jam", dispensed=0)
    result = await fx.o.confirm_transaction()
    assert {(i["kind"],i["currency"],i["amount"]) for i in result["claim"]["items"]} == {
        ("OUTPUT_SHORTFALL","USD",10),("PHP_CHANGE","PHP",20),("FEE_REFUND","PHP",30)}
    assert fx.bill.dispense.await_count == 1


async def test_change_reserved_before_retention_and_not_double_debited(fx):
    await fx.start()
    for bill in ["PHP_500","PHP_100"]: await fx.insert(bill)
    async with fx.factory() as session:
        for row in (await session.execute(select(InventoryBalance).where(InventoryBalance.denomination.like("PHP%"), InventoryBalance.location != "BILL_STORAGE"))).scalars(): row.count=0
        await session.commit()
    await fx.inventory.refresh_runtime()
    state = await fx.insert("PHP_50")
    assert state["inserted_amount"] == 600
    assert state["state"] == "WAITING_FOR_BILL"
    async with fx.factory() as session:
        assert len((await session.execute(select(ForexIntake))).scalars().all()) == 2


@pytest.mark.parametrize("state_name,cash", [("WAITING_FOR_BILL",500),("WAITING_FOR_CONFIRMATION",630),("AUTHENTICATING",500),("SORTING",500)])
async def test_restart_refunds_input_in_all_prepayout_states(fx,state_name,cash):
    state = await fx.start()
    async with fx.factory() as session:
        record=await session.get(TransactionRecord,state["transaction_id"])
        record.state=state_name;record.inserted_amount=cash
        await session.commit()
    await fx.o._cleanup(state["transaction_id"])
    fresh=fx.make()
    await fresh.recover_pending_transactions()
    result=await fresh.get_transaction_state(state["transaction_id"])
    assert result["state"] == "CLAIM_REQUIRED"
    assert [(i["currency"],i["amount"]) for i in result["claim"]["items"]] == [("PHP",cash)]
    fx.bill.dispense.assert_not_awaited()


async def test_completed_hardware_unfinalized_source_recovers(fx):
    state=await fx.start("usd-to-php",10)
    await fx.insert("USD_10")
    original=fx.o._settle
    fx.o._settle=AsyncMock(side_effect=RuntimeError("Crash before finalize"))
    with pytest.raises(RuntimeError): await fx.o.confirm_transaction()
    calls=fx.bill.dispense.await_count
    fx.o._settle=original
    await fx.o._cleanup(state["transaction_id"])
    await fx.o.recover_pending_transactions()
    assert (await fx.o.get_transaction_state(state["transaction_id"]))["state"] == "COMPLETE"
    assert fx.bill.dispense.await_count == calls


async def test_intake_fault_preserves_previously_accepted_cash(fx):
    await fx.start(); await fx.insert("PHP_500")
    fx.acceptor.accept_bill.side_effect = None
    fx.acceptor.accept_bill.return_value = BillAcceptResult(error="camera failure", retention="UNCERTAIN")
    result=await fx.o.handle_bill_inserted()
    assert result["claim"]["items"][0]["amount"] == 500
    assert result["claim"]["items"][0]["currency"] == "PHP"


async def test_retention_accounting_failure_is_provisional_and_reconcilable(fx):
    state=await fx.start()
    async def failed(**kwargs):
        await kwargs["on_authenticated"](BillDenom.PHP_500,500)
        raise RuntimeError("Crash after physical retention")
    fx.acceptor.accept_bill.side_effect=failed
    result=await fx.o.handle_bill_inserted()
    item=result["claim"]["items"][0]
    assert (item["amount"],item["status"]) == (500,"PROVISIONAL")
    with pytest.raises(ValueError): await fx.claims.resolve_forex_item(result["claim_ticket_code"],item["id"],"admin","checked")
    async with fx.factory() as s: op=(await s.execute(select(ForexIntake))).scalars().one()
    result=await fx.o.reconcile_intake(op.id,True,"admin","Counted retained bill")
    assert result["claim"]["items"][0]["status"] == "OPEN"
    assert result["inserted_amount"] == 500
    with pytest.raises(ValueError): await fx.o.reconcile_intake(op.id,True,"admin","duplicate")


async def test_concurrent_start_and_idempotency(fx):
    q1=await fx.rates.create_quote("usd-to-php",10)
    q2=await fx.rates.create_quote("eur-to-php",5)
    outcomes=await asyncio.gather(fx.o.start_transaction(quote_id=q1.quote_id,idempotency_key="first-key"),fx.o.start_transaction(quote_id=q2.quote_id,idempotency_key="second-key"),return_exceptions=True)
    success=next(r for r in outcomes if isinstance(r,dict))
    assert sum(isinstance(r,dict) for r in outcomes)==1
    assert fx.acceptor.set_expected_currency.call_args.args[0] == success["from_currency"]
    retry=await fx.o.start_transaction(quote_id=q1.quote_id,idempotency_key="first-key")
    assert retry["transaction_id"]==success["transaction_id"]
    with pytest.raises(ValueError): await fx.o.start_transaction(quote_id=q2.quote_id,idempotency_key="first-key")


async def test_start_failure_releases_owner(fx):
    quote=await fx.rates.create_quote("usd-to-php",10)
    fx.acceptor.set_expected_denomination.side_effect=RuntimeError("Configuration failed")
    with pytest.raises(RuntimeError): await fx.o.start_transaction(quote_id=quote.quote_id,idempotency_key="failed-start")
    assert not fx.mode.has_active_transaction


async def test_expired_quote_rejected_and_fees_locked(fx):
    quote=await fx.rates.create_quote("usd-to-php",10)
    await fx.rates.update_fees({"usd-to-php":10})
    state=await fx.o.start_transaction(quote_id=quote.quote_id,idempotency_key="locked-fee")
    assert state["fee"]==30
    await fx.o.cancel_transaction()
    with pytest.raises(ValueError, match="Quote already used"):
        await fx.o.start_transaction(quote_id=quote.quote_id, idempotency_key="another-key")
    quote=await fx.rates.create_quote("usd-to-php",10)
    async with fx.factory() as s:
        saved=await s.get(ForexQuoteRecord,quote.quote_id);saved.expires_at=now()-timedelta(seconds=1);await s.commit()
    with pytest.raises(ValueError,match="QUOTE_EXPIRED"):
        await fx.o.start_transaction(quote_id=quote.quote_id,idempotency_key="expired-key")


async def test_poll_does_not_extend_deadline_continue_does(fx):
    state=await fx.start()
    fx.acceptor.wait_for_bill.return_value=False
    polled=await fx.o.handle_bill_inserted()
    assert polled["deadline"]==state["deadline"]
    extended=await fx.o.continue_transaction()
    assert extended["deadline"]>state["deadline"]
    await fx.o.cancel_transaction()
    assert not fx.mode.has_active_transaction


async def test_cancellation_after_cash_disabled_and_tamper_claims(fx):
    await fx.start();await fx.insert("PHP_500")
    with pytest.raises(Exception,match="CASH_ALREADY_ACCEPTED"):await fx.o.cancel_transaction()
    tx=fx.o.active_transaction_id
    await fx.o.handle_tamper("shock")
    result=await fx.o.get_transaction_state(tx)
    assert result["claim"]["items"][0]["amount"]==500


async def test_claim_items_settle_independently(fx):
    await fx.start();await fx.insert("PHP_500");await fx.o.handle_tamper("shock")
    async with fx.factory() as s: item=(await s.execute(select(ForexClaimItem))).scalars().one()
    result=await fx.claims.resolve_forex_item(item.ticket_id,item.id,"tech","Cash returned")
    assert result["status"]=="RESOLVED"


async def test_legacy_audit_does_not_rewrite_history(fx):
    async with fx.factory() as s:
        s.add(TransactionRecord(id="old",type="forex-php-to-usd",state="DISPENSING",inserted_amount=630,target_amount=10,converted_amount=600))
        await s.commit()
    await fx.o.recover_pending_transactions()
    async with fx.factory() as s: assert (await s.get(TransactionRecord,"old")).state=="DISPENSING"
    assert (await fx.claims.forex_legacy_audit())[0]["transaction_id"]=="old"


async def test_fee_changes_survive_service_restart(fx):
    await fx.rates.update_fees({"php-to-usd":7.25})
    settings=Settings(environment="test",forex_fee_php_to_usd=1)
    fresh=ForexRateService(settings,AsyncMock(),db_session_factory=fx.factory)
    await fresh.initialize_fees()
    assert fresh.get_fee_percentage("php-to-usd")==7.25


async def test_confirm_retry_never_sends_twice(fx):
    state=await fx.start("usd-to-php",10);await fx.insert("USD_10")
    results=await asyncio.gather(fx.o.confirm_transaction(state["transaction_id"]),fx.o.confirm_transaction(state["transaction_id"]))
    assert all(r["state"]=="COMPLETE" for r in results)
    count=fx.bill.dispense.await_count
    await fx.o.confirm_transaction(state["transaction_id"])
    assert fx.bill.dispense.await_count==count


async def test_reservation_debits_once(fx):
    state=await fx.start()
    async with fx.factory() as session:
        before=(await session.execute(select(InventoryBalance).where(InventoryBalance.location=="BILL_DISPENSER",InventoryBalance.denomination=="USD_10"))).scalar_one().count
    for bill in ["PHP_500","PHP_100","PHP_50"]: await fx.insert(bill)
    await fx.o.confirm_transaction()
    async with fx.factory() as session:
        after=(await session.execute(select(InventoryBalance).where(InventoryBalance.location=="BILL_DISPENSER",InventoryBalance.denomination=="USD_10"))).scalar_one().count
        holds=(await session.execute(select(InventoryHold).where(InventoryHold.transaction_id.like(state["transaction_id"]+"%")))).scalars().all()
    assert before-after==1
    assert all(h.state=="CONSUMED" for h in holds)


async def test_browser_cancellation_does_not_cancel_retention(fx):
    state=await fx.start()
    entered=asyncio.Event();release=asyncio.Event()
    async def accept(**kwargs):
        await kwargs["on_authenticated"](BillDenom.PHP_500,500)
        entered.set();await release.wait()
        await kwargs["custom_store_and_record"](BillDenom.PHP_500,500)
        return BillAcceptResult(success=True,retention="RETAINED")
    fx.acceptor.accept_bill.side_effect=accept
    request=asyncio.create_task(fx.o.handle_bill_inserted())
    await entered.wait();request.cancel();release.set();await request
    assert (await fx.o.get_transaction_state(state["transaction_id"]))["inserted_amount"]==500


async def test_server_timeout_claims_cash_without_motion(fx):
    state=await fx.start();await fx.insert("PHP_500")
    async with fx.factory() as session:
        meta=await session.get(ForexSession,state["transaction_id"]);meta.deadline=now()-timedelta(seconds=1);await session.commit()
    await asyncio.wait_for(fx.o._timer,timeout=3)
    result=await fx.o.get_transaction_state(state["transaction_id"])
    assert result["claim"]["items"][0]["amount"]==500
    fx.bill.dispense.assert_not_awaited()


async def test_receipt_and_input_claim_use_currency_labels(fx):
    from app.services.receipt_service import ReceiptService
    printer=ReceiptService.__new__(ReceiptService)
    printer._render_text_lines=MagicMock(side_effect=lambda lines: lines)
    printer._queue_print_job=AsyncMock()
    await fx.start()
    for bill in ["PHP_500","PHP_100","PHP_50"]: await fx.insert(bill)
    state=await fx.o.confirm_transaction()
    await printer.print_receipt(state)
    text="\n".join(printer._render_text_lines.call_args.args[0])
    assert "EXCHANGE: USD 10" in text
    assert "CHANGE: PHP 20" in text
    assert "Fee: PHP 30" in text
    await fx.start();await fx.insert("PHP_500")
    tx=fx.o.active_transaction_id
    await fx.o.handle_tamper("test")
    await printer.print_forex_claim(await fx.o.get_transaction_state(tx))
    text="\n".join(printer._render_text_lines.call_args.args[0])
    assert "PHP 500 (OPEN)" in text
    assert "USD 500" not in text


async def test_availability_uses_foreign_stock(fx):
    async with fx.factory() as session:
        rows=(await session.execute(select(InventoryBalance).where(InventoryBalance.location=="BILL_DISPENSER", InventoryBalance.denomination.like("USD%")))).scalars().all()
        for row in rows: row.count=1 if row.denomination=="USD_10" else 0
        await session.commit()
    await fx.inventory.refresh_runtime()
    available=await fx.o.availability()
    assert available["php-to-usd"][0]["available"]
    assert not available["php-to-usd"][1]["available"]
    assert all(row["available"] for row in available["php-to-eur"])


async def test_recovery_releases_hold_after_terminal_commit(fx):
    state = await fx.start()
    tx_id = state["transaction_id"]
    async with fx.factory() as session:
        record = await session.get(TransactionRecord, tx_id)
        record.state = "CANCELLED"
        await session.commit()
    recovered = fx.make()
    await recovered.recover_pending_transactions()
    await recovered.recover_pending_transactions()
    async with fx.factory() as session:
        hold = (await session.execute(select(InventoryHold).where(
            InventoryHold.transaction_id == tx_id + ":EXCHANGE"))).scalar_one()
        assert hold.state == "RELEASED"
    fx.bill.dispense.assert_not_awaited()


async def test_prepared_but_verified_ejected_is_not_credited(fx):
    state = await fx.start()
    async def accept(**kwargs):
        await kwargs["on_authenticated"](BillDenom.PHP_1000, 1000)
        return BillAcceptResult(retention="EJECTED", error="Preparation interrupted")
    fx.acceptor.accept_bill.side_effect = accept
    result = await fx.o.handle_bill_inserted()
    assert result["inserted_amount"] == 0
    assert result["state"] == "WAITING_FOR_BILL"
    assert "CHANGE" not in result["payout_legs"]
    async with fx.factory() as session:
        op = (await session.execute(select(ForexIntake))).scalar_one()
        assert op.state == "EJECTED"
    assert not fx.o._accounting_fault


def test_forex_backup_preserves_existing_history(tmp_path):
    import sqlite3
    from app.core.database import _backup_before_forex_migration
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE transactions (id TEXT, amount INTEGER)")
        connection.execute("INSERT INTO transactions VALUES ('legacy', 600)")
        connection.commit()
        _backup_before_forex_migration(str(database))
        backup = next(tmp_path.glob("*.pre-forex.backup"))
        with sqlite3.connect(backup) as copied:
            assert copied.execute("SELECT * FROM transactions").fetchall() == [("legacy", 600)]
        connection.execute("CREATE TABLE forex_sessions (id TEXT)")
        connection.commit()
        _backup_before_forex_migration(str(database))
        assert len(list(tmp_path.glob("*.pre-forex.backup"))) == 1


async def test_ambiguous_exchange_fee_is_provisional_until_evidence(fx):
    await fx.start()
    for bill in ["PHP_500", "PHP_100", "PHP_50"]:
        await fx.insert(bill)
    fx.bill.dispense.side_effect = HardwareError("AMBIGUOUS", "Lost hardware reply")
    result = await fx.o.confirm_transaction()
    items = {item["kind"]: item for item in result["claim"]["items"]}
    assert items["OUTPUT_SHORTFALL"]["status"] == "PROVISIONAL"
    assert items["FEE_REFUND"]["status"] == "PROVISIONAL"
    with pytest.raises(ValueError, match="Reconcile physical evidence"):
        await fx.claims.resolve_forex_item(result["claim_ticket_code"],
            items["FEE_REFUND"]["id"], "operator", "Attempt before verification")
    calls = fx.bill.dispense.await_count
    async with fx.factory() as session:
        operation = (await session.execute(select(PhysicalOperation))).scalar_one()
        operation.confirmed_count = operation.requested_count
        operation.state = "COMPLETED"
        await session.commit()
    reconciled = await fx.o.reconcile_payout(result["transaction_id"])
    remaining = {item["kind"]: item for item in reconciled["claim"]["items"]}
    assert remaining["FEE_REFUND"]["amount"] == 0
    assert remaining["OUTPUT_SHORTFALL"]["amount"] == 0
    assert remaining["PHP_CHANGE"]["amount"] == 20
    assert fx.bill.dispense.await_count == calls


@pytest.mark.parametrize("action", ["continue_transaction", "confirm_transaction"])
async def test_expired_deadline_cannot_be_bypassed_before_watchdog(fx, action):
    state = await fx.start("usd-to-php", 10)
    await fx.insert("USD_10")
    async with fx.factory() as session:
        meta = await session.get(ForexSession, state["transaction_id"])
        meta.deadline = now() - timedelta(seconds=1)
        await session.commit()
    result = await getattr(fx.o, action)()
    assert result["state"] == "CLAIM_REQUIRED"
    assert result["claim"]["items"][0]["currency"] == "USD"
    assert result["claim"]["items"][0]["amount"] == 10
    fx.bill.dispense.assert_not_awaited()


async def test_printer_failure_does_not_leak_machine_ownership(fx):
    await fx.start("usd-to-php", 10)
    await fx.insert("USD_10")
    fx.o._receipt_service = AsyncMock()
    fx.o._receipt_service.print_receipt.side_effect = RuntimeError("Printer unavailable")
    result = await fx.o.confirm_transaction()
    assert result["state"] == "COMPLETE"
    assert not fx.mode.has_active_transaction
    assert not fx.o.has_active_transaction
