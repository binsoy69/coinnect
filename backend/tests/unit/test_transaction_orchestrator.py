"""Tests for the TransactionOrchestrator.

Validates the full money changer transaction lifecycle including
start, bill/coin insertion, confirmation, cancellation, and WAL recovery.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.ws import ConnectionManager
from app.core.config import Settings
from app.core.constants import BillDenom
from app.core.errors import TransactionError
from app.models.db_models import (
    Base,
    TransactionRecord,
    TransactionState,
    WALEntry,
    WALStatus,
)
from app.services.bill_acceptor import BillAcceptResult
from app.services.dispense_orchestrator import DispenseResult
from app.services.machine_status import MachineStatus
from app.services.transaction_orchestrator import TransactionOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_settings():
    return Settings(
        use_mock_serial=True,
        use_mock_hardware=True,
        mock_delay=0.0,
        serial_port_bill="MOCK_BILL",
        serial_port_coin="MOCK_COIN",
        environment="test",
        log_level="DEBUG",
        db_url="sqlite+aiosqlite:///:memory:",
        led_stabilization_delay=0.0,
        bill_position_timeout=0.5,
        bill_store_duration=0.0,
        bill_eject_duration=0.0,
        bill_acceptance_timeout=1,
    )


@pytest.fixture
def machine_status(test_settings):
    ms = MachineStatus(test_settings)
    # Pre-populate dispenser inventory so calculate_change works
    ms.set_dispenser_counts({
        "PHP_20": 50,
        "PHP_50": 50,
        "PHP_100": 50,
        "PHP_200": 50,
        "PHP_500": 50,
        "PHP_1000": 50,
    })
    ms.set_coin_counts({
        "PHP_1": 200,
        "PHP_5": 200,
        "PHP_10": 200,
        "PHP_20": 200,
    })
    return ms


@pytest.fixture
def ws_manager():
    manager = AsyncMock(spec=ConnectionManager)
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture
def mock_bill_acceptor():
    acceptor = AsyncMock()
    acceptor.accept_bill = AsyncMock(
        return_value=BillAcceptResult(
            success=True,
            denomination=BillDenom.PHP_100,
            value=100,
            auth_confidence=0.98,
            denom_confidence=0.95,
        )
    )
    return acceptor


@pytest.fixture
def mock_dispense_orchestrator():
    dispenser = AsyncMock()
    dispenser.execute_dispense = AsyncMock(
        return_value=DispenseResult(
            success=True,
            dispensed_bills={"PHP_100": 1},
            dispensed_coins={},
            total_dispensed=100,
            shortfall=0,
            error=None,
            claim_ticket_code=None,
        )
    )
    return dispenser


@pytest.fixture
async def db_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    yield factory
    await engine.dispose()


@pytest.fixture
def orchestrator(
    mock_bill_acceptor,
    mock_dispense_orchestrator,
    machine_status,
    ws_manager,
    db_session_factory,
):
    return TransactionOrchestrator(
        bill_acceptor=mock_bill_acceptor,
        dispense_orchestrator=mock_dispense_orchestrator,
        machine_status=machine_status,
        ws_manager=ws_manager,
        db_session_factory=db_session_factory,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _start_default_transaction(orchestrator, target_amount=100, fee=0):
    """Start a standard bill-to-bill transaction and return the state dict."""
    return await orchestrator.start_transaction(
        transaction_type="bill-to-bill",
        target_amount=target_amount,
        fee=fee,
        selected_dispense_denoms=[100],
    )


# ---------------------------------------------------------------------------
# TestStartTransaction
# ---------------------------------------------------------------------------


class TestStartTransaction:
    """Tests for TransactionOrchestrator.start_transaction."""

    async def test_creates_transaction_and_returns_state(
        self, orchestrator, db_session_factory
    ):
        """A new transaction is created, persisted to DB, and returned
        in the WAITING_FOR_BILL state."""
        state = await _start_default_transaction(orchestrator)

        assert state["transaction_id"] is not None
        assert state["type"] == "bill-to-bill"
        assert state["state"] == TransactionState.WAITING_FOR_BILL.value
        assert state["target_amount"] == 100
        assert state["fee"] == 0
        assert state["total_due"] == 100
        assert state["inserted_amount"] == 0
        assert state["dispensed_amount"] == 0

        # Verify persisted in DB
        async with db_session_factory() as session:
            record = await session.get(TransactionRecord, state["transaction_id"])
            assert record is not None
            assert record.type == "bill-to-bill"

    async def test_sets_has_active_transaction_flag(self, orchestrator):
        """After starting, has_active_transaction is True and id is set."""
        assert orchestrator.has_active_transaction is False
        assert orchestrator.active_transaction_id is None

        state = await _start_default_transaction(orchestrator)

        assert orchestrator.has_active_transaction is True
        assert orchestrator.active_transaction_id == state["transaction_id"]

    async def test_raises_if_already_active(self, orchestrator):
        """Starting a second transaction while one is active raises TransactionError."""
        await _start_default_transaction(orchestrator)

        with pytest.raises(TransactionError, match="already in progress"):
            await _start_default_transaction(orchestrator)

    async def test_raises_if_machine_in_lockdown(self, orchestrator, machine_status):
        """Cannot start a transaction when tamper is active."""
        machine_status.update_security(tamper_active=True)

        with pytest.raises(TransactionError, match="lockdown"):
            await _start_default_transaction(orchestrator)

    async def test_raises_if_cannot_dispense_amount(self, orchestrator, machine_status):
        """If the machine cannot dispense the requested target amount,
        start_transaction raises TransactionError."""
        # Empty all dispensers so no change can be made
        machine_status.set_dispenser_counts({
            "PHP_20": 0, "PHP_50": 0, "PHP_100": 0,
            "PHP_200": 0, "PHP_500": 0, "PHP_1000": 0,
        })
        machine_status.set_coin_counts({
            "PHP_1": 0, "PHP_5": 0, "PHP_10": 0, "PHP_20": 0,
        })

        with pytest.raises(TransactionError, match="Cannot dispense"):
            await _start_default_transaction(orchestrator, target_amount=500)

    async def test_total_due_includes_fee(self, orchestrator):
        """total_due = target_amount + fee."""
        state = await orchestrator.start_transaction(
            transaction_type="bill-to-bill",
            target_amount=100,
            fee=10,
            selected_dispense_denoms=[100],
        )

        assert state["target_amount"] == 100
        assert state["fee"] == 10
        assert state["total_due"] == 110

    async def test_broadcasts_state_change_event(self, orchestrator, ws_manager):
        """Starting a transaction broadcasts WebSocket state change events."""
        await _start_default_transaction(orchestrator)

        # The state machine transitions IDLE -> WAITING_FOR_BILL, which
        # causes a WS broadcast
        assert ws_manager.broadcast.call_count >= 1


# ---------------------------------------------------------------------------
# TestHandleBillInserted
# ---------------------------------------------------------------------------


class TestHandleBillInserted:
    """Tests for TransactionOrchestrator.handle_bill_inserted."""

    async def test_successful_bill_updates_inserted_amount(
        self, orchestrator, mock_bill_acceptor
    ):
        """A successful bill acceptance increments the inserted_amount."""
        mock_bill_acceptor.accept_bill.return_value = BillAcceptResult(
            success=True,
            denomination=BillDenom.PHP_100,
            value=100,
            auth_confidence=0.98,
            denom_confidence=0.95,
        )

        await _start_default_transaction(orchestrator, target_amount=200)

        state = await orchestrator.handle_bill_inserted()

        assert state["inserted_amount"] == 100
        # Not enough money yet, so still waiting
        assert state["state"] == TransactionState.WAITING_FOR_BILL.value

    async def test_enough_money_transitions_to_waiting_for_confirmation(
        self, orchestrator, mock_bill_acceptor
    ):
        """When inserted_amount >= total_due, state transitions to
        WAITING_FOR_CONFIRMATION."""
        mock_bill_acceptor.accept_bill.return_value = BillAcceptResult(
            success=True,
            denomination=BillDenom.PHP_100,
            value=100,
            auth_confidence=0.98,
            denom_confidence=0.95,
        )

        # Target 100, insert 100 -> should reach WAITING_FOR_CONFIRMATION
        await _start_default_transaction(orchestrator, target_amount=100)
        state = await orchestrator.handle_bill_inserted()

        assert state["inserted_amount"] == 100
        assert state["state"] == TransactionState.WAITING_FOR_CONFIRMATION.value

    async def test_rejected_bill_stays_in_waiting_for_bill(
        self, orchestrator, mock_bill_acceptor
    ):
        """A rejected bill returns to WAITING_FOR_BILL with a rejection note."""
        mock_bill_acceptor.accept_bill.return_value = BillAcceptResult(
            success=False,
            error="NOT_GENUINE",
            auth_confidence=0.3,
        )

        await _start_default_transaction(orchestrator, target_amount=100)
        state = await orchestrator.handle_bill_inserted()

        assert state["state"] == TransactionState.WAITING_FOR_BILL.value
        assert state["inserted_amount"] == 0

    async def test_raises_if_no_active_transaction(self, orchestrator):
        """handle_bill_inserted raises TransactionError when there is
        no active transaction."""
        with pytest.raises(TransactionError, match="No active transaction"):
            await orchestrator.handle_bill_inserted()

    async def test_tracks_inserted_denominations(
        self, orchestrator, mock_bill_acceptor
    ):
        """Inserted denominations are tracked as a dict {value_str: count}."""
        mock_bill_acceptor.accept_bill.return_value = BillAcceptResult(
            success=True,
            denomination=BillDenom.PHP_50,
            value=50,
            auth_confidence=0.98,
            denom_confidence=0.95,
        )

        await _start_default_transaction(orchestrator, target_amount=200)
        await orchestrator.handle_bill_inserted()
        state = await orchestrator.handle_bill_inserted()

        # Two PHP_50 bills inserted
        assert state["inserted_denominations"]["50"] == 2
        assert state["inserted_amount"] == 100

    async def test_multiple_bills_accumulate(
        self, orchestrator, mock_bill_acceptor
    ):
        """Inserting multiple bills accumulates inserted_amount correctly."""
        # First bill: PHP_100
        mock_bill_acceptor.accept_bill.return_value = BillAcceptResult(
            success=True,
            denomination=BillDenom.PHP_100,
            value=100,
            auth_confidence=0.98,
            denom_confidence=0.95,
        )

        await _start_default_transaction(orchestrator, target_amount=300)
        state1 = await orchestrator.handle_bill_inserted()
        assert state1["inserted_amount"] == 100

        # Second bill: PHP_200
        mock_bill_acceptor.accept_bill.return_value = BillAcceptResult(
            success=True,
            denomination=BillDenom.PHP_200,
            value=200,
            auth_confidence=0.97,
            denom_confidence=0.94,
        )
        state2 = await orchestrator.handle_bill_inserted()
        assert state2["inserted_amount"] == 300
        assert state2["state"] == TransactionState.WAITING_FOR_CONFIRMATION.value


# ---------------------------------------------------------------------------
# TestHandleCoinInserted
# ---------------------------------------------------------------------------


class TestHandleCoinInserted:
    """Tests for TransactionOrchestrator.handle_coin_inserted."""

    async def test_coin_updates_inserted_amount(
        self, orchestrator, ws_manager
    ):
        """A coin insertion increments the inserted_amount."""
        await _start_default_transaction(orchestrator, target_amount=200)

        state = await orchestrator.handle_coin_inserted(denom=10, total=10)

        assert state["inserted_amount"] == 10

    async def test_coin_broadcasts_coin_inserted_event(
        self, orchestrator, ws_manager
    ):
        """A COIN_INSERTED WebSocket event is broadcast on coin insertion."""
        await _start_default_transaction(orchestrator, target_amount=200)

        # Reset call count after start (which emits its own events)
        ws_manager.broadcast.reset_mock()

        await orchestrator.handle_coin_inserted(denom=5, total=5)

        # Should have at least the COIN_INSERTED broadcast
        assert ws_manager.broadcast.call_count >= 1

    async def test_enough_coins_transition_to_waiting_for_confirmation(
        self, orchestrator
    ):
        """When enough coins are inserted, state transitions to
        WAITING_FOR_CONFIRMATION."""
        await _start_default_transaction(orchestrator, target_amount=20)

        # Insert 10 PHP coins twice (10+10=20 >= 20)
        await orchestrator.handle_coin_inserted(denom=10, total=10)
        state = await orchestrator.handle_coin_inserted(denom=10, total=20)

        assert state["state"] == TransactionState.WAITING_FOR_CONFIRMATION.value
        assert state["inserted_amount"] == 20

    async def test_raises_if_no_active_transaction(self, orchestrator):
        """handle_coin_inserted raises TransactionError when there is
        no active transaction."""
        with pytest.raises(TransactionError, match="No active transaction"):
            await orchestrator.handle_coin_inserted(denom=10, total=10)

    async def test_tracks_coin_denominations(self, orchestrator):
        """Inserted coin denominations are tracked correctly."""
        await _start_default_transaction(orchestrator, target_amount=100)

        await orchestrator.handle_coin_inserted(denom=5, total=5)
        await orchestrator.handle_coin_inserted(denom=5, total=10)
        state = await orchestrator.handle_coin_inserted(denom=10, total=20)

        assert state["inserted_denominations"]["5"] == 2
        assert state["inserted_denominations"]["10"] == 1
        assert state["inserted_amount"] == 20


# ---------------------------------------------------------------------------
# TestConfirmTransaction
# ---------------------------------------------------------------------------


class TestConfirmTransaction:
    """Tests for TransactionOrchestrator.confirm_transaction."""

    async def _start_and_fill(self, orchestrator, mock_bill_acceptor, target=100):
        """Helper: start a transaction and insert enough money."""
        mock_bill_acceptor.accept_bill.return_value = BillAcceptResult(
            success=True,
            denomination=BillDenom.PHP_100,
            value=100,
            auth_confidence=0.98,
            denom_confidence=0.95,
        )
        await _start_default_transaction(orchestrator, target_amount=target)
        await orchestrator.handle_bill_inserted()

    async def test_successful_dispense_completes_transaction(
        self, orchestrator, mock_bill_acceptor, mock_dispense_orchestrator
    ):
        """confirm_transaction executes dispense and transitions to COMPLETE."""
        mock_dispense_orchestrator.execute_dispense.return_value = DispenseResult(
            success=True,
            dispensed_bills={"PHP_100": 1},
            dispensed_coins={},
            total_dispensed=100,
            shortfall=0,
        )

        await self._start_and_fill(orchestrator, mock_bill_acceptor)
        state = await orchestrator.confirm_transaction()

        assert state["state"] == TransactionState.COMPLETE.value
        assert state["dispensed_amount"] == 100
        mock_dispense_orchestrator.execute_dispense.assert_called_once()

    async def test_partial_dispense_transitions_to_error(
        self, orchestrator, mock_bill_acceptor, mock_dispense_orchestrator
    ):
        """If dispense has a shortfall, the transaction transitions to ERROR
        with a claim ticket code."""
        mock_dispense_orchestrator.execute_dispense.return_value = DispenseResult(
            success=False,
            dispensed_bills={"PHP_100": 0},
            dispensed_coins={},
            total_dispensed=0,
            shortfall=100,
            error="Partial bill dispense: PHP_100 (0/1)",
            claim_ticket_code="ABC12345",
        )

        await self._start_and_fill(orchestrator, mock_bill_acceptor)
        state = await orchestrator.confirm_transaction()

        assert state["state"] == TransactionState.ERROR.value
        assert state["dispensed_amount"] == 0

    async def test_raises_if_not_in_waiting_for_confirmation(self, orchestrator):
        """confirm_transaction raises TransactionError if the transaction is
        not in WAITING_FOR_CONFIRMATION."""
        await _start_default_transaction(orchestrator, target_amount=200)

        # Transaction is in WAITING_FOR_BILL, not WAITING_FOR_CONFIRMATION
        with pytest.raises(TransactionError, match="Cannot confirm"):
            await orchestrator.confirm_transaction()

    async def test_raises_if_no_active_transaction(self, orchestrator):
        """confirm_transaction raises TransactionError when there is
        no active transaction."""
        with pytest.raises(TransactionError, match="No active transaction"):
            await orchestrator.confirm_transaction()

    async def test_cleans_up_active_transaction_after_confirm(
        self, orchestrator, mock_bill_acceptor, mock_dispense_orchestrator
    ):
        """After confirmation, the active transaction is cleared so a new one
        can be started."""
        mock_dispense_orchestrator.execute_dispense.return_value = DispenseResult(
            success=True,
            dispensed_bills={"PHP_100": 1},
            dispensed_coins={},
            total_dispensed=100,
            shortfall=0,
        )

        await self._start_and_fill(orchestrator, mock_bill_acceptor)
        await orchestrator.confirm_transaction()

        assert orchestrator.has_active_transaction is False
        assert orchestrator.active_transaction_id is None


# ---------------------------------------------------------------------------
# TestCancelTransaction
# ---------------------------------------------------------------------------


class TestCancelTransaction:
    """Tests for TransactionOrchestrator.cancel_transaction."""

    async def test_cancel_transitions_to_cancelled(self, orchestrator):
        """Cancelling a transaction transitions to CANCELLED state."""
        await _start_default_transaction(orchestrator)

        state = await orchestrator.cancel_transaction()

        assert state["state"] == TransactionState.CANCELLED.value

    async def test_cleans_up_active_transaction_after_cancel(self, orchestrator):
        """After cancellation, the active transaction is cleared."""
        await _start_default_transaction(orchestrator)

        await orchestrator.cancel_transaction()

        assert orchestrator.has_active_transaction is False
        assert orchestrator.active_transaction_id is None

    async def test_raises_if_no_active_transaction(self, orchestrator):
        """cancel_transaction raises TransactionError when there is
        no active transaction."""
        with pytest.raises(TransactionError, match="No active transaction"):
            await orchestrator.cancel_transaction()

    async def test_cancel_after_bill_inserted(
        self, orchestrator, mock_bill_acceptor
    ):
        """A transaction can be cancelled after a bill has been inserted
        (while still in WAITING_FOR_BILL)."""
        mock_bill_acceptor.accept_bill.return_value = BillAcceptResult(
            success=True,
            denomination=BillDenom.PHP_50,
            value=50,
            auth_confidence=0.98,
            denom_confidence=0.95,
        )

        await _start_default_transaction(orchestrator, target_amount=200)
        await orchestrator.handle_bill_inserted()

        state = await orchestrator.cancel_transaction()

        assert state["state"] == TransactionState.CANCELLED.value
        assert orchestrator.has_active_transaction is False


# ---------------------------------------------------------------------------
# TestRecoverPendingTransactions
# ---------------------------------------------------------------------------


class TestRecoverPendingTransactions:
    """Tests for TransactionOrchestrator.recover_pending_transactions."""

    async def test_no_pending_entries_is_noop(
        self, orchestrator, db_session_factory
    ):
        """When there are no pending WAL entries, recovery does nothing."""
        # Should not raise
        await orchestrator.recover_pending_transactions()

    async def test_recovers_pending_wal_entries(
        self, orchestrator, db_session_factory
    ):
        """Pending WAL entries are rolled back, and their associated
        transactions are marked as ERROR with CRASH_RECOVERY."""
        tx_id = str(uuid.uuid4())

        # Manually create a transaction record and a pending WAL entry
        async with db_session_factory() as session:
            record = TransactionRecord(
                id=tx_id,
                type="bill-to-bill",
                state=TransactionState.DISPENSING.value,
                target_amount=500,
                fee=0,
                total_due=500,
            )
            session.add(record)

            wal = WALEntry(
                transaction_id=tx_id,
                action="DISPENSE_START",
                data={},
                status=WALStatus.PENDING.value,
            )
            session.add(wal)
            await session.commit()
            wal_id = wal.id

        # Run recovery
        await orchestrator.recover_pending_transactions()

        # Verify the transaction is now in ERROR state
        async with db_session_factory() as session:
            record = await session.get(TransactionRecord, tx_id)
            assert record is not None
            assert record.state == TransactionState.ERROR.value
            assert record.error_code == "CRASH_RECOVERY"
            assert "DISPENSE_START" in record.error_message

            # Verify WAL entry is rolled back
            wal = await session.get(WALEntry, wal_id)
            assert wal.status == WALStatus.ROLLED_BACK.value

    async def test_recovery_handles_multiple_entries(
        self, orchestrator, db_session_factory
    ):
        """Multiple pending WAL entries are all processed."""
        tx_ids = [str(uuid.uuid4()) for _ in range(3)]

        async with db_session_factory() as session:
            for tx_id in tx_ids:
                record = TransactionRecord(
                    id=tx_id,
                    type="bill-to-bill",
                    state=TransactionState.AUTHENTICATING.value,
                    target_amount=100,
                    fee=0,
                    total_due=100,
                )
                session.add(record)

                wal = WALEntry(
                    transaction_id=tx_id,
                    action="BILL_ACCEPTED",
                    data={},
                    status=WALStatus.PENDING.value,
                )
                session.add(wal)
            await session.commit()

        await orchestrator.recover_pending_transactions()

        async with db_session_factory() as session:
            for tx_id in tx_ids:
                record = await session.get(TransactionRecord, tx_id)
                assert record.state == TransactionState.ERROR.value
                assert record.error_code == "CRASH_RECOVERY"

    async def test_recovery_skips_completed_wal_entries(
        self, orchestrator, db_session_factory
    ):
        """Already-completed WAL entries are not reprocessed."""
        tx_id = str(uuid.uuid4())

        async with db_session_factory() as session:
            record = TransactionRecord(
                id=tx_id,
                type="bill-to-bill",
                state=TransactionState.COMPLETE.value,
                target_amount=100,
                fee=0,
                total_due=100,
            )
            session.add(record)

            wal = WALEntry(
                transaction_id=tx_id,
                action="DISPENSE_COMPLETE",
                data={},
                status=WALStatus.COMPLETED.value,
            )
            session.add(wal)
            await session.commit()

        await orchestrator.recover_pending_transactions()

        # Transaction should remain COMPLETE (not changed to ERROR)
        async with db_session_factory() as session:
            record = await session.get(TransactionRecord, tx_id)
            assert record.state == TransactionState.COMPLETE.value


# ---------------------------------------------------------------------------
# TestSingleActiveTransactionEnforcement
# ---------------------------------------------------------------------------


class TestSingleActiveTransactionEnforcement:
    """Tests confirming only one transaction can be active at a time."""

    async def test_second_start_raises_with_existing_tx_id(self, orchestrator):
        """The error for a duplicate start includes the active transaction id."""
        state = await _start_default_transaction(orchestrator)
        active_id = state["transaction_id"]

        with pytest.raises(TransactionError) as exc_info:
            await _start_default_transaction(orchestrator)

        assert active_id in str(exc_info.value)

    async def test_can_start_after_cancel(self, orchestrator):
        """After cancelling, a new transaction can be started."""
        await _start_default_transaction(orchestrator)
        await orchestrator.cancel_transaction()

        state = await _start_default_transaction(orchestrator)
        assert state["state"] == TransactionState.WAITING_FOR_BILL.value

    async def test_can_start_after_confirm(
        self, orchestrator, mock_bill_acceptor, mock_dispense_orchestrator
    ):
        """After confirmation completes, a new transaction can be started."""
        mock_bill_acceptor.accept_bill.return_value = BillAcceptResult(
            success=True,
            denomination=BillDenom.PHP_100,
            value=100,
            auth_confidence=0.98,
            denom_confidence=0.95,
        )
        mock_dispense_orchestrator.execute_dispense.return_value = DispenseResult(
            success=True,
            dispensed_bills={"PHP_100": 1},
            dispensed_coins={},
            total_dispensed=100,
            shortfall=0,
        )

        await _start_default_transaction(orchestrator)
        await orchestrator.handle_bill_inserted()
        await orchestrator.confirm_transaction()

        # Should be able to start a new transaction now
        state = await _start_default_transaction(orchestrator)
        assert state["state"] == TransactionState.WAITING_FOR_BILL.value


# ---------------------------------------------------------------------------
# TestGetTransactionState
# ---------------------------------------------------------------------------


class TestGetTransactionState:
    """Tests for TransactionOrchestrator.get_transaction_state."""

    async def test_returns_full_state_dict(self, orchestrator):
        """get_transaction_state returns a dict with all expected keys."""
        state = await _start_default_transaction(orchestrator)

        expected_keys = {
            "transaction_id",
            "type",
            "state",
            "target_amount",
            "fee",
            "total_due",
            "inserted_amount",
            "dispensed_amount",
            "inserted_denominations",
            "dispense_plan",
            "dispense_result",
            "selected_dispense_denoms",
            "error_code",
            "error_message",
            "created_at",
            "updated_at",
            "completed_at",
        }
        assert set(state.keys()) == expected_keys

    async def test_raises_for_unknown_transaction_id(
        self, orchestrator, db_session_factory
    ):
        """Querying a nonexistent transaction id raises TransactionError."""
        with pytest.raises(TransactionError, match="not found"):
            await orchestrator.get_transaction_state("nonexistent-id")
