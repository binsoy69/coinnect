"""Transaction state machine with WAL-backed state transitions.

Manages the lifecycle of a money changer transaction through defined
states with validation, timeout handling, and WebSocket event emission.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws import ConnectionManager
from app.core.errors import InvalidTransitionError
from app.models.db_models import (
    TransactionRecord,
    TransactionState,
    WALAction,
    WALEntry,
    WALStatus,
)
from app.models.events import WSEvent, WSEventType

logger = logging.getLogger(__name__)

# Valid state transitions
VALID_TRANSITIONS: Dict[TransactionState, Set[TransactionState]] = {
    TransactionState.IDLE: {
        TransactionState.WAITING_FOR_BILL,
        TransactionState.CANCELLED,
    },
    TransactionState.WAITING_FOR_BILL: {
        TransactionState.AUTHENTICATING,
        TransactionState.WAITING_FOR_CONFIRMATION,
        TransactionState.CANCELLED,
        TransactionState.ERROR,
    },
    TransactionState.AUTHENTICATING: {
        TransactionState.SORTING,
        TransactionState.WAITING_FOR_BILL,
        TransactionState.ERROR,
    },
    TransactionState.SORTING: {
        TransactionState.WAITING_FOR_BILL,
        TransactionState.ERROR,
    },
    TransactionState.WAITING_FOR_CONFIRMATION: {
        TransactionState.DISPENSING,
        TransactionState.CANCELLED,
    },
    TransactionState.DISPENSING: {
        TransactionState.COMPLETE,
        TransactionState.ERROR,
    },
    TransactionState.COMPLETE: {TransactionState.IDLE},
    TransactionState.CANCELLED: {TransactionState.IDLE},
    TransactionState.ERROR: {TransactionState.IDLE},
}

# States that can be cancelled by user
CANCELLABLE_STATES: Set[TransactionState] = {
    TransactionState.IDLE,
    TransactionState.WAITING_FOR_BILL,
    TransactionState.WAITING_FOR_CONFIRMATION,
}

# Timeout per state in seconds (None = no timeout)
STATE_TIMEOUTS: Dict[TransactionState, Optional[float]] = {
    TransactionState.WAITING_FOR_BILL: 60.0,
    TransactionState.AUTHENTICATING: 10.0,
    TransactionState.SORTING: 10.0,
    TransactionState.WAITING_FOR_CONFIRMATION: 60.0,
    TransactionState.DISPENSING: 30.0,
}


class TransactionStateMachine:
    """Manages a single transaction lifecycle through defined states."""

    def __init__(
        self,
        transaction_id: str,
        transaction_type: str,
        ws_manager: ConnectionManager,
        db_session: AsyncSession,
    ):
        self._id = transaction_id
        self._type = transaction_type
        self._state = TransactionState.IDLE
        self._ws = ws_manager
        self._db = db_session
        self._timeout_task: Optional[asyncio.Task] = None
        self._data: dict = {}

    @property
    def state(self) -> TransactionState:
        return self._state

    @property
    def transaction_id(self) -> str:
        return self._id

    def is_in_state(self, state: TransactionState) -> bool:
        return self._state == state

    async def transition_to(
        self, new_state: TransactionState, data: Optional[dict] = None
    ) -> None:
        """Transition to a new state with validation, WAL, and WS broadcast.

        Args:
            new_state: Target state.
            data: Optional data to associate with the transition.

        Raises:
            InvalidTransitionError: If transition is not allowed.
        """
        old_state = self._state

        # Validate transition
        allowed = VALID_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            raise InvalidTransitionError(old_state.value, new_state.value)

        # Cancel existing timeout
        self._cancel_timeout()

        # Write WAL entry before transition
        wal_entry = WALEntry(
            transaction_id=self._id,
            action=f"STATE_{old_state.value}_TO_{new_state.value}",
            data=data or {},
            status=WALStatus.PENDING.value,
        )
        self._db.add(wal_entry)
        await self._db.flush()

        # Update state
        self._state = new_state
        if data:
            self._data.update(data)

        # Update DB record
        result = await self._db.execute(
            select(TransactionRecord).where(
                TransactionRecord.id == self._id
            )
        )
        record = result.scalar_one_or_none()
        if record:
            record.state = new_state.value
            record.updated_at = datetime.utcnow()
            if data:
                if "inserted_amount" in data:
                    record.inserted_amount = data["inserted_amount"]
                if "dispensed_amount" in data:
                    record.dispensed_amount = data["dispensed_amount"]
                if "inserted_denominations" in data:
                    record.inserted_denominations = data["inserted_denominations"]
                if "dispense_plan" in data:
                    record.dispense_plan = data["dispense_plan"]
                if "dispense_result" in data:
                    record.dispense_result = data["dispense_result"]
                if "error_code" in data:
                    record.error_code = data["error_code"]
                if "error_message" in data:
                    record.error_message = data["error_message"]
            if new_state in (
                TransactionState.COMPLETE,
                TransactionState.CANCELLED,
                TransactionState.ERROR,
            ):
                record.completed_at = datetime.utcnow()

        await self._db.commit()

        # Mark WAL entry as completed
        wal_entry.status = WALStatus.COMPLETED.value
        await self._db.commit()

        # Start timeout for new state if applicable
        timeout = STATE_TIMEOUTS.get(new_state)
        if timeout is not None:
            self._start_timeout(new_state, timeout)

        # Broadcast state change via WebSocket
        event_type = self._get_event_type(new_state)
        event = WSEvent(
            type=event_type,
            payload={
                "transaction_id": self._id,
                "previous_state": old_state.value,
                "state": new_state.value,
                "type": self._type,
                **(data or {}),
            },
        )
        await self._ws.broadcast(event)

        logger.info(
            f"Transaction {self._id}: {old_state.value} -> {new_state.value}"
        )

    async def cancel(self) -> None:
        """Cancel the transaction from any cancellable state."""
        if self._state in CANCELLABLE_STATES:
            await self.transition_to(TransactionState.CANCELLED)
        elif self._state not in (
            TransactionState.COMPLETE,
            TransactionState.CANCELLED,
            TransactionState.ERROR,
        ):
            # Force cancel for non-terminal states
            await self.transition_to(TransactionState.ERROR, {
                "error_code": "CANCELLED",
                "error_message": "Transaction cancelled by user",
            })

    def _start_timeout(self, state: TransactionState, timeout: float) -> None:
        """Start an async timeout task for the current state."""
        self._timeout_task = asyncio.create_task(
            self._timeout_handler(state, timeout)
        )

    async def _timeout_handler(
        self, expected_state: TransactionState, timeout: float
    ) -> None:
        """Handle state timeout by transitioning to ERROR/CANCELLED."""
        try:
            await asyncio.sleep(timeout)
            # Only act if still in the expected state
            if self._state == expected_state:
                logger.warning(
                    f"Transaction {self._id}: timeout in state {expected_state.value} "
                    f"after {timeout}s"
                )
                if expected_state in CANCELLABLE_STATES:
                    await self.transition_to(
                        TransactionState.CANCELLED,
                        {"error_code": "TIMEOUT", "error_message": f"Timeout in {expected_state.value}"},
                    )
                else:
                    await self.transition_to(
                        TransactionState.ERROR,
                        {"error_code": "TIMEOUT", "error_message": f"Timeout in {expected_state.value}"},
                    )
        except asyncio.CancelledError:
            pass

    def _cancel_timeout(self) -> None:
        """Cancel any running timeout task."""
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
            self._timeout_task = None

    def reset_timeout(self) -> None:
        """Reset the timeout for the current state (e.g., after bill insert)."""
        self._cancel_timeout()
        timeout = STATE_TIMEOUTS.get(self._state)
        if timeout is not None:
            self._start_timeout(self._state, timeout)

    @staticmethod
    def _get_event_type(state: TransactionState) -> WSEventType:
        """Map state to the appropriate WS event type."""
        mapping = {
            TransactionState.COMPLETE: WSEventType.TRANSACTION_COMPLETE,
            TransactionState.CANCELLED: WSEventType.TRANSACTION_CANCELLED,
            TransactionState.ERROR: WSEventType.TRANSACTION_ERROR,
        }
        return mapping.get(state, WSEventType.TRANSACTION_STATE_CHANGED)
