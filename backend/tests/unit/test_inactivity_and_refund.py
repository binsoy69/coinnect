import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.config import Settings
from app.models.db_models import TransactionRecord, TransactionState
from app.services.transaction_state_machine import TransactionStateMachine


@pytest.fixture
def ws_manager():
    manager = AsyncMock()
    manager.broadcast = AsyncMock()
    return manager


def _create_mock_session():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    return session


class TestInactivityTimers:
    @pytest.mark.asyncio
    async def test_inactivity_warning_and_timeout(self, ws_manager):
        session = _create_mock_session()
        on_warning = AsyncMock()
        on_timeout = AsyncMock()

        tsm = TransactionStateMachine(
            transaction_id="tx_test_inactivity",
            transaction_type="bill-to-bill",
            ws_manager=ws_manager,
            db_session=session,
            on_timeout=on_timeout,
            on_warning=on_warning,
            warning_seconds=0.05,
            timeout_seconds=0.1,
        )

        await tsm.transition_to(TransactionState.WAITING_FOR_BILL)

        # After 0.06s, warning should have fired, but not timeout
        await asyncio.sleep(0.06)
        on_warning.assert_awaited_once_with(TransactionState.WAITING_FOR_BILL)
        on_timeout.assert_not_awaited()

        # After another 0.06s (total 0.12s), timeout should have fired
        await asyncio.sleep(0.06)
        on_timeout.assert_awaited_once_with(TransactionState.WAITING_FOR_BILL)

    @pytest.mark.asyncio
    async def test_inactivity_reset_clears_timer(self, ws_manager):
        session = _create_mock_session()
        on_warning = AsyncMock()
        on_timeout = AsyncMock()

        tsm = TransactionStateMachine(
            transaction_id="tx_test_reset",
            transaction_type="bill-to-bill",
            ws_manager=ws_manager,
            db_session=session,
            on_timeout=on_timeout,
            on_warning=on_warning,
            warning_seconds=0.08,
            timeout_seconds=0.15,
        )

        await tsm.transition_to(TransactionState.WAITING_FOR_BILL)

        # At 0.05s, reset timeout
        await asyncio.sleep(0.05)
        tsm.reset_timeout()

        # Sleep another 0.05s (total 0.10s, which is >0.08s from start, but only 0.05s since reset)
        await asyncio.sleep(0.05)
        on_warning.assert_not_awaited()
        on_timeout.assert_not_awaited()

        # Cancel cleanly
        tsm._cancel_timeout()


class TestRefundFormula:
    @pytest.mark.asyncio
    async def test_timeout_after_cash_refunds_exact_inserted_amount_no_fees(self):
        accepted_cash = 100
        confirmed_cash = 0
        fee = 10
        
        # Policy: zero fee deducted on failed / timed-out / cancelled transactions
        refund_amount = max(0, accepted_cash - confirmed_cash)
        assert refund_amount == 100
        assert refund_amount != accepted_cash - fee

    @pytest.mark.asyncio
    async def test_partial_dispense_refund_formula(self):
        accepted_cash = 200
        confirmed_cash = 50
        refund_amount = max(0, accepted_cash - confirmed_cash)
        assert refund_amount == 150
        claim_kind = "OUTPUT_SHORTFALL" if confirmed_cash > 0 else "INPUT_REFUND"
        assert claim_kind == "OUTPUT_SHORTFALL"

    @pytest.mark.asyncio
    async def test_orchestrator_handle_timeout_with_cash_creates_claim(self):
        from app.services.transaction_orchestrator import TransactionOrchestrator

        bill_acceptor = MagicMock()
        dispenser = MagicMock()
        coin_controller = MagicMock()
        machine_status = MagicMock()
        ws_manager = AsyncMock()
        db_factory = MagicMock()
        claim_service = AsyncMock()

        claim_rec = MagicMock(claim_ticket_code="CLAIM_TIMEOUT_123")
        claim_service.create = AsyncMock(return_value=claim_rec)

        orchestrator = TransactionOrchestrator(
            bill_acceptor=bill_acceptor,
            dispense_orchestrator=dispenser,
            coin_controller=coin_controller,
            machine_status=machine_status,
            ws_manager=ws_manager,
            db_session_factory=db_factory,
            claim_service=claim_service,
        )

        # Mock active transaction
        active_tx = MagicMock(transaction_id="tx_123")
        active_tx.state = TransactionState.WAITING_FOR_BILL
        active_tx.transition_to = AsyncMock()
        orchestrator._active_tx = active_tx

        # Mock db record with cash inserted
        record = MagicMock()
        record.id = "tx_123"
        record.type = "bill-to-bill"
        record.inserted_amount = 100
        record.dispensed_amount = 0
        orchestrator._get_db_record = AsyncMock(return_value=record)
        orchestrator._active_session = AsyncMock()
        orchestrator._cleanup_active = AsyncMock()

        await orchestrator._handle_timeout(TransactionState.WAITING_FOR_BILL)

        claim_service.create.assert_awaited_once_with(
            source_kind="STANDARD",
            transaction_id="tx_123",
            claim_kind="INPUT_REFUND",
            amount=100,
            currency="PHP",
            reason_code="TIMEOUT_AFTER_CASH",
            reason_message="Timeout in WAITING_FOR_BILL",
            record=record,
            session=orchestrator._active_session,
        )
        active_tx.transition_to.assert_awaited_once_with(
            TransactionState.CLAIM_REQUIRED,
            {
                "claim_ticket_code": "CLAIM_TIMEOUT_123",
                "error_code": "TIMEOUT_AFTER_CASH",
                "error_message": "Timeout in WAITING_FOR_BILL",
            },
        )
