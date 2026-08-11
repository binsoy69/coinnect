"""Transaction orchestrator coordinating the full money changer lifecycle.

This is the central coordinator connecting the bill acceptor, change
calculator, dispense orchestrator, and transaction state machine.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.ws import ConnectionManager
from app.core.constants import BILL_DENOM_VALUES, BillDenom
from app.core.errors import InsufficientInventoryError, TransactionError
from app.models.db_models import (
    TransactionRecord,
    TransactionState,
)
from app.models.events import WSEvent, WSEventType
from app.services.bill_acceptor import BillAcceptor
from app.services.change_calculator import DispensePlan, calculate_change
from app.services.dispense_orchestrator import DispenseOrchestrator
from app.drivers.coin_security_controller import CoinSecurityController
from app.services.machine_status import MachineStatus
from app.services.transaction_state_machine import TransactionStateMachine
from app.services.operation_mode import OperationModeManager
from app.services.receipt_service import ReceiptService
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class TransactionOrchestrator:
    """Manages money changer transaction lifecycles.

    Enforces single active transaction and coordinates all subsystems.
    """

    def __init__(
        self,
        bill_acceptor: BillAcceptor,
        dispense_orchestrator: DispenseOrchestrator,
        coin_controller: CoinSecurityController | None,
        machine_status: MachineStatus,
        ws_manager: ConnectionManager,
        db_session_factory: async_sessionmaker,
        operation_mode: OperationModeManager | None = None,
        receipt_service: ReceiptService | None = None,
        claim_service=None,
    ):
        self._bill_acceptor = bill_acceptor
        self._dispenser = dispense_orchestrator
        self._coin_controller = coin_controller
        self._status = machine_status
        self._ws = ws_manager
        self._db_factory = db_session_factory
        self._active_tx: Optional[TransactionStateMachine] = None
        self._active_session: Optional[AsyncSession] = None
        self._operation_mode = operation_mode
        self._operation_owner: Optional[str] = None
        self._receipt_service = receipt_service
        self._confirm_lock = asyncio.Lock()
        self._claim_service = claim_service

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
        selected_dispense_denoms: list,
        selected_dispense_counts: Optional[dict] = None,
        fee: Optional[int] = None,
    ) -> dict:
        """Create and start a new money changer transaction.

        Args:
            transaction_type: "bill-to-bill", "bill-to-coin", or "coin-to-bill"
            target_amount: Amount user selected to convert
            selected_dispense_denoms: User-selected dispense denominations
            selected_dispense_counts: User-selected breakdown quantities (e.g. {"500": 1, "100": 4})

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

        settings = get_settings()
        fee_map = {
            "bill-to-bill": settings.fee_bill_to_bill,
            "bill-to-coin": settings.fee_bill_to_coin,
            "coin-to-bill": settings.fee_coin_to_bill,
        }
        if transaction_type not in fee_map:
            raise TransactionError("", "Unsupported transaction type")
        # ``fee`` is accepted only for compatibility with internal callers;
        # client-provided values are never used and the HTTP schema forbids it.
        fee = fee_map[transaction_type]

        # Validate machine is ready
        snapshot = self._status.snapshot()
        if snapshot.security.tamper_active:
            raise TransactionError("", "Machine is in lockdown mode")
        if self._status.should_block_dispensing_for_inventory_reconciliation():
            raise TransactionError("", "Inventory reconciliation is required")

        # Pre-check: can we dispense the target amount?
        if transaction_type in {"bill-to-bill", "bill-to-coin"}:
            total_due = target_amount
            dispense_amount = target_amount - fee
            if dispense_amount < 0:
                raise TransactionError("", f"Fee {fee} exceeds target amount {target_amount}")
        else:
            total_due = target_amount + fee
            dispense_amount = target_amount

        try:
            bill_inventory = (
                {} if transaction_type == "bill-to-coin"
                else snapshot.consumables.bill_dispenser_counts
            )
            coin_inventory = (
                snapshot.consumables.coin_counts
                if transaction_type == "bill-to-coin" else {}
            )
            calculate_change(
                dispense_amount,
                bill_inventory,
                coin_inventory,
                preferred_denoms=selected_dispense_denoms,
                requested_counts=selected_dispense_counts,
            )
        except Exception as e:
            raise TransactionError("", f"Cannot dispense requested amount: {e}")

        if selected_dispense_counts is not None:
            requested_total = sum(
                int(denom) * int(count)
                for denom, count in selected_dispense_counts.items()
            )
            if requested_total != dispense_amount:
                raise TransactionError(
                    "", "Requested denomination counts must exactly match payout"
                )

        # Create transaction
        tx_id = str(uuid.uuid4())
        if self._operation_mode:
            self._operation_mode.begin_transaction(tx_id)
            self._operation_owner = tx_id
        try:
            if transaction_type in {"bill-to-bill", "bill-to-coin"}:
                self._bill_acceptor.set_expected_denomination(f"PHP_{target_amount}")
            else:
                self._bill_acceptor.set_expected_denomination(None)

            await self._set_coin_acceptor_enabled(
                transaction_type == "coin-to-bill"
            )
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
                selected_dispense_counts=selected_dispense_counts,
            )
            session.add(record)
            await session.commit()
            self._active_tx = TransactionStateMachine(
                transaction_id=tx_id,
                transaction_type=transaction_type,
                ws_manager=self._ws,
                db_session=session,
                on_timeout=self._handle_timeout,
            )
            await self._active_tx.transition_to(
                TransactionState.WAITING_FOR_BILL
            )
        except Exception:
            if self._operation_mode and self._operation_owner:
                self._operation_mode.end_transaction(self._operation_owner)
                self._operation_owner = None
            raise

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

        # Step 0: Wait for bill at entry IR sensor (matching healthcheck flow)
        detected = await self._bill_acceptor.wait_for_bill(timeout=5.0)
        if not detected:
            tx.reset_timeout()
            return await self.get_transaction_state(tx.transaction_id)

        # Transition to AUTHENTICATING only after bill is detected
        await tx.transition_to(TransactionState.AUTHENTICATING)

        # Run bill acceptance (pass skip_entry_wait=True since entry IR was already confirmed above)
        result = await self._bill_acceptor.accept_bill(skip_entry_wait=True)

        if not result.success:
            # Check if this is a critical hardware/jam fault
            is_critical = result.error and (
                "jam" in result.error.lower()
                or "camera" in result.error.lower()
                or "serial" in result.error.lower()
                or "hardware" in result.error.lower()
                or "sensor" in result.error.lower()
            )
            if is_critical:
                logger.error(f"Critical hardware fault detected during bill acceptance: {result.error}")
                await tx.transition_to(
                    TransactionState.ERROR,
                    {"error_code": "HARDWARE_FAULT", "error_message": result.error},
                )
                await self._cleanup_active()
                return await self.get_transaction_state(tx.transaction_id)

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

        if tx.transaction_type != "coin-to-bill":
            return await self.get_transaction_state(tx.transaction_id)

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
            await self._set_coin_acceptor_enabled(False)

        return await self.get_transaction_state(tx.transaction_id)

    async def confirm_transaction(self) -> dict:
        """Confirm once and return current state for duplicate requests."""
        tx = self._require_active_transaction()
        async with self._confirm_lock:
            if tx.state in {
                TransactionState.DISPENSING,
                TransactionState.COMPLETE,
                TransactionState.ERROR,
                TransactionState.CLAIM_REQUIRED,
            }:
                return await self.get_transaction_state(tx.transaction_id)
            return await self._confirm_transaction_once(tx)

    @staticmethod
    def _build_dispense_plan(db_record, snapshot) -> tuple[DispensePlan, int, bool]:
        """Build the payout plan and any coin-only overpayment refund."""
        bill_inventory = snapshot.consumables.bill_dispenser_counts
        coin_inventory = snapshot.consumables.coin_counts

        if db_record.type != "coin-to-bill":
            amount = db_record.inserted_amount - db_record.fee
            plan = calculate_change(
                amount,
                {} if db_record.type == "bill-to-coin" else bill_inventory,
                coin_inventory if db_record.type == "bill-to-coin" else {},
                preferred_denoms=db_record.selected_dispense_denoms,
                requested_counts=db_record.selected_dispense_counts,
            )
            return plan, 0, False

        bill_plan = calculate_change(
            db_record.target_amount,
            bill_inventory,
            {},
            preferred_denoms=db_record.selected_dispense_denoms,
            requested_counts=db_record.selected_dispense_counts,
        )
        excess_refund = max(0, db_record.inserted_amount - db_record.total_due)
        if excess_refund == 0:
            return bill_plan, 0, False

        try:
            refund_plan = calculate_change(
                excess_refund,
                {},
                coin_inventory,
            )
        except InsufficientInventoryError:
            logger.warning(
                "Exact excess refund unavailable transaction_id=%s amount=%s; "
                "dispensing selected bill payout and claiming the refund",
                db_record.id,
                excess_refund,
            )
            return (
                DispensePlan(
                    items=list(bill_plan.items),
                    total_amount=bill_plan.total_amount + excess_refund,
                    is_exact=False,
                ),
                excess_refund,
                True,
            )

        return (
            DispensePlan(
                items=[*bill_plan.items, *refund_plan.items],
                total_amount=bill_plan.total_amount + refund_plan.total_amount,
                is_exact=True,
            ),
            excess_refund,
            False,
        )

    async def _confirm_transaction_once(
        self, tx: TransactionStateMachine
    ) -> dict:
        """User confirms transaction. Triggers dispensing.

        Returns:
            Final transaction state dict.
        """
        if not tx.is_in_state(TransactionState.WAITING_FOR_CONFIRMATION):
            raise TransactionError(
                tx.transaction_id,
                f"Cannot confirm in state {tx.state.value}",
            )

        await self._set_coin_acceptor_enabled(False)

        session = self._active_session
        db_record = await self._get_db_record(session, tx.transaction_id)
        if not db_record:
            raise TransactionError(tx.transaction_id, "Transaction record not found")

        # Coin-to-bill keeps the selected bill payout immutable and returns
        # any overpayment above total_due through the coin dispensers.
        snapshot = self._status.snapshot()
        plan, excess_refund, refund_unavailable = self._build_dispense_plan(
            db_record, snapshot
        )

        # Store dispense plan
        db_record.dispense_plan = {
            "items": [item.model_dump() for item in plan.items],
            "total_amount": plan.total_amount,
            "is_exact": plan.is_exact,
            "excess_refund_amount": excess_refund,
            "refund_unavailable": refund_unavailable,
        }
        await session.commit()

        # Transition to DISPENSING
        await tx.transition_to(TransactionState.DISPENSING)

        # Execute dispense
        result = await self._dispenser.execute_dispense(
            plan, reference_id=tx.transaction_id, source_kind="STANDARD"
        )

        if refund_unavailable and result.shortfall > 0 and not result.error:
            result.success = False
            result.error = "Exact excess coin refund unavailable"

        # Update record with result
        db_record.dispensed_amount = result.total_dispensed
        db_record.dispense_result = result.model_dump()
        await session.commit()

        if result.success:
            await tx.transition_to(
                TransactionState.COMPLETE,
                {"dispensed_amount": result.total_dispensed},
            )
            if self._receipt_service:
                await self._receipt_service.print_receipt(db_record)
        else:
            refund_only_shortfall = (
                refund_unavailable
                and result.total_dispensed >= db_record.target_amount
                and result.shortfall == excess_refund
            )
            if result.ambiguous_amount:
                reason_code = "AMBIGUOUS_DISPENSE"
            elif refund_only_shortfall:
                reason_code = "EXCESS_REFUND_UNAVAILABLE"
            else:
                reason_code = "PARTIAL_DISPENSE"
            if self._claim_service:
                claim = await self._claim_service.create(
                    source_kind="STANDARD",
                    transaction_id=db_record.id,
                    claim_kind="OUTPUT_SHORTFALL",
                    amount=result.shortfall,
                    currency="PHP",
                    reason_code=reason_code,
                    reason_message=result.error,
                    confirmed_dispensed_amount=result.total_dispensed,
                    ambiguous_amount=result.ambiguous_amount,
                    provisional=bool(result.ambiguous_amount),
                    record=db_record,
                    session=session,
                )
                await tx.transition_to(TransactionState.CLAIM_REQUIRED, {
                    "error_code": reason_code,
                    "error_message": result.error,
                    "dispensed_amount": result.total_dispensed,
                    "shortfall": result.shortfall,
                    "claim_ticket_code": claim.claim_ticket_code,
                })
            else:
                await tx.transition_to(TransactionState.ERROR, {
                    "error_code": reason_code,
                    "error_message": result.error,
                    "dispensed_amount": result.total_dispensed,
                    "shortfall": result.shortfall,
                    "claim_ticket_code": result.claim_ticket_code,
                })

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

        record = await self._get_db_record(self._active_session, tx.transaction_id)
        if record and record.inserted_amount > 0:
            raise TransactionError(
                tx.transaction_id,
                "CASH_ALREADY_ACCEPTED: transaction cannot be cancelled",
            )

        await tx.cancel()
        state = await self.get_transaction_state(tx.transaction_id)

        # Clean up active transaction
        await self._cleanup_active()

        return state

    async def _handle_timeout(self, expected_state: TransactionState) -> None:
        tx = self._require_active_transaction()
        record = await self._get_db_record(self._active_session, tx.transaction_id)
        if record and record.inserted_amount > 0 and self._claim_service:
            claim = await self._claim_service.create(
                source_kind="STANDARD",
                transaction_id=record.id,
                claim_kind="INPUT_REFUND",
                amount=record.inserted_amount,
                currency="PHP",
                reason_code="TIMEOUT_AFTER_CASH",
                reason_message=f"Timeout in {expected_state.value}",
                record=record,
                session=self._active_session,
            )
            await tx.transition_to(
                TransactionState.CLAIM_REQUIRED,
                {
                    "claim_ticket_code": claim.claim_ticket_code,
                    "error_code": "TIMEOUT_AFTER_CASH",
                    "error_message": f"Timeout in {expected_state.value}",
                },
            )
        else:
            await tx.transition_to(
                TransactionState.CANCELLED,
                {"error_code": "TIMEOUT", "error_message": f"Timeout in {expected_state.value}"},
            )
        await self._cleanup_active()

    async def get_transaction_state(self, transaction_id: str) -> dict:
        """Get current state of a transaction.

        Args:
            transaction_id: Transaction UUID.

        Returns:
            Dict with all transaction fields.
        """
        async with self._db_factory() as session:
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
                "payout_amount": (
                    db_record.target_amount - db_record.fee
                    if db_record.type in {"bill-to-bill", "bill-to-coin"}
                    else db_record.target_amount
                ),
                "inserted_amount": db_record.inserted_amount,
                "dispensed_amount": db_record.dispensed_amount,
                "inserted_denominations": db_record.inserted_denominations or {},
                "dispense_plan": db_record.dispense_plan,
                "dispense_result": db_record.dispense_result,
                "selected_dispense_denoms": db_record.selected_dispense_denoms or [],
                "selected_dispense_counts": db_record.selected_dispense_counts or {},
                "error_code": db_record.error_code,
                "error_message": db_record.error_message,
                "claim_ticket_code": db_record.claim_ticket_code,
                "shortfall": (
                    (db_record.dispense_result or {}).get("shortfall")
                    if db_record.dispense_result
                    else None
                ),
                "created_at": db_record.created_at.isoformat() if db_record.created_at else None,
                "updated_at": db_record.updated_at.isoformat() if db_record.updated_at else None,
                "completed_at": db_record.completed_at.isoformat() if db_record.completed_at else None,
            }

        return result


    async def recover_pending_transactions(self) -> None:
        """Close non-physical transactions interrupted by a backend crash."""
        async with self._db_factory() as session:
            stuck_result = await session.execute(
                select(TransactionRecord).where(
                    TransactionRecord.state.in_(
                        {
                            TransactionState.AUTHENTICATING.value,
                            TransactionState.SORTING.value,
                            TransactionState.DISPENSING.value,
                        }
                    ),
                    ~TransactionRecord.type.like("forex-%")
                )
            )
            stuck_records = stuck_result.scalars().all()
            for record in stuck_records:
                logger.warning(
                    f"Recovering transaction {record.id} stuck in active state {record.state}"
                )
                if self._claim_service and record.inserted_amount > 0:
                    dispensing = record.state == TransactionState.DISPENSING.value
                    planned_output = int(
                        (record.dispense_plan or {}).get("total_amount") or 0
                    )
                    default_output = (
                        record.target_amount
                        if record.type == "coin-to-bill"
                        else record.target_amount - record.fee
                    )
                    await self._claim_service.create(
                        source_kind="STANDARD",
                        transaction_id=record.id,
                        claim_kind="OUTPUT_SHORTFALL" if dispensing else "INPUT_REFUND",
                        amount=(planned_output or default_output)
                        if dispensing
                        else record.inserted_amount,
                        currency="PHP",
                        reason_code="CRASH_RECOVERY",
                        reason_message="Recovered interrupted transaction during startup",
                        provisional=dispensing,
                        record=record,
                        session=session,
                    )
                else:
                    record.state = TransactionState.ERROR.value
                    record.error_code = "CRASH_RECOVERY"
                    record.error_message = "Recovered from stuck active state during startup"
                    record.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

            if stuck_records:
                await session.commit()
            else:
                logger.info("No stuck standard transactions to recover")

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
        try:
            await self._set_coin_acceptor_enabled(False)
        except Exception as exc:
            logger.error("Failed to disable coin acceptor during cleanup: %s", exc)
        finally:
            if self._active_session:
                await self._active_session.close()
                self._active_session = None
            self._active_tx = None
            if self._operation_mode and self._operation_owner:
                self._operation_mode.end_transaction(self._operation_owner)
                self._operation_owner = None

    async def _set_coin_acceptor_enabled(self, enabled: bool) -> None:
        if self._coin_controller is None:
            return
        await self._coin_controller.set_coin_acceptor_enabled(enabled)
