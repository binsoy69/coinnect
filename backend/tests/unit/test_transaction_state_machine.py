"""Tests for the transaction state machine with WAL-backed transitions.

Validates state transition logic, cancellation behavior, DB persistence,
and WebSocket event broadcasting.
"""

import pytest
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.errors import InvalidTransitionError
from app.models.db_models import Base, TransactionRecord, TransactionState
from app.models.events import WSEventType
from app.services.transaction_state_machine import (
    CANCELLABLE_STATES,
    VALID_TRANSITIONS,
    TransactionStateMachine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_session():
    """In-memory async SQLite session pre-loaded with one transaction record."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        record = TransactionRecord(id="test-tx-001", type="bill-to-bill", state="IDLE")
        session.add(record)
        await session.commit()
        yield session
    await engine.dispose()


@pytest.fixture
def ws_manager():
    """Mock WebSocket ConnectionManager that records broadcast calls."""
    manager = AsyncMock()
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture
def state_machine(ws_manager, db_session):
    """Fresh TransactionStateMachine in IDLE state."""
    return TransactionStateMachine(
        transaction_id="test-tx-001",
        transaction_type="bill-to-bill",
        ws_manager=ws_manager,
        db_session=db_session,
    )


# ---------------------------------------------------------------------------
# Test: Valid single-step transitions
# ---------------------------------------------------------------------------

class TestValidTransitions:
    async def test_idle_to_waiting_for_bill(self, state_machine):
        assert state_machine.state == TransactionState.IDLE

        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)

        assert state_machine.state == TransactionState.WAITING_FOR_BILL

    async def test_idle_to_waiting_for_bill_updates_db(self, state_machine, db_session):
        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)

        from sqlalchemy import select
        result = await db_session.execute(
            select(TransactionRecord).where(TransactionRecord.id == "test-tx-001")
        )
        record = result.scalar_one()
        assert record.state == TransactionState.WAITING_FOR_BILL.value


# ---------------------------------------------------------------------------
# Test: Invalid transitions
# ---------------------------------------------------------------------------

class TestInvalidTransitions:
    async def test_idle_to_dispensing_raises(self, state_machine):
        with pytest.raises(InvalidTransitionError) as exc_info:
            await state_machine.transition_to(TransactionState.DISPENSING)

        assert exc_info.value.current_state == "IDLE"
        assert exc_info.value.target_state == "DISPENSING"

    async def test_idle_to_complete_raises(self, state_machine):
        with pytest.raises(InvalidTransitionError):
            await state_machine.transition_to(TransactionState.COMPLETE)

    async def test_idle_to_sorting_raises(self, state_machine):
        with pytest.raises(InvalidTransitionError):
            await state_machine.transition_to(TransactionState.SORTING)

    async def test_state_unchanged_after_invalid_transition(self, state_machine):
        try:
            await state_machine.transition_to(TransactionState.DISPENSING)
        except InvalidTransitionError:
            pass

        assert state_machine.state == TransactionState.IDLE


# ---------------------------------------------------------------------------
# Test: Full lifecycle chain
# ---------------------------------------------------------------------------

class TestFullLifecycle:
    async def test_complete_transaction_lifecycle(self, state_machine):
        transitions = [
            TransactionState.WAITING_FOR_BILL,
            TransactionState.AUTHENTICATING,
            TransactionState.SORTING,
            TransactionState.WAITING_FOR_BILL,
            TransactionState.WAITING_FOR_CONFIRMATION,
            TransactionState.DISPENSING,
            TransactionState.COMPLETE,
        ]

        for target in transitions:
            await state_machine.transition_to(target)
            assert state_machine.state == target

    async def test_lifecycle_to_idle_reset(self, state_machine):
        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)
        await state_machine.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)
        await state_machine.transition_to(TransactionState.DISPENSING)
        await state_machine.transition_to(TransactionState.COMPLETE)
        await state_machine.transition_to(TransactionState.IDLE)

        assert state_machine.state == TransactionState.IDLE


# ---------------------------------------------------------------------------
# Test: Cancellation
# ---------------------------------------------------------------------------

class TestCancellation:
    async def test_cancel_from_waiting_for_bill(self, state_machine):
        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)

        await state_machine.cancel()

        assert state_machine.state == TransactionState.CANCELLED

    async def test_cancel_from_idle(self, state_machine):
        await state_machine.cancel()

        assert state_machine.state == TransactionState.CANCELLED

    async def test_cancel_from_waiting_for_confirmation(self, state_machine):
        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)
        await state_machine.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)

        await state_machine.cancel()

        assert state_machine.state == TransactionState.CANCELLED

    async def test_cancel_from_non_cancellable_state_transitions_to_error(self, state_machine):
        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)
        await state_machine.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)
        await state_machine.transition_to(TransactionState.DISPENSING)

        await state_machine.cancel()

        assert state_machine.state == TransactionState.ERROR

    async def test_cancel_from_authenticating_transitions_to_error(self, state_machine):
        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)
        await state_machine.transition_to(TransactionState.AUTHENTICATING)

        await state_machine.cancel()

        assert state_machine.state == TransactionState.ERROR

    async def test_cancel_from_terminal_state_is_noop(self, state_machine):
        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)
        await state_machine.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)
        await state_machine.transition_to(TransactionState.DISPENSING)
        await state_machine.transition_to(TransactionState.COMPLETE)

        await state_machine.cancel()

        # Still COMPLETE -- cancel() does nothing for terminal states
        assert state_machine.state == TransactionState.COMPLETE


# ---------------------------------------------------------------------------
# Test: WebSocket event broadcasting
# ---------------------------------------------------------------------------

class TestWebSocketBroadcast:
    async def test_transition_broadcasts_state_changed_event(self, state_machine, ws_manager):
        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)

        ws_manager.broadcast.assert_called_once()
        event = ws_manager.broadcast.call_args[0][0]

        assert event.type == WSEventType.TRANSACTION_STATE_CHANGED
        assert event.payload["transaction_id"] == "test-tx-001"
        assert event.payload["previous_state"] == "IDLE"
        assert event.payload["state"] == "WAITING_FOR_BILL"

    async def test_complete_broadcasts_transaction_complete(self, state_machine, ws_manager):
        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)
        await state_machine.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)
        await state_machine.transition_to(TransactionState.DISPENSING)
        await state_machine.transition_to(TransactionState.COMPLETE)

        event = ws_manager.broadcast.call_args_list[-1][0][0]
        assert event.type == WSEventType.TRANSACTION_COMPLETE

    async def test_cancelled_broadcasts_transaction_cancelled(self, state_machine, ws_manager):
        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)
        await state_machine.cancel()

        event = ws_manager.broadcast.call_args_list[-1][0][0]
        assert event.type == WSEventType.TRANSACTION_CANCELLED

    async def test_error_broadcasts_transaction_error(self, state_machine, ws_manager):
        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)
        await state_machine.transition_to(TransactionState.AUTHENTICATING)
        await state_machine.transition_to(
            TransactionState.ERROR,
            {"error_code": "TIMEOUT", "error_message": "Camera timeout"},
        )

        event = ws_manager.broadcast.call_args_list[-1][0][0]
        assert event.type == WSEventType.TRANSACTION_ERROR
        assert event.payload["error_code"] == "TIMEOUT"

    async def test_broadcast_count_matches_transition_count(self, state_machine, ws_manager):
        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)
        await state_machine.transition_to(TransactionState.AUTHENTICATING)
        await state_machine.transition_to(TransactionState.SORTING)

        assert ws_manager.broadcast.call_count == 3

    async def test_transition_with_data_appears_in_broadcast(self, state_machine, ws_manager):
        await state_machine.transition_to(
            TransactionState.WAITING_FOR_BILL,
            data={"inserted_amount": 500},
        )

        event = ws_manager.broadcast.call_args[0][0]
        assert event.payload["inserted_amount"] == 500


# ---------------------------------------------------------------------------
# Test: WAL (Write-Ahead Log) entries
# ---------------------------------------------------------------------------

class TestWriteAheadLog:
    async def test_transition_creates_wal_entry(self, state_machine, db_session):
        from sqlalchemy import select
        from app.models.db_models import WALEntry

        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)

        result = await db_session.execute(select(WALEntry))
        entries = result.scalars().all()

        assert len(entries) == 1
        assert entries[0].transaction_id == "test-tx-001"
        assert "IDLE" in entries[0].action
        assert "WAITING_FOR_BILL" in entries[0].action
        assert entries[0].status == "COMPLETED"

    async def test_multiple_transitions_create_multiple_wal_entries(
        self, state_machine, db_session
    ):
        from sqlalchemy import select
        from app.models.db_models import WALEntry

        await state_machine.transition_to(TransactionState.WAITING_FOR_BILL)
        await state_machine.transition_to(TransactionState.AUTHENTICATING)
        await state_machine.transition_to(TransactionState.SORTING)

        result = await db_session.execute(select(WALEntry))
        entries = result.scalars().all()
        assert len(entries) == 3
