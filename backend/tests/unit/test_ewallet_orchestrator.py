from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.ws import ConnectionManager
from app.core.config import EWalletFeeTier, Settings
from app.models.db_models import Base, EWalletTransactionRecord
from app.services.ewallet_orchestrator import EWalletOrchestrator
from app.services.paymongo_client import DisbursementResult, QRPaymentResult
from app.services.machine_status import MachineStatus


@pytest.fixture
async def ewallet_dependencies():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    settings = Settings(
        use_mock_hardware=True,
        paymongo_sandbox=True,
        ewallet_fee_tiers=[
            EWalletFeeTier(min=1, max=500, fee=15),
            EWalletFeeTier(min=501, max=None, fee=25),
        ],
    )
    status = MachineStatus(settings)
    status.set_dispenser_counts({"PHP_100": 20, "PHP_50": 20, "PHP_20": 20})
    status.set_coin_counts({"PHP_10": 20, "PHP_5": 20, "PHP_1": 20})
    gateway = MagicMock()
    gateway.create_qr_payment = AsyncMock(
        return_value=QRPaymentResult(
            payment_intent_id="pi_1",
            status="awaiting_next_action",
            qr_image_url="data:image/png;base64,abc",
            test_url="https://test.paymongo.com/pi_1",
        )
    )
    gateway.create_disbursement = AsyncMock(
        return_value=DisbursementResult(
            batch_transfer_id="btr_1",
            transfer_id="tr_1",
            status="pending",
        )
    )
    gateway.get_payment_intent = AsyncMock()
    gateway.get_batch_transfer = AsyncMock()
    dispenser = MagicMock()
    ws = ConnectionManager()
    ws.broadcast = AsyncMock()
    orchestrator = EWalletOrchestrator(
        settings=settings,
        gateway=gateway,
        bill_acceptor=MagicMock(),
        dispenser=dispenser,
        machine_status=status,
        ws_manager=ws,
        db_session_factory=factory,
    )
    yield orchestrator, gateway, dispenser, factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_cashout_creates_qr_but_does_not_dispense(ewallet_dependencies):
    orchestrator, gateway, dispenser, factory = ewallet_dependencies

    tx = await orchestrator.start_transaction(
        provider="maya",
        direction="cash-out",
        amount=105,
    )

    assert tx["state"] == "WAITING_FOR_PAYMENT"
    assert tx["transfer_amount"] == 90
    assert tx["gateway_payment_intent_id"] == "pi_1"
    gateway.create_qr_payment.assert_awaited_once()
    dispenser.execute_dispense.assert_not_called()
    async with factory() as session:
        record = await session.get(
            EWalletTransactionRecord,
            tx["transaction_id"],
        )
        assert record.mobile_number == ""
        assert record.account_name == ""


def test_ewallet_model_does_not_require_new_payment_id_column():
    assert (
        "gateway_payment_id"
        not in EWalletTransactionRecord.__table__.columns
    )


@pytest.mark.asyncio
async def test_cash_in_submits_disbursement_only_after_cash_confirmed(
    ewallet_dependencies,
):
    orchestrator, gateway, _, factory = ewallet_dependencies
    tx = await orchestrator.start_transaction(
        provider="gcash",
        direction="cash-in",
        mobile_number="09171234567",
        account_name="Test User",
        amount=105,
    )
    async with factory() as session:
        record = await session.get(EWalletTransactionRecord, tx["transaction_id"])
        record.inserted_amount = 105
        record.state = "CASH_ACCEPTED"
        await session.commit()

    result = await orchestrator.confirm_cash_in(tx["transaction_id"])

    assert result["state"] == "DISBURSEMENT_PENDING"
    gateway.create_disbursement.assert_awaited_once()
    kwargs = gateway.create_disbursement.await_args.kwargs
    assert kwargs["account_number"] == "09171234567"
    assert kwargs["amount_centavos"] == 9_000


