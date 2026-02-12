"""Transaction orchestrator coordinating the full money changer lifecycle.

This is the central coordinator connecting the bill acceptor, change
calculator, dispense orchestrator, and transaction state machine.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.ws import ConnectionManager
from app.core.constants import BILL_DENOM_VALUES, BillDenom
from app.core.errors import TransactionError
from app.models.db_models import (
    TransactionRecord,
    TransactionState,
    WALEntry,
    WALStatus,
)
from app.models.events import WSEvent, WSEventType
from app.services.bill_acceptor import BillAcceptor
from app.services.change_calculator import calculate_change
from app.services.dispense_orchestrator import DispenseOrchestrator
from app.services.machine_status import MachineStatus
from app.services.transaction_state_machine import TransactionStateMachine

logger = logging.getLogger(__name__)


class TransactionOrchestrator:
    """Manages money changer transaction lifecycles.

    Enforces single active transaction and coordinates all subsystems.
    """

    def __init__(
        self,
        bill_acceptor: BillAcceptor,
        dispense_orchestrator: DispenseOrchestrator,
        machine_status: MachineStatus,
        ws_manager: ConnectionManager,
        db_session_factory: async_sessionmaker,
    ):
        self._bill_acceptor = bill_acceptor
        self._dispenser = dispense_orchestrator
        self._status = machine_status
        self._ws = ws_manager
        self._db_factory = db_session_factory
        self._active_tx: Optional[TransactionStateMachine] = None
        self._active_session: Optional[AsyncSession] = None

    @property
    def has_active_transaction(self) -> bool:
        return self._active_tx is not None

    @property
    def active_transaction_id(self) -> Optional[str]:
        return self._active_tx.transaction_id if self._active_tx else None

    async def start_transaction(
        self,
        transaction_type: str,
        target_amount: int,
        fee: int,
        selected_dispense_denoms: list,
    ) -> dict:
        """Create and start a new money changer transaction.

        Args:
            transaction_type: "bill-to-bill", "bill-to-coin", or "coin-to-bill"
            target_amount: Amount user selected to convert
            fee: Transaction fee
            selected_dispense_denoms: User-selected dispense denominations

        Returns:
            Transaction state dict.

        Raises:
            TransactionError: If a transaction is already active or machine not ready.
        """
        if self._active_tx is not None:
            raise TransactionError(
                self._active_tx.transaction_id,
                "A transaction is already in progress",
            )

        # Validate machine is ready
        snapshot = self._status.snapshot()
        if snapshot.security.tamper_active:
            raise TransactionError("", "Machine is in lockdown mode")

        # Pre-check: can we dispense the target amount?
        total_due = target_amount + fee
        try:
            calculate_change(
                target_amount,
                snapshot.consumables.bill_dispenser_counts,
                snapshot.consumables.coin_counts,
                preferred_denoms=selected_dispense_denoms,
            )
        except Exception as e:
            raise TransactionError("", f"Cannot dispense requested amount: {e}")

        # Create transaction
        tx_id = str(uuid.uuid4())
        session = self._db_factory()
        self._active_session = session

        record = TransactionRecord(
            id=tx_id,
            type=transaction_type,
            state=TransactionState.IDLE.value,
            target_amount=target_amount,
            fee=fee,
            total_due=total_due,
            selected_dispense_denoms=selected_dispense_denoms,
        )
        session.add(record)
        await session.commit()

        # Create state machine
        self._active_tx = TransactionStateMachine(
            transaction_id=tx_id,
            transaction_type=transaction_type,
            ws_manager=self._ws,
            db_session=session,
        )

        # Transition to WAITING_FOR_BILL
        await self._active_tx.transition_to(TransactionState.WAITING_FOR_BILL)

        logger.info(
            f"Transaction started: {tx_id} type={transaction_type} "
            f"amount={target_amount} fee={fee}"
        )

        return await self.get_transaction_state(tx_id)

    async def handle_bill_inserted(self) -> dict:
        """Handle a bill acceptance cycle during an active transaction.

        Runs the full accept_bill() flow and updates transaction state.

        Returns:
            Updated transaction state dict.
        """
        tx = self._require_active_transaction()

        if not tx.is_in_state(TransactionState.WAITING_FOR_BILL):
            raise TransactionError(
                tx.transaction_id,
                f"Cannot accept bill in state {tx.state.value}",
            )

        # Transition to AUTHENTICATING
        await tx.transition_to(TransactionState.AUTHENTICATING)

        # Run bill acceptance
        result = await self._bill_acceptor.accept_bill()

        if not result.success:
            # Bill rejected - go back to WAITING_FOR_BILL
            await tx.transition_to(
                TransactionState.WAITING_FOR_BILL,
                {"last_rejection": result.error},
            )
            # Reset timeout since user is still active
            tx.reset_timeout()
            return await self.get_transaction_state(tx.transaction_id)

        # Bill accepted - transition through SORTING back to WAITING_FOR_BILL
        await tx.transition_to(
            TransactionState.SORTING,
            {"denomination": result.denomination.value, "value": result.value},
        )

        # Update transaction amounts
        session = self._active_session
        db_record = await self._get_db_record(session, tx.transaction_id)
        if db_record:
            db_record.inserted_amount += result.value
            inserted = dict(db_record.inserted_denominations or {})
            denom_key = str(result.value)
            inserted[denom_key] = inserted.get(denom_key, 0) + 1
            db_record.inserted_denominations = inserted
            await session.commit()

        # Transition back to WAITING_FOR_BILL first (SORTING -> WAITING_FOR_BILL)
        await tx.transition_to(TransactionState.WAITING_FOR_BILL)

        # Check if enough money inserted
        if db_record and db_record.inserted_amount >= db_record.total_due:
            await tx.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)
        else:
            tx.reset_timeout()

        return await self.get_transaction_state(tx.transaction_id)

    async def handle_coin_inserted(self, denom: int, total: int) -> dict:
        """Handle a coin insertion event (from Arduino #2 COIN_IN event).

        Used for coin-to-bill transactions.

        Args:
            denom: Coin denomination value (1, 5, 10, 20)
            total: Running total from coin acceptor
        """
        tx = self._require_active_transaction()

        if not tx.is_in_state(TransactionState.WAITING_FOR_BILL):
            return await self.get_transaction_state(tx.transaction_id)

        # Update transaction amounts
        session = self._active_session
        db_record = await self._get_db_record(session, tx.transaction_id)
        if db_record:
            db_record.inserted_amount += denom
            inserted = dict(db_record.inserted_denominations or {})
            denom_key = str(denom)
            inserted[denom_key] = inserted.get(denom_key, 0) + 1
            db_record.inserted_denominations = inserted
            await session.commit()

        # Reset timeout since user is actively inserting
        tx.reset_timeout()

        # Broadcast coin inserted event
        event = WSEvent(
            type=WSEventType.COIN_INSERTED,
            payload={
                "transaction_id": tx.transaction_id,
                "denomination": denom,
                "inserted_amount": db_record.inserted_amount if db_record else 0,
            },
        )
        await self._ws.broadcast(event)

        # Check if enough money
        if db_record and db_record.inserted_amount >= db_record.total_due:
            await tx.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)

        return await self.get_transaction_state(tx.transaction_id)

    async def confirm_transaction(self) -> dict:
        """User confirms transaction. Triggers dispensing.

        Returns:
            Final transaction state dict.
        """
        tx = self._require_active_transaction()

        if not tx.is_in_state(TransactionState.WAITING_FOR_CONFIRMATION):
            raise TransactionError(
                tx.transaction_id,
                f"Cannot confirm in state {tx.state.value}",
            )

        session = self._active_session
        db_record = await self._get_db_record(session, tx.transaction_id)
        if not db_record:
            raise TransactionError(tx.transaction_id, "Transaction record not found")

        # Calculate dispense plan
        snapshot = self._status.snapshot()
        plan = calculate_change(
            db_record.target_amount,
            snapshot.consumables.bill_dispenser_counts,
            snapshot.consumables.coin_counts,
            preferred_denoms=db_record.selected_dispense_denoms,
        )

        # Store dispense plan
        db_record.dispense_plan = {
            "items": [item.model_dump() for item in plan.items],
            "total_amount": plan.total_amount,
        }
        await session.commit()

        # Transition to DISPENSING
        await tx.transition_to(TransactionState.DISPENSING)

        # Execute dispense
        result = await self._dispenser.execute_dispense(plan)

        # Update record with result
        db_record.dispensed_amount = result.total_dispensed
        db_record.dispense_result = result.model_dump()
        await session.commit()

        if result.success:
            await tx.transition_to(
                TransactionState.COMPLETE,
                {"dispensed_amount": result.total_dispensed},
            )
        else:
            await tx.transition_to(
                TransactionState.ERROR,
                {
                    "error_code": "PARTIAL_DISPENSE",
                    "error_message": result.error,
                    "dispensed_amount": result.total_dispensed,
                    "shortfall": result.shortfall,
                    "claim_ticket_code": result.claim_ticket_code,
                },
            )

        state = await self.get_transaction_state(tx.transaction_id)

        # Clean up active transaction
        await self._cleanup_active()

        return state

    async def cancel_transaction(self) -> dict:
        """Cancel the active transaction.

        Returns:
            Final transaction state dict.
        """
        tx = self._require_active_transaction()

        await tx.cancel()
        state = await self.get_transaction_state(tx.transaction_id)

        # Clean up active transaction
        await self._cleanup_active()

        return state

    async def get_transaction_state(self, transaction_id: str) -> dict:
        """Get current state of a transaction.

        Args:
            transaction_id: Transaction UUID.

        Returns:
            Dict with all transaction fields.
        """
        session = self._active_session
        if session is None:
            session = self._db_factory()

        db_record = await self._get_db_record(session, transaction_id)
        if not db_record:
            raise TransactionError(transaction_id, "Transaction not found")

        result = {
            "transaction_id": db_record.id,
            "type": db_record.type,
            "state": db_record.state,
            "target_amount": db_record.target_amount,
            "fee": db_record.fee,
            "total_due": db_record.total_due,
            "inserted_amount": db_record.inserted_amount,
            "dispensed_amount": db_record.dispensed_amount,
            "inserted_denominations": db_record.inserted_denominations or {},
            "dispense_plan": db_record.dispense_plan,
            "dispense_result": db_record.dispense_result,
            "selected_dispense_denoms": db_record.selected_dispense_denoms or [],
            "error_code": db_record.error_code,
            "error_message": db_record.error_message,
            "created_at": db_record.created_at.isoformat() if db_record.created_at else None,
            "updated_at": db_record.updated_at.isoformat() if db_record.updated_at else None,
            "completed_at": db_record.completed_at.isoformat() if db_record.completed_at else None,
        }

        if session != self._active_session:
            await session.close()

        return result

    async def recover_pending_transactions(self) -> None:
        """Recover from pending WAL entries on startup.

        Called during app initialization to handle transactions that
        were interrupted by power loss or crash.
        """
        async with self._db_factory() as session:
            result = await session.execute(
                select(WALEntry).where(
                    WALEntry.status == WALStatus.PENDING.value
                )
            )
            pending_entries = result.scalars().all()

            if not pending_entries:
                logger.info("No pending WAL entries to recover")
                return

            logger.warning(
                f"Found {len(pending_entries)} pending WAL entries to recover"
            )

            for entry in pending_entries:
                try:
                    await self._recover_wal_entry(session, entry)
                except Exception as e:
                    logger.error(
                        f"Failed to recover WAL entry {entry.id}: {e}",
                        exc_info=True,
                    )

            await session.commit()

    async def _recover_wal_entry(
        self, session: AsyncSession, entry: WALEntry
    ) -> None:
        """Recover a single pending WAL entry."""
        logger.info(
            f"Recovering WAL entry {entry.id}: "
            f"tx={entry.transaction_id} action={entry.action}"
        )

        # Find the transaction record
        result = await session.execute(
            select(TransactionRecord).where(
                TransactionRecord.id == entry.transaction_id
            )
        )
        record = result.scalar_one_or_none()

        if record:
            # Mark transaction as ERROR with recovery note
            record.state = TransactionState.ERROR.value
            record.error_code = "CRASH_RECOVERY"
            record.error_message = f"Recovered from pending action: {entry.action}"
            record.completed_at = datetime.utcnow()

        # Mark WAL entry as rolled back
        entry.status = WALStatus.ROLLED_BACK.value

        logger.info(f"WAL entry {entry.id} recovered (rolled back)")

    def _require_active_transaction(self) -> TransactionStateMachine:
        """Get the active transaction or raise an error."""
        if self._active_tx is None:
            raise TransactionError("", "No active transaction")
        return self._active_tx

    async def _get_db_record(
        self, session: AsyncSession, transaction_id: str
    ) -> Optional[TransactionRecord]:
        """Fetch a transaction record from the database."""
        result = await session.execute(
            select(TransactionRecord).where(
                TransactionRecord.id == transaction_id
            )
        )
        return result.scalar_one_or_none()

    async def _cleanup_active(self) -> None:
        """Clean up the active transaction and session."""
        if self._active_session:
            await self._active_session.close()
            self._active_session = None
        self._active_tx = None