@pytest.mark.asyncio
async def test_verified_payment_webhook_dispenses_once(ewallet_dependencies):
    orchestrator, gateway, dispenser, _ = ewallet_dependencies
    dispenser.execute_dispense = AsyncMock()
    dispenser.execute_dispense.return_value = MagicMock(
        success=True,
        total_dispensed=90,
        shortfall=0,
        claim_ticket_code=None,
        error=None,
        model_dump=lambda: {"success": True, "total_dispensed": 90},
    )
    tx = await orchestrator.start_transaction(
        provider="gcash",
        direction="cash-out",
        amount=105,
    )
    gateway.get_payment_intent.return_value = {
        "id": tx["gateway_payment_intent_id"],
        "attributes": {
            "amount": 10_500,
            "currency": "PHP",
            "status": "succeeded",
            "metadata": {
                "coinnect_transaction_id": tx["transaction_id"],
            },
            "payments": [
                {
                    "id": "pay_1",
                    "attributes": {
                        "amount": 10_500,
                        "currency": "PHP",
                        "status": "paid",
                        "source": {"type": "qrph"},
                    },
                }
            ],
        },
    }
    event = {
        "id": "evt_1",
        "type": "payment.paid",
        "resource_id": tx["gateway_payment_intent_id"],
        "payment_id": "pay_1",
    }

    await orchestrator.process_gateway_event(event)
    await orchestrator.process_gateway_event(event)

    dispenser.execute_dispense.assert_awaited_once()


@pytest.mark.asyncio
async def test_payment_mismatch_never_dispenses(ewallet_dependencies):
    orchestrator, gateway, dispenser, _ = ewallet_dependencies
    tx = await orchestrator.start_transaction(
        provider="gcash",
        direction="cash-out",
        amount=105,
    )
    gateway.get_payment_intent.return_value = {
        "id": tx["gateway_payment_intent_id"],
        "attributes": {
            "amount": 10_000,
            "currency": "PHP",
            "status": "succeeded",
            "metadata": {
                "coinnect_transaction_id": tx["transaction_id"],
            },
            "payments": [
                {
                    "id": "pay_1",
                    "attributes": {
                        "amount": 10_000,
                        "currency": "PHP",
                        "status": "paid",
                        "source": {"type": "qrph"},
                    },
                }
            ],
        },
    }

    result = await orchestrator.process_gateway_event(
        {
            "id": "evt_mismatch",
            "type": "payment.paid",
            "resource_id": tx["gateway_payment_intent_id"],
            "payment_id": "pay_1",
        }
    )

    assert result["state"] == "CLAIM_REQUIRED"
    assert result["error_code"] == "PAYMENT_VERIFICATION_FAILED"
    dispenser.execute_dispense.assert_not_called()


@pytest.mark.asyncio
async def test_transfer_webhook_is_reconciled_before_completion(
    ewallet_dependencies,
):
    orchestrator, gateway, _, factory = ewallet_dependencies
    tx = await orchestrator.start_transaction(
        provider="maya",
        direction="cash-in",
        mobile_number="09181234567",
        account_name="Test User",
        amount=105,
    )
    async with factory() as session:
        record = await session.get(EWalletTransactionRecord, tx["transaction_id"])
        record.inserted_amount = 105
        record.state = "CASH_ACCEPTED"
        await session.commit()
    pending = await orchestrator.confirm_cash_in(tx["transaction_id"])
    gateway.get_batch_transfer.return_value = {
        "id": pending["gateway_batch_transfer_id"],
        "transfers": [
            {
                "id": pending["gateway_transfer_id"],
                "status": "succeeded",
                "reference_number": tx["transaction_id"],
                "amount": pending["transfer_amount"] * 100,
                "currency": "PHP",
            }
        ],
    }

    result = await orchestrator.process_gateway_event(
        {
            "id": "evt_transfer_success",
            "type": "transfer.outward.successful",
            "resource_id": pending["gateway_transfer_id"],
            "status": "succeeded",
        }
    )

    assert result["state"] == "COMPLETE"
    gateway.get_batch_transfer.assert_awaited_once_with(
        pending["gateway_batch_transfer_id"]
    )
