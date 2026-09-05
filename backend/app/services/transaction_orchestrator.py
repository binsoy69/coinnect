"""Transaction orchestrator coordinating the full money changer lifecycle.

This is the central coordinator connecting the bill acceptor, change
calculator, dispense orchestrator, and transaction state machine.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.ws import ConnectionManager
from app.core.constants import BILL_DENOM_VALUES, BillDenom
from app.core.errors import (
    InsufficientInventoryError,
    TransactionError,
    QuoteChangedError,
    PayoutReapprovalRequiredError,
)
from app.models.db_models import (
    TransactionRecord,
    TransactionState,
    ConverterQuote,
    ClaimRecord,
    ConverterIntakeOperation,
    ConverterCoinSession,
)
from app.services.inventory_service import InventoryLocation
from app.models.converter import (
    ConverterQuotePayload,
    ConverterClaimSnapshot,
    PayoutItem,
)
from app.services.converter_payout_planner import (
    plan_payout,
    PHP_BILL_DENOMINATIONS,
    PHP_COIN_DENOMINATIONS,
)
from app.models.events import WSEvent, WSEventType
from app.services.bill_acceptor import BillAcceptor
from app.services.change_calculator import DispensePlan, DispensePlanItem, calculate_change
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
        settings=None,
        inventory_service=None,
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
        self._start_lock = asyncio.Lock()
        self._accounting_lock = asyncio.Lock()
        self._intake_lock = asyncio.Lock()
        self._termination_requested = False
        self._claim_service = claim_service
        self._settings = (
            settings
            or getattr(machine_status, "_settings", None)
            or get_settings()
        )
        self._inventory = (
            inventory_service
            or getattr(self._dispenser, "_inventory", None)
            or getattr(self._bill_acceptor, "_inventory", None)
        )
        self._has_accounting_fault: bool = False
        self._accounting_retry_task: Optional[asyncio.Task] = None
        import time as _py_time
        self._last_activity_mono: float = _py_time.monotonic()
        self._warning_active: bool = False

    @property
    def has_accounting_fault(self) -> bool:
        return self._has_accounting_fault

    @property
    def has_active_transaction(self) -> bool:
        return self._active_tx is not None

    @property
    def active_transaction_id(self) -> Optional[str]:
        return self._active_tx.transaction_id if self._active_tx else None

    async def start_transaction(self, transaction_type=None, target_amount=None,
                                selected_dispense_denoms=None, selected_dispense_counts=None,
                                fee=None, quote_id=None):
        async with self._start_lock:
            return await self._start_transaction_once(transaction_type, target_amount,
                selected_dispense_denoms or [], selected_dispense_counts, fee, quote_id)

    async def _start_transaction_once(
        self,
        transaction_type: str,
        target_amount: int,
        selected_dispense_denoms: list,
        selected_dispense_counts: Optional[dict] = None,
        fee: Optional[int] = None,
        quote_id: Optional[str] = None,
    ) -> dict:
        """Create and start a new money changer transaction.

        Args:
            transaction_type: "bill-to-bill", "bill-to-coin", or "coin-to-bill"
            target_amount: Amount user selected to convert
            selected_dispense_denoms: User-selected dispense denominations
            selected_dispense_counts: User-selected breakdown quantities (e.g. {"500": 1, "100": 4})
            fee: Internal caller override fee (otherwise from settings)
            quote_id: Optional quote proposal ID from pre-flight /quote request

        Returns:
            Transaction state dict.

        Raises:
            TransactionError: If a transaction is already active or machine not ready.
            QuoteChangedError: If quote terms or stock changed since quote creation.
        """
        if self._active_tx is None:
            async with self._db_factory() as session:
                unresolved_bill = (await session.execute(select(ConverterIntakeOperation.id).where(
                    ConverterIntakeOperation.state.in_(["PREPARED", "UNCERTAIN"])
                ).limit(1))).scalar_one_or_none()
                unresolved_coin = (await session.execute(select(ConverterCoinSession.id).where(
                    ConverterCoinSession.state != "CLOSED"
                ).limit(1))).scalar_one_or_none()
                if unresolved_bill or unresolved_coin:
                    self._has_accounting_fault = True
        if self._has_accounting_fault:
            raise TransactionError("", "ACCOUNTING_FAULT: Machine has pending accounting reconciliation")

        if not self._settings.use_mock_serial:
            await self._bill_acceptor._bill.verify_converter_protocol()
            await self._coin_controller.verify_converter_protocol()

        if self._active_tx is not None:
            raise TransactionError(
                self._active_tx.transaction_id,
                "A transaction is already in progress",
            )

        if quote_id:
            async with self._db_factory() as quote_session:
                proposal = await quote_session.get(ConverterQuote, quote_id)
                if proposal is None or proposal.transaction_id is not None:
                    raise TransactionError("", "Quote is missing or already belongs to a transaction")
                if transaction_type is not None and transaction_type != proposal.service_type:
                    raise TransactionError("", "Quote type does not match request")
                if target_amount is not None and target_amount != proposal.input_amount:
                    raise TransactionError("", "Quote amount does not match request")
                transaction_type = proposal.service_type
                target_amount = proposal.input_amount

        settings = get_settings()
        fee_map = {
            "bill-to-bill": settings.fee_bill_to_bill,
            "bill-to-coin": settings.fee_bill_to_coin,
            "coin-to-bill": settings.fee_coin_to_bill,
        }
        if transaction_type not in fee_map:
            raise TransactionError("", "Unsupported transaction type")
        fee = fee_map[transaction_type]

        # Validate machine is ready
        snapshot = self._status.snapshot()
        if snapshot.security.tamper_active:
            raise TransactionError("", "Machine is in lockdown mode")
        if self._status.should_block_dispensing_for_inventory_reconciliation():
            raise TransactionError("", "Inventory reconciliation is required")

        bill_inventory = (
            {} if transaction_type == "bill-to-coin"
            else snapshot.consumables.bill_dispenser_counts
        )
        coin_inventory = (
            snapshot.consumables.coin_counts
            if transaction_type == "bill-to-coin" else {}
        )

        quote_record = None
        if quote_id:
            async with self._db_factory() as check_session:
                q_res = await check_session.execute(
                    select(ConverterQuote).where(ConverterQuote.id == quote_id)
                )
                quote_record = q_res.scalar_one_or_none()
                if not quote_record:
                    raise TransactionError("", f"Quote {quote_id} not found")

                now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                is_stale = False
                if quote_record.expires_at <= now_utc:
                    is_stale = True
                elif quote_record.service_type != transaction_type or quote_record.input_amount != target_amount:
                    is_stale = True
                elif quote_record.fee != fee:
                    is_stale = True

                rechecked_plan = plan_payout(
                    transaction_type,
                    target_amount if transaction_type == "coin-to-bill" else target_amount - fee,
                    bill_inventory,
                    coin_inventory,
                    requested_counts=quote_record.requested_counts,
                )
                if not rechecked_plan.success:
                    is_stale = True
                else:
                    rechecked_items = [item.model_dump() for item in rechecked_plan.items]
                    if rechecked_items != quote_record.items:
                        is_stale = True

                if is_stale:
                    new_payload = None
                    if rechecked_plan.success:
                        new_qid = str(uuid.uuid4())
                        now_dt = datetime.now(timezone.utc)
                        exp_dt = now_dt + timedelta(seconds=120)
                        new_q = ConverterQuote(
                            id=new_qid,
                            transaction_id=None,
                            service_type=transaction_type,
                            input_amount=target_amount,
                            fee=fee,
                            total_due=(
                                target_amount
                                if transaction_type in {"bill-to-bill", "bill-to-coin"}
                                else target_amount + fee
                            ),
                            payout_amount=rechecked_plan.payout_amount,
                            items=[item.model_dump() for item in rechecked_plan.items],
                            requested_counts=rechecked_plan.requested_counts,
                            is_substitution=rechecked_plan.is_substitution,
                            substitution_notice=rechecked_plan.substitution_notice,
                            created_at=now_dt.replace(tzinfo=None),
                            expires_at=exp_dt.replace(tzinfo=None),
                        )
                        check_session.add(new_q)
                        await check_session.commit()
                        new_payload = ConverterQuotePayload(
                            id=new_qid,
                            transaction_id=None,
                            service_type=transaction_type,
                            input_amount=target_amount,
                            fee=fee,
                            total_due=new_q.total_due,
                            payout_amount=new_q.payout_amount,
                            items=rechecked_plan.items,
                            requested_counts=rechecked_plan.requested_counts,
                            is_substitution=rechecked_plan.is_substitution,
                            substitution_notice=rechecked_plan.substitution_notice,
                            created_at=now_dt.isoformat(),
                            expires_at=exp_dt.isoformat(),
                        )
                    raise QuoteChangedError(new_quote=new_payload.model_dump() if new_payload else None)

                dispense_amount = quote_record.payout_amount
                total_due = quote_record.total_due
                selected_dispense_counts = quote_record.requested_counts
                selected_dispense_denoms = [int(item.get("value", 0)) for item in quote_record.items]
                approved_quote_id = quote_record.id
        else:
            if transaction_type in {"bill-to-bill", "bill-to-coin"}:
                total_due = target_amount
                dispense_amount = target_amount - fee
                if dispense_amount < 0:
                    raise TransactionError("", f"Fee {fee} exceeds target amount {target_amount}")
            else:
                total_due = target_amount + fee
                dispense_amount = target_amount

            plan = plan_payout(
                transaction_type,
                dispense_amount,
                bill_inventory,
                coin_inventory,
                requested_counts=selected_dispense_counts,
            )
            if not plan.success:
                raise TransactionError("", f"Cannot dispense requested amount: {plan.reason}")

            if selected_dispense_counts is not None:
                requested_total = sum(
                    int(denom) * int(count)
                    for denom, count in selected_dispense_counts.items()
                )
                if requested_total != dispense_amount:
                    raise TransactionError(
                        "", "Requested denomination counts must exactly match payout"
                    )

            qid = str(uuid.uuid4())
            now_dt = datetime.now(timezone.utc)
            exp_dt = now_dt + timedelta(seconds=120)
            quote_record = ConverterQuote(
                id=qid,
                transaction_id=None,
                service_type=transaction_type,
                input_amount=target_amount,
                fee=fee,
                total_due=total_due,
                payout_amount=dispense_amount,
                items=[item.model_dump() for item in plan.items],
                requested_counts=plan.requested_counts,
                is_substitution=plan.is_substitution,
                substitution_notice=plan.substitution_notice,
                created_at=now_dt.replace(tzinfo=None),
                expires_at=exp_dt.replace(tzinfo=None),
            )
            approved_quote_id = qid

        # Create transaction
        tx_id = str(uuid.uuid4())
        if self._operation_mode:
            self._operation_mode.begin_transaction(tx_id)
            self._operation_owner = tx_id
        try:
            if transaction_type in {"bill-to-bill", "bill-to-coin"}:
                r = self._bill_acceptor.set_expected_denomination(f"PHP_{target_amount}")
            else:
                r = self._bill_acceptor.set_expected_denomination(None)
            if asyncio.iscoroutine(r):
                await r

            session = self._db_factory()
            self._active_session = session

            coin_session_id = None
            if transaction_type == "coin-to-bill":
                stmt = select(func.coalesce(func.max(ConverterCoinSession.session_id), 0) + 1)
                res = await session.execute(stmt)
                coin_session_id = res.scalar_one()
                if not 0 < coin_session_id <= 0xFFFFFFFF:
                    raise TransactionError(tx_id, "Coin session identifiers exhausted")
                coin_sess = ConverterCoinSession(
                    session_id=coin_session_id,
                    transaction_id=tx_id,
                    state="ACTIVE",
                )
                session.add(coin_sess)

            now_utc = datetime.now(timezone.utc)
            warn_sec = getattr(self._settings, "inactivity_warning_seconds", 60.0)
            time_sec = getattr(self._settings, "inactivity_timeout_seconds", 90.0)
            converter_metadata = {
                "revision": 1,
                "approved_quote_id": approved_quote_id,
                "pending_quote_id": None,
                "acceptance_phase": "OPEN",
                "warning_at": (now_utc + timedelta(seconds=warn_sec)).isoformat(),
                "expires_at": (now_utc + timedelta(seconds=time_sec)).isoformat(),
                "coin_session_id": coin_session_id,
                "termination_reason": None,
            }
            record = TransactionRecord(
                id=tx_id,
                type=transaction_type,
                state=TransactionState.IDLE.value,
                target_amount=target_amount,
                fee=fee,
                total_due=total_due,
                selected_dispense_denoms=selected_dispense_denoms,
                selected_dispense_counts=selected_dispense_counts,
                converter_metadata=converter_metadata,
            )
            session.add(record)
            quote_record.transaction_id = tx_id
            await session.merge(quote_record)
            await session.commit()
            self._active_tx = TransactionStateMachine(
                transaction_id=tx_id,
                transaction_type=transaction_type,
                ws_manager=self._ws,
                db_session=session,
                on_timeout=self._handle_timeout,
                on_warning=self._handle_inactivity_warning,
                warning_seconds=warn_sec,
                timeout_seconds=time_sec,
            )
            await self._active_tx.transition_to(
                TransactionState.WAITING_FOR_BILL
            )
            if transaction_type == "coin-to-bill":
                await self._coin_controller.coin_session_start(coin_session_id)
            else:
                await self._set_coin_acceptor_enabled(False)
        except Exception as exc:
            if self._active_tx is not None:
                self._has_accounting_fault = True
                if transaction_type == "coin-to-bill":
                    self._accounting_retry_task = asyncio.create_task(self._retry_coin_accounting(tx_id))
                raise TransactionError(tx_id, "Startup interrupted; cash acceptance requires reconciliation") from exc
            if self._active_session:
                await self._active_session.rollback()
                await self._active_session.close()
                self._active_session = None
            if self._operation_mode and self._operation_owner:
                self._operation_mode.end_transaction(self._operation_owner)
                self._operation_owner = None
            raise

        logger.info(
            f"Transaction started: {tx_id} type={transaction_type} "
            f"amount={target_amount} fee={fee}"
        )

        return await self.get_transaction_state(tx_id)

    async def _commit_retained_bill(self, op_id, transaction_id, denomination_str, bill_value):
        async with self._accounting_lock:
            return await self._commit_retained_bill_once(op_id, transaction_id, denomination_str, bill_value)

    async def _commit_retained_bill_once(
        self,
        op_id: str,
        transaction_id: str,
        denomination_str: str,
        bill_value: int,
    ) -> bool:
        """Atomically credit inventory, customer transaction, and mark intake operation RETAINED."""
        runtime_increment = False
        async with self._db_factory() as session:
            op = await session.get(ConverterIntakeOperation, op_id)
            if not op:
                op = ConverterIntakeOperation(
                    id=op_id,
                    transaction_id=transaction_id,
                    denomination=denomination_str,
                    value=bill_value,
                    state="PREPARED",
                    inventory_credited=False,
                    transaction_credited=False,
                )
                session.add(op)

            db_record = await session.get(TransactionRecord, transaction_id)
            if not db_record:
                raise RuntimeError(f"Transaction {transaction_id} not found during intake commit")

            if not op.transaction_credited:
                db_record.inserted_amount += bill_value
                inserted = dict(db_record.inserted_denominations or {})
                denom_key = str(bill_value)
                inserted[denom_key] = inserted.get(denom_key, 0) + 1
                db_record.inserted_denominations = inserted
                meta = dict(db_record.converter_metadata or {})
                meta["revision"] = meta.get("revision", 1) + 1
                if db_record.inserted_amount >= db_record.total_due and db_record.total_due > 0:
                    meta["acceptance_phase"] = "CLOSED"
                else:
                    meta["acceptance_phase"] = "OPEN"
                db_record.converter_metadata = meta
                op.transaction_credited = True

            if not op.inventory_credited and self._inventory is not None:
                storage_denom = denomination_str
                if storage_denom.startswith("USD_"):
                    storage_denom = "USD"
                elif storage_denom.startswith("EUR_"):
                    storage_denom = "EUR"
                await self._inventory.adjust_in_session(
                    session,
                    InventoryLocation.BILL_STORAGE,
                    storage_denom,
                    1,
                    reason="BILL_ACCEPTED",
                    reference_id=op_id,
                )
                op.inventory_credited = True

            if self._inventory is None and not op.inventory_credited:
                runtime_increment = True
                op.inventory_credited = True
            op.state = "RETAINED"
            await session.commit()

        if self._inventory is not None:
            await self._inventory.refresh_runtime()
        elif runtime_increment:
            self._status.increment_bill_storage(denomination_str)

        return True

    async def _retry_intake_accounting(
        self,
        op_id: str,
        transaction_id: str,
        denomination_str: str,
        bill_value: int,
    ) -> None:
        """Background retry loop executing every 2 seconds until accounting reconciles."""
        while True:
            await asyncio.sleep(2.0)
            try:
                await self._commit_retained_bill(
                    op_id, transaction_id, denomination_str, bill_value
                )
                if self._termination_requested and self._active_tx:
                    await self.request_claim(transaction_id)
                    self._termination_requested = False
                    self._has_accounting_fault = False
                    await self._broadcast_converter_snapshot(transaction_id)
                    break
                self._has_accounting_fault = False
                logger.info("Accounting reconciled for operation %s", op_id)
                if self._active_tx and self._active_tx.transaction_id == transaction_id:
                    async with self._db_factory() as session:
                        rec = await session.get(TransactionRecord, transaction_id)
                        if rec and rec.inserted_amount >= rec.total_due and rec.total_due > 0:
                            if self._active_tx.is_in_state(TransactionState.WAITING_FOR_BILL):
                                await self._active_tx.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)
                await self._broadcast_converter_snapshot(transaction_id)
                break
            except Exception as exc:
                self._has_accounting_fault = True
                logger.warning(
                    f"Accounting retry for op {op_id} failed: {exc}. Retrying in 2 seconds..."
                )

    async def handle_bill_inserted(self) -> dict:
        if self._intake_lock.locked():
            raise TransactionError("", "Bill acceptance already in progress")
        async with self._intake_lock:
            try:
                return await self._handle_bill_inserted_once()
            except TransactionError:
                raise
            except Exception:
                self._has_accounting_fault = True
                if self._active_tx and (not self._accounting_retry_task or self._accounting_retry_task.done()):
                    self._accounting_retry_task = asyncio.create_task(
                        self._recover_intake_failure(self._active_tx.transaction_id)
                    )
                raise

    async def _recover_intake_failure(self, transaction_id):
        """Recover accounting after intake has stopped, without replaying motion."""
        while self._active_tx and self._active_tx.transaction_id == transaction_id:
            await asyncio.sleep(2)
            try:
                async with self._confirm_lock:
                    tx = self._active_tx
                    if not tx or tx.transaction_id != transaction_id:
                        return
                    session = self._active_session
                    await session.rollback()
                    record = await self._get_db_record(session, transaction_id)
                    unresolved = (await session.execute(select(ConverterIntakeOperation).where(
                        ConverterIntakeOperation.transaction_id == transaction_id,
                        ConverterIntakeOperation.state.in_(["PREPARED", "UNCERTAIN"]),
                    ))).scalars().all()
                    for operation in unresolved:
                        operation.state = "UNCERTAIN"
                    ambiguity = sum(operation.value for operation in unresolved)
                    if self._claim_service and (record.inserted_amount or unresolved):
                        claim = await self._claim_service.create(
                            source_kind="STANDARD", transaction_id=transaction_id, claim_kind="INPUT_REFUND",
                            amount=max(0, record.inserted_amount - record.dispensed_amount) + ambiguity,
                            currency="PHP", reason_code="INTAKE_ACCOUNTING_FAILURE",
                            reason_message="Intake stopped after an accounting failure",
                            provisional=bool(unresolved), ambiguous_amount=ambiguity,
                            record=record, session=session,
                        )
                        await tx.transition_to(TransactionState.CLAIM_REQUIRED, {"claim_ticket_code": claim.claim_ticket_code})
                    else:
                        await tx.transition_to(TransactionState.ERROR, {"error_code": "INTAKE_ACCOUNTING_FAILURE"})
                    await self._cleanup_active()
                    self._has_accounting_fault = bool(unresolved)
                    await self._broadcast_converter_snapshot(transaction_id)
                    return
            except Exception:
                logger.exception("Intake accounting recovery remains pending for %s", transaction_id)

    async def _handle_bill_inserted_once(self) -> dict:
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

        if self._has_accounting_fault:
            raise TransactionError(
                tx.transaction_id,
                "ACCOUNTING_FAULT: Bill intake blocked due to pending accounting reconciliation",
            )

        if tx.transaction_type == "coin-to-bill":
            raise TransactionError(tx.transaction_id, "This transaction accepts coins only")

        # Step 0: Wait for bill at entry IR sensor (matching healthcheck flow)
        detected = await self._bill_acceptor.wait_for_bill(timeout=5.0)
        if not detected:
            return await self.get_transaction_state(tx.transaction_id)

        # Transition to AUTHENTICATING only after bill is detected
        await tx.transition_to(TransactionState.AUTHENTICATING)

        op_id = str(uuid.uuid4())
        op_recorded = False

        async def _prepare_intake(denom: BillDenom, val: int) -> None:
            async with self._db_factory() as session:
                op = ConverterIntakeOperation(
                    id=op_id,
                    transaction_id=tx.transaction_id,
                    denomination=denom.value,
                    value=val,
                    state="PREPARED",
                    inventory_credited=False,
                    transaction_credited=False,
                )
                session.add(op)
                await session.commit()

        async def _record_outcome(denom: BillDenom, val: int) -> None:
            nonlocal op_recorded
            try:
                await self._commit_retained_bill(
                    op_id, tx.transaction_id, denom.value, val
                )
                op_recorded = True
            except Exception as exc:
                logger.error(
                    f"Failed to commit retained bill {op_id} for tx {tx.transaction_id}: {exc}. Activating ACCOUNTING_FAULT and retry loop."
                )
                self._has_accounting_fault = True
                self._termination_requested = True
                self._accounting_retry_task = asyncio.create_task(
                    self._retry_intake_accounting(
                        op_id, tx.transaction_id, denom.value, val
                    )
                )

        # Run bill acceptance (pass skip_entry_wait=True since entry IR was already confirmed above)
        result = await self._bill_acceptor.accept_bill(
            skip_entry_wait=True,
            on_authenticated=_prepare_intake,
            custom_store_and_record=_record_outcome,
        )

        if not result.success:
            async with self._db_factory() as outcome_session:
                operation = await outcome_session.get(ConverterIntakeOperation, op_id)
                if operation is None and result.error == "INTAKE_INTERRUPTED":
                    operation = ConverterIntakeOperation(id=op_id, transaction_id=tx.transaction_id,
                        denomination="UNKNOWN", value=0, state="PREPARED")
                    outcome_session.add(operation)
                if operation and operation.state == "PREPARED":
                    operation.state = "UNCERTAIN"
                    operation.error_code = result.error
                    self._has_accounting_fault = True
                    await outcome_session.commit()
                    record = await self._get_db_record(self._active_session, tx.transaction_id)
                    if self._claim_service:
                        claim = await self._claim_service.create(
                            source_kind="STANDARD", transaction_id=tx.transaction_id,
                            claim_kind="INPUT_REFUND",
                            amount=max(0, record.inserted_amount - record.dispensed_amount) + operation.value,
                            currency="PHP", reason_code="INTAKE_UNCERTAIN",
                            reason_message="Bill retention requires technician reconciliation",
                            ambiguous_amount=operation.value, provisional=True,
                            record=record, session=self._active_session,
                        )
                        await tx.transition_to(TransactionState.CLAIM_REQUIRED, {
                            "claim_ticket_code": claim.claim_ticket_code,
                            "error_code": "INTAKE_UNCERTAIN",
                        })
                    else:
                        await tx.transition_to(TransactionState.ERROR, {"error_code": "INTAKE_UNCERTAIN"})
                    await self._cleanup_active()
                    return await self.get_transaction_state(tx.transaction_id)
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
                record = await self._get_db_record(self._active_session, tx.transaction_id)
                if record.inserted_amount > 0 and self._claim_service:
                    claim = await self._claim_service.create(
                        source_kind="STANDARD", transaction_id=tx.transaction_id, claim_kind="INPUT_REFUND",
                        amount=max(0, record.inserted_amount - record.dispensed_amount), currency="PHP",
                        reason_code="HARDWARE_FAULT", reason_message=result.error,
                        record=record, session=self._active_session,
                    )
                    await tx.transition_to(TransactionState.CLAIM_REQUIRED, {"claim_ticket_code": claim.claim_ticket_code})
                    await self._cleanup_active()
                    return await self.get_transaction_state(tx.transaction_id)
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
            await self._reset_inactivity_timer()
            return await self.get_transaction_state(tx.transaction_id)

        # Bill accepted - transition through SORTING back to WAITING_FOR_BILL
        await tx.transition_to(
            TransactionState.SORTING,
            {"denomination": result.denomination.value, "value": result.value},
        )

        # If custom_store_and_record was not called (e.g. mock bill acceptor in tests),
        # ensure atomic retention commit is run
        if not op_recorded and not self._has_accounting_fault:
            try:
                await self._commit_retained_bill(
                    op_id, tx.transaction_id, result.denomination.value, result.value
                )
                op_recorded = True
            except Exception as exc:
                logger.error(
                    f"Failed to commit retained bill {op_id}: {exc}. Starting accounting retry."
                )
                self._has_accounting_fault = True
                self._termination_requested = True
                self._accounting_retry_task = asyncio.create_task(
                    self._retry_intake_accounting(
                        op_id, tx.transaction_id, result.denomination.value, result.value
                    )
                )

        # Transition back to WAITING_FOR_BILL first (SORTING -> WAITING_FOR_BILL)
        await tx.transition_to(TransactionState.WAITING_FOR_BILL)

        # If accounting fault is active, do not transition to confirmation yet
        if self._has_accounting_fault:
            await self._broadcast_converter_snapshot(tx.transaction_id)
            return await self.get_transaction_state(tx.transaction_id)

        # Check if enough money inserted
        async with self._db_factory() as session:
            db_record = await self._get_db_record(session, tx.transaction_id)
            if db_record and db_record.inserted_amount >= db_record.total_due and db_record.total_due > 0:
                await tx.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)
            await self._reset_inactivity_timer()

        await self._reset_inactivity_timer()
        await self._broadcast_converter_snapshot(tx.transaction_id)
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
            meta = dict(db_record.converter_metadata or {})
            meta["revision"] = meta.get("revision", 1) + 1
            db_record.converter_metadata = meta
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
        await self._broadcast_converter_snapshot(tx.transaction_id)

        # Check if enough money
        if db_record and db_record.inserted_amount >= db_record.total_due:
            await tx.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)
            await self._set_coin_acceptor_enabled(False)

        return await self.get_transaction_state(tx.transaction_id)

    async def _apply_coin_counts(self, transaction_id, sid, counts, closed=False):
        """Atomically advance cumulative cursors, customer credit, and inventory."""
        async with self._accounting_lock:
            async with self._db_factory() as session:
                coin_session = (await session.execute(select(ConverterCoinSession).where(
                    ConverterCoinSession.session_id == sid,
                    ConverterCoinSession.transaction_id == transaction_id,
                ))).scalar_one_or_none()
                if not coin_session or coin_session.state == "CLOSED":
                    return False
                record = await session.get(TransactionRecord, transaction_id)
                inserted = dict(record.inserted_denominations or {})
                added = 0
                for denom, count in counts.items():
                    if denom not in {1, 5, 10, 20} or not isinstance(count, int) or not 0 <= count <= 65535:
                        raise TransactionError(transaction_id, "Invalid coin counter")
                    attr = f"cursor_php_{denom}"
                    cursor = getattr(coin_session, attr)
                    if count < cursor and closed:
                        raise TransactionError(transaction_id, "Final coin counter regressed")
                    delta = max(0, count - cursor)
                    if delta:
                        if self._inventory:
                            await self._inventory.adjust_in_session(
                                session, InventoryLocation.COIN_DISPENSER, f"PHP_{denom}", delta,
                                reason="COIN_ACCEPTED", reference_id=transaction_id,
                            )
                        inserted[str(denom)] = inserted.get(str(denom), 0) + delta
                        added += delta * denom
                        setattr(coin_session, attr, count)
                    if closed:
                        setattr(coin_session, f"final_count_php_{denom}", count)
                record.inserted_amount += added
                record.inserted_denominations = inserted
                meta = dict(record.converter_metadata or {})
                if added or closed:
                    meta["revision"] = meta.get("revision", 0) + 1
                if closed:
                    coin_session.state = "CLOSED"
                    coin_session.closed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    meta["acceptance_phase"] = "CLOSED"
                record.converter_metadata = meta
                await session.commit()
            if self._inventory:
                await self._inventory.refresh_runtime()
        return bool(added)

    async def handle_coin_session_pulse(self, sid: int, seq: int, denom: int, count: int) -> dict:
        tx = self._active_tx
        if not tx or tx.transaction_type != "coin-to-bill":
            return {}
        try:
            added = await self._apply_coin_counts(tx.transaction_id, sid, {denom: count})
        except Exception:
            self._has_accounting_fault = True
            try:
                await self._coin_controller.coin_session_stop(sid)
            finally:
                if not self._accounting_retry_task or self._accounting_retry_task.done():
                    self._accounting_retry_task = asyncio.create_task(self._retry_coin_accounting(tx.transaction_id))
            raise
        if added and self._active_tx is tx:
            await self._reset_inactivity_timer()
            record = await self._get_db_record(self._active_session, tx.transaction_id)
            if record.inserted_amount >= record.total_due and tx.state == TransactionState.WAITING_FOR_BILL:
                await tx.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)
                await self._coin_controller.coin_session_stop(sid)
            await self._broadcast_converter_snapshot(tx.transaction_id)
        return await self.get_transaction_state(tx.transaction_id)

    async def _retry_coin_accounting(self, transaction_id):
        while self._active_tx and self._active_tx.transaction_id == transaction_id:
            await asyncio.sleep(2)
            try:
                await self._drain_and_reconcile_coin_session(transaction_id)
                await self.request_claim(transaction_id)
                self._has_accounting_fault = False
                await self._broadcast_converter_snapshot(transaction_id)
                return
            except Exception:
                self._has_accounting_fault = True
                logger.exception("Coin accounting reconciliation is still pending")

    async def _drain_and_reconcile_coin_session(self, transaction_id: str) -> None:
        async with self._db_factory() as session:
            coin_session = (await session.execute(select(ConverterCoinSession).where(
                ConverterCoinSession.transaction_id == transaction_id
            ).order_by(ConverterCoinSession.id.desc()))).scalars().first()
            if not coin_session or coin_session.state == "CLOSED":
                return
            sid = coin_session.session_id
            coin_session.state = "CLOSING"
            record = await session.get(TransactionRecord, transaction_id)
            meta = dict(record.converter_metadata or {})
            meta.update(acceptance_phase="CLOSING", revision=meta.get("revision", 0) + 1)
            record.converter_metadata = meta
            await session.commit()
        try:
            await self._coin_controller.coin_session_stop(sid)
            deadline = asyncio.get_running_loop().time() + self._settings.coin_session_timeout_ms / 1000 + 0.5
            while asyncio.get_running_loop().time() < deadline:
                report = await self._coin_controller.coin_session_status()
                if report.sid != sid:
                    raise TransactionError(transaction_id, "Coin session identifier mismatch")
                if report.session_state == "UNCERTAIN":
                    raise TransactionError(transaction_id, "Coin pulse train is unresolved")
                if report.session_state == "CLOSED":
                    await self._apply_coin_counts(transaction_id, sid, {
                        1: report.count_1, 5: report.count_5,
                        10: report.count_10, 20: report.count_20,
                    }, closed=True)
                    return
                await asyncio.sleep(0.1)
            raise TransactionError(transaction_id, "Coin drain timed out")
        except Exception:
            self._has_accounting_fault = True
            async with self._db_factory() as session:
                coin_session = (await session.execute(select(ConverterCoinSession).where(
                    ConverterCoinSession.session_id == sid
                ))).scalar_one()
                coin_session.state = "UNCERTAIN"
                await session.commit()
            tx = self._active_tx
            if tx and tx.transaction_id == transaction_id and self._claim_service:
                record = await self._get_db_record(self._active_session, transaction_id)
                claim = await self._claim_service.create(
                    source_kind="STANDARD", transaction_id=transaction_id, claim_kind="INPUT_REFUND",
                    amount=max(0, record.inserted_amount - record.dispensed_amount), currency="PHP",
                    reason_code="COIN_SESSION_UNCERTAIN",
                    reason_message="Final coin count requires technician reconciliation; claim amount is provisional",
                    provisional=True, record=record, session=self._active_session,
                )
                await tx.transition_to(TransactionState.CLAIM_REQUIRED, {"claim_ticket_code": claim.claim_ticket_code})
                await self._cleanup_active()
            raise

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
    def _build_dispense_plan(
        db_record, snapshot, approved_quote=None
    ) -> tuple[DispensePlan, int, bool]:
        """Build the payout plan and any coin-only overpayment refund."""
        bill_inventory = snapshot.consumables.bill_dispenser_counts
        coin_inventory = snapshot.consumables.coin_counts

        if approved_quote and approved_quote.items:
            items = [
                DispensePlanItem(
                    denom=str(item.get("denom") or f"PHP_{item.get('value', item.get('denomination', ''))}"),
                    denom_type=str(item.get("denom_type") or item.get("type", "bill")),
                    count=int(item.get("count", item.get("quantity", 0))),
                    value=int(item.get("value", item.get("denomination", 0))),
                )
                for item in approved_quote.items
            ]
            if db_record.type != "coin-to-bill":
                return (
                    DispensePlan(
                        items=items,
                        total_amount=approved_quote.payout_amount,
                        is_exact=True,
                    ),
                    0,
                    False,
                )
            else:
                excess_refund = max(0, db_record.inserted_amount - db_record.total_due)
                if excess_refund == 0:
                    return (
                        DispensePlan(
                            items=items,
                            total_amount=approved_quote.payout_amount,
                            is_exact=True,
                        ),
                        0,
                        False,
                    )
                try:
                    refund = plan_payout("bill-to-coin", excess_refund, {}, coin_inventory)
                    if not refund.success:
                        raise InsufficientInventoryError(excess_refund, 0, excess_refund)
                    refund_plan = DispensePlan(items=[DispensePlanItem(**item.model_dump()) for item in refund.items],
                        total_amount=excess_refund, is_exact=True)
                    return (
                        DispensePlan(
                            items=[*items, *refund_plan.items],
                            total_amount=approved_quote.payout_amount + refund_plan.total_amount,
                            is_exact=True,
                        ),
                        excess_refund,
                        False,
                    )
                except InsufficientInventoryError:
                    return (
                        DispensePlan(
                            items=items,
                            total_amount=approved_quote.payout_amount + excess_refund,
                            is_exact=False,
                        ),
                        excess_refund,
                        True,
                    )

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

        if self._has_accounting_fault or self._status.snapshot().security.tamper_active:
            raise TransactionError(tx.transaction_id, "Machine reconciliation is required")
        if tx.transaction_type == "coin-to-bill":
            await self._drain_and_reconcile_coin_session(tx.transaction_id)
        else:
            await self._set_coin_acceptor_enabled(False)

        session = self._active_session
        db_record = await self._get_db_record(session, tx.transaction_id)
        if not db_record:
            raise TransactionError(tx.transaction_id, "Transaction record not found")

        meta = dict(db_record.converter_metadata or {})
        if db_record.inserted_amount < db_record.total_due:
            raise TransactionError(tx.transaction_id, "Insufficient accepted cash")
        if meta.get("pending_quote_id"):
            current = await self.get_transaction_state(tx.transaction_id)
            raise PayoutReapprovalRequiredError(pending_quote=current["pending_quote"])
        approved_quote_id = meta.get("approved_quote_id")
        approved_quote = None
        if approved_quote_id:
            q_res = await session.execute(
                select(ConverterQuote).where(ConverterQuote.id == approved_quote_id)
            )
            approved_quote = q_res.scalar_one_or_none()

        snapshot = self._status.snapshot()
        bill_inventory = snapshot.consumables.bill_dispenser_counts
        coin_inventory = snapshot.consumables.coin_counts

        # Check stock for approved breakdown
        stock_available = True
        if approved_quote and approved_quote.items:
            for item in approved_quote.items:
                denom_str = str(item.get("denom", ""))
                qty = int(item.get("count", item.get("quantity", 0)))
                itype = item.get("denom_type", item.get("type", "bill"))
                val_str = str(item.get("value", ""))
                if itype == "coin":
                    avail = max(
                        0,
                        coin_inventory.get(
                            denom_str,
                            coin_inventory.get(
                                denom_str.replace("PHP_", ""),
                                coin_inventory.get(val_str, 0),
                            ),
                        ),
                    )
                    if avail < qty:
                        stock_available = False
                        break
                else:
                    avail = max(
                        0,
                        bill_inventory.get(
                            denom_str,
                            bill_inventory.get(
                                denom_str.replace("PHP_", ""),
                                bill_inventory.get(val_str, 0),
                            ),
                        ),
                    )
                    if avail < qty:
                        stock_available = False
                        break

        if not stock_available:
            logger.warning(
                "Approved breakdown no longer available for tx %s. Attempting revised plan.",
                tx.transaction_id,
            )
            payout_target = (
                approved_quote.payout_amount
                if approved_quote
                else (
                    db_record.target_amount
                    if db_record.type == "coin-to-bill"
                    else db_record.target_amount - db_record.fee
                )
            )
            avail_bills = {} if db_record.type == "bill-to-coin" else bill_inventory
            avail_coins = coin_inventory if db_record.type == "bill-to-coin" else {}
            revised_plan = plan_payout(
                db_record.type,
                payout_target,
                avail_bills,
                avail_coins,
                requested_counts=approved_quote.requested_counts if approved_quote else None,
            )
            if revised_plan.success:
                new_qid = str(uuid.uuid4())
                now_dt = datetime.now(timezone.utc)
                exp_dt = now_dt + timedelta(seconds=120)
                new_q = ConverterQuote(
                    id=new_qid,
                    transaction_id=tx.transaction_id,
                    service_type=db_record.type,
                    input_amount=db_record.target_amount,
                    fee=db_record.fee,
                    total_due=db_record.total_due,
                    payout_amount=payout_target,
                    items=[item.model_dump() for item in revised_plan.items],
                    requested_counts=revised_plan.requested_counts,
                    is_substitution=True,
                    substitution_notice=revised_plan.substitution_notice or "Stock changed; revised breakdown proposed.",
                    created_at=now_dt.replace(tzinfo=None),
                    expires_at=exp_dt.replace(tzinfo=None),
                )
                session.add(new_q)
                meta["pending_quote_id"] = new_qid
                meta["revision"] = meta.get("revision", 1) + 1
                meta["acceptance_phase"] = "CLOSED"
                db_record.converter_metadata = meta
                await session.commit()
                await self._broadcast_converter_snapshot(tx.transaction_id)
                new_payload = ConverterQuotePayload(
                    id=new_qid,
                    transaction_id=tx.transaction_id,
                    service_type=db_record.type,
                    input_amount=db_record.target_amount,
                    fee=db_record.fee,
                    total_due=db_record.total_due,
                    payout_amount=payout_target,
                    items=revised_plan.items,
                    requested_counts=revised_plan.requested_counts,
                    is_substitution=True,
                    substitution_notice=new_q.substitution_notice,
                    created_at=now_dt.isoformat(),
                    expires_at=exp_dt.isoformat(),
                )
                raise PayoutReapprovalRequiredError(
                    transaction_id=tx.transaction_id,
                    pending_quote=new_payload.model_dump(),
                )
            else:
                logger.error(
                    "No exact revised breakdown possible for tx %s. Transitioning to CLAIM_REQUIRED.",
                    tx.transaction_id,
                )
                refund_amount = max(0, db_record.inserted_amount - db_record.dispensed_amount)
                if self._claim_service and refund_amount > 0:
                    claim = await self._claim_service.create(
                        source_kind="STANDARD",
                        transaction_id=db_record.id,
                        claim_kind="INPUT_REFUND",
                        amount=refund_amount,
                        currency="PHP",
                        reason_code="STOCK_EXHAUSTED",
                        reason_message="Payout breakdown no longer available and no alternative found",
                        record=db_record,
                        session=session,
                    )
                    meta["acceptance_phase"] = "CLOSED"
                    db_record.converter_metadata = meta
                    await session.commit()
                    await tx.transition_to(
                        TransactionState.CLAIM_REQUIRED,
                        {
                            "error_code": "STOCK_EXHAUSTED",
                            "error_message": "Payout breakdown no longer available",
                            "claim_ticket_code": claim.claim_ticket_code,
                        },
                    )
                else:
                    await tx.transition_to(
                        TransactionState.ERROR,
                        {
                            "error_code": "STOCK_EXHAUSTED",
                            "error_message": "Payout breakdown no longer available",
                        },
                    )
                state = await self.get_transaction_state(tx.transaction_id)
                await self._cleanup_active()
                return state

        # Build dispense plan
        plan, excess_refund, refund_unavailable = self._build_dispense_plan(
            db_record, snapshot, approved_quote=approved_quote
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
                    amount=max(0, db_record.inserted_amount - result.total_dispensed),
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

    async def approve_quote(self, transaction_id: str, quote_id: str) -> dict:
        """Customer approves a replacement proposal for an active transaction."""
        if self._confirm_lock.locked():
            raise TransactionError(transaction_id, "Payout is in progress")
        async with self._confirm_lock:
            return await self._approve_quote_once(transaction_id, quote_id)

    async def _approve_quote_once(self, transaction_id: str, quote_id: str) -> dict:
        tx = self._require_active_transaction()
        if tx.transaction_id != transaction_id:
            raise TransactionError(transaction_id, "Transaction is not active")

        session = self._active_session
        db_record = await self._get_db_record(session, transaction_id)
        if not db_record:
            raise TransactionError(transaction_id, "Transaction record not found")

        q_res = await session.execute(
            select(ConverterQuote).where(ConverterQuote.id == quote_id)
        )
        quote = q_res.scalar_one_or_none()
        if not quote:
            raise TransactionError(transaction_id, f"Quote {quote_id} not found")

        meta = dict(db_record.converter_metadata or {})
        if tx.state != TransactionState.WAITING_FOR_CONFIRMATION:
            raise TransactionError(transaction_id, "Payout approval is not allowed in this state")
        if meta.get("pending_quote_id") != quote_id or quote.transaction_id != transaction_id:
            raise TransactionError(transaction_id, "Only this transaction's pending quote can be approved")
        approved = await session.get(ConverterQuote, meta.get("approved_quote_id"))
        if approved is None or any(
            getattr(quote, field) != getattr(approved, field)
            for field in ("service_type", "input_amount", "fee", "total_due", "payout_amount")
        ):
            raise TransactionError(transaction_id, "Replacement quote changes approved financial terms")
        if quote.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
            raise TransactionError(transaction_id, "Replacement quote expired")

        snapshot = self._status.snapshot()
        bill_inventory = snapshot.consumables.bill_dispenser_counts
        coin_inventory = snapshot.consumables.coin_counts

        for item in quote.items:
            denom_str = str(item.get("denom", ""))
            qty = int(item.get("count", item.get("quantity", 0)))
            itype = item.get("denom_type", item.get("type", "bill"))
            val_str = str(item.get("value", ""))
            if itype == "coin":
                avail = max(
                    0,
                    coin_inventory.get(
                        denom_str,
                        coin_inventory.get(
                            denom_str.replace("PHP_", ""),
                            coin_inventory.get(val_str, 0),
                        ),
                    ),
                )
                if avail < qty:
                    raise TransactionError(transaction_id, "Proposed breakdown is no longer available in inventory")
            else:
                avail = max(
                    0,
                    bill_inventory.get(
                        denom_str,
                        bill_inventory.get(
                            denom_str.replace("PHP_", ""),
                            bill_inventory.get(val_str, 0),
                        ),
                    ),
                )
                if avail < qty:
                    raise TransactionError(transaction_id, "Proposed breakdown is no longer available in inventory")

        meta = dict(db_record.converter_metadata or {})
        meta["revision"] = meta.get("revision", 1) + 1
        meta["approved_quote_id"] = quote.id
        meta["pending_quote_id"] = None
        if db_record.inserted_amount >= db_record.total_due:
            meta["acceptance_phase"] = "CLOSED"
        else:
            meta["acceptance_phase"] = "OPEN"
        db_record.converter_metadata = meta

        db_record.selected_dispense_counts = quote.requested_counts
        db_record.selected_dispense_denoms = [int(item.get("value", 0)) for item in quote.items]
        quote.transaction_id = transaction_id

        await session.commit()
        await self._reset_inactivity_timer()
        await self._broadcast_converter_snapshot(transaction_id)
        return await self.get_transaction_state(transaction_id)

    async def request_claim(self, transaction_id: str) -> dict:
        """Customer requests termination and a cash claim."""
        if not self._active_tx or self._active_tx.transaction_id != transaction_id:
            existing = await self.get_transaction_state(transaction_id)
            if existing["state"] in {"CLAIM_REQUIRED", "CANCELLED"}:
                return existing
            raise TransactionError(transaction_id, "Transaction is not active")
        if self._confirm_lock.locked() or self._intake_lock.locked():
            raise TransactionError(transaction_id, "Cash handling is in progress; wait for its confirmed result")
        async with self._confirm_lock:
            return await self._request_claim_once(transaction_id)

    async def _request_claim_once(self, transaction_id: str) -> dict:
        tx = self._require_active_transaction()
        if tx.transaction_id != transaction_id:
            raise TransactionError(transaction_id, "Transaction is not active")

        session = self._active_session
        db_record = await self._get_db_record(session, transaction_id)
        if not db_record:
            raise TransactionError(transaction_id, "Transaction record not found")

        if tx.state not in {TransactionState.WAITING_FOR_BILL, TransactionState.WAITING_FOR_CONFIRMATION}:
            raise TransactionError(transaction_id, "Cash handling is still in progress")
        if db_record.type == "coin-to-bill":
            await self._drain_and_reconcile_coin_session(transaction_id)
            db_record = await self._get_db_record(session, transaction_id)
        else:
            await self._set_coin_acceptor_enabled(False)

        claim_amount = max(0, db_record.inserted_amount - db_record.dispensed_amount)
        meta = dict(db_record.converter_metadata or {})
        meta["revision"] = meta.get("revision", 1) + 1

        if claim_amount == 0:
            meta["acceptance_phase"] = "CLOSED"
            meta["termination_reason"] = "USER_CANCELLED"
            db_record.converter_metadata = meta
            await session.commit()
            await tx.cancel()
        else:
            meta["acceptance_phase"] = "CLOSED"
            meta["termination_reason"] = "CUSTOMER_CLAIM_REQUESTED"
            db_record.converter_metadata = meta
            if self._claim_service:
                claim_kind = "OUTPUT_SHORTFALL" if db_record.dispensed_amount > 0 else "INPUT_REFUND"
                claim = await self._claim_service.create(
                    source_kind="STANDARD",
                    transaction_id=db_record.id,
                    claim_kind=claim_kind,
                    amount=claim_amount,
                    currency="PHP",
                    reason_code="CUSTOMER_ABORT",
                    reason_message="Customer requested refund before payout completion",
                    record=db_record,
                    session=session,
                )
                await session.commit()
                await tx.transition_to(
                    TransactionState.CLAIM_REQUIRED,
                    {
                        "claim_ticket_code": claim.claim_ticket_code,
                        "error_code": "CUSTOMER_ABORT",
                        "error_message": "Customer requested refund before payout completion",
                    },
                )
            else:
                await session.commit()
                await tx.transition_to(
                    TransactionState.ERROR,
                    {
                        "error_code": "CUSTOMER_ABORT",
                        "error_message": "Customer requested refund before payout completion",
                    },
                )

        state = await self.get_transaction_state(transaction_id)
        await self._cleanup_active()
        return state

    async def cancel_transaction(self) -> dict:
        async with self._intake_lock:
            async with self._confirm_lock:
                return await self._cancel_transaction_once()

    async def _cancel_transaction_once(self) -> dict:
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

        if record and record.type == "coin-to-bill":
            await self._drain_and_reconcile_coin_session(tx.transaction_id)
            record = await self._get_db_record(self._active_session, tx.transaction_id)
            if record.inserted_amount > 0:
                return await self._request_claim_once(tx.transaction_id)

        await tx.cancel()
        state = await self.get_transaction_state(tx.transaction_id)

        # Clean up active transaction
        await self._cleanup_active()

        return state

    async def _reset_inactivity_timer(self) -> None:
        """Reset monotonic activity tracker and update warning/expiry deadlines."""
        import time as _py_time
        self._last_activity_mono = _py_time.monotonic()
        self._warning_active = False
        if not self._active_tx or not self._active_session:
            return

        self._active_tx.reset_timeout()

        try:
            record = await self._get_db_record(self._active_session, self._active_tx.transaction_id)
            if record and record.state in {
                TransactionState.WAITING_FOR_BILL.value,
                TransactionState.WAITING_FOR_CONFIRMATION.value,
            }:
                meta = dict(record.converter_metadata or {})
                now_utc = datetime.now(timezone.utc)
                warn_sec = getattr(self._settings, "inactivity_warning_seconds", 60.0)
                time_sec = getattr(self._settings, "inactivity_timeout_seconds", 90.0)
                meta["revision"] = meta.get("revision", 0) + 1
                meta["warning_at"] = (now_utc + timedelta(seconds=warn_sec)).isoformat()
                meta["expires_at"] = (now_utc + timedelta(seconds=time_sec)).isoformat()
                record.converter_metadata = meta
                await self._active_session.commit()
                await self._broadcast_converter_snapshot(record.id)
        except Exception as e:
            logger.error(f"Error resetting inactivity timer in DB: {e}")

    async def _handle_inactivity_warning(self, expected_state: TransactionState) -> None:
        """Handle 60s inactivity warning."""
        if not self._active_tx or not self._active_session:
            return
        self._warning_active = True
        logger.warning(f"Inactivity warning fired in state {expected_state.value}")
        await self._ws.broadcast(WSEvent(
            type=WSEventType.TRANSACTION_STATE_CHANGED,
            payload={
                "warning": "INACTIVITY",
                "transaction_id": self._active_tx.transaction_id,
                "seconds_remaining": 30,
            },
        ))
        await self._broadcast_converter_snapshot(self._active_tx.transaction_id)

    async def record_activity(self, transaction_id: str) -> dict:
        """Record user UI activity (e.g. touch) to reset the inactivity timer."""
        if not self.has_active_transaction:
            raise TransactionError(transaction_id, "No active transaction")
        if self._active_tx.transaction_id != transaction_id:
            raise TransactionError(transaction_id, "Transaction ID mismatch")
        if self._active_tx.state not in {TransactionState.WAITING_FOR_BILL, TransactionState.WAITING_FOR_CONFIRMATION} or self._has_accounting_fault:
            raise TransactionError(transaction_id, "Activity cannot extend hardware or reconciliation deadlines")
        await self._reset_inactivity_timer()
        return await self.get_transaction_state(transaction_id)

    async def _handle_timeout(self, expected_state: TransactionState) -> None:
        if expected_state in {TransactionState.AUTHENTICATING, TransactionState.SORTING}:
            await self._handle_timeout_once(expected_state)
            return
        async with self._intake_lock:
            async with self._confirm_lock:
                await self._handle_timeout_once(expected_state)

    async def _handle_timeout_once(self, expected_state: TransactionState) -> None:
        if not self._active_tx or self._active_tx.state != expected_state:
            return
        if self._has_accounting_fault:
            self._termination_requested = True
            return  # Retained-cash retry must establish the obligation before cleanup.
        tx = self._require_active_transaction()
        if expected_state in {TransactionState.AUTHENTICATING, TransactionState.SORTING}:
            await self._bill_acceptor.stop_all()
            self._has_accounting_fault = True
            return
        record = await self._get_db_record(self._active_session, tx.transaction_id)
        if record and record.type == "coin-to-bill":
            await self._drain_and_reconcile_coin_session(tx.transaction_id)
            record = await self._get_db_record(self._active_session, tx.transaction_id)

        accepted_cash = record.inserted_amount if record else 0
        confirmed_cash = record.dispensed_amount if record else 0
        refund_amount = max(0, accepted_cash - confirmed_cash)

        if refund_amount > 0 and self._claim_service:
            claim_kind = "OUTPUT_SHORTFALL" if confirmed_cash > 0 else "INPUT_REFUND"
            claim = await self._claim_service.create(
                source_kind="STANDARD",
                transaction_id=record.id,
                claim_kind=claim_kind,
                amount=refund_amount,
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

    async def handle_tamper(self, sensor: str) -> None:
        async with self._intake_lock:
            async with self._confirm_lock:
                if not self.has_active_transaction:
                    return
                await self._handle_tamper_once(sensor)

    async def _handle_tamper_once(self, sensor: str) -> None:
        """Handle security tamper event during active transaction."""
        if not self.has_active_transaction:
            return
        tx = self._active_tx
        if not tx:
            return
        record = None
        if self._active_session:
            record = await self._get_db_record(self._active_session, tx.transaction_id)
        if record and record.type == "coin-to-bill":
            try:
                await self._drain_and_reconcile_coin_session(tx.transaction_id)
            except Exception as e:
                logger.error(f"Failed draining coin session on tamper: {e}")
            if self._active_tx is not tx:
                return
            record = await self._get_db_record(self._active_session, tx.transaction_id)
        if record and record.inserted_amount > 0 and self._claim_service:
            claim = await self._claim_service.create(
                source_kind="STANDARD",
                transaction_id=record.id,
                claim_kind="INPUT_REFUND",
                amount=max(0, record.inserted_amount - record.dispensed_amount),
                currency="PHP",
                reason_code="TAMPER_DETECTED",
                reason_message=f"Tamper detected ({sensor})",
                record=record,
                session=self._active_session,
            )
            await tx.transition_to(
                TransactionState.CLAIM_REQUIRED,
                {
                    "claim_ticket_code": claim.claim_ticket_code,
                    "error_code": "TAMPER_DETECTED",
                    "error_message": f"Tamper detected ({sensor})",
                },
            )
        else:
            await tx.transition_to(
                TransactionState.ERROR,
                {
                    "error_code": "TAMPER_DETECTED",
                    "error_message": f"Tamper detected ({sensor})",
                },
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

            meta = dict(db_record.converter_metadata or {})
            approved_quote_payload = None
            pending_quote_payload = None

            approved_quote_id = meta.get("approved_quote_id")
            if approved_quote_id:
                aq = (
                    await session.execute(
                        select(ConverterQuote).where(ConverterQuote.id == approved_quote_id)
                    )
                ).scalar_one_or_none()
                if aq:
                    approved_quote_payload = ConverterQuotePayload(
                        id=aq.id,
                        transaction_id=aq.transaction_id,
                        service_type=aq.service_type,
                        input_amount=aq.input_amount,
                        fee=aq.fee,
                        total_due=aq.total_due,
                        payout_amount=aq.payout_amount,
                        items=aq.items or [],
                        requested_counts=aq.requested_counts,
                        is_substitution=aq.is_substitution,
                        substitution_notice=aq.substitution_notice,
                        created_at=aq.created_at.isoformat() if aq.created_at else "",
                        expires_at=aq.expires_at.isoformat() if aq.expires_at else "",
                    ).model_dump()

            pending_quote_id = meta.get("pending_quote_id")
            if pending_quote_id:
                pq = (
                    await session.execute(
                        select(ConverterQuote).where(ConverterQuote.id == pending_quote_id)
                    )
                ).scalar_one_or_none()
                if pq:
                    pending_quote_payload = ConverterQuotePayload(
                        id=pq.id,
                        transaction_id=pq.transaction_id,
                        service_type=pq.service_type,
                        input_amount=pq.input_amount,
                        fee=pq.fee,
                        total_due=pq.total_due,
                        payout_amount=pq.payout_amount,
                        items=pq.items or [],
                        requested_counts=pq.requested_counts,
                        is_substitution=pq.is_substitution,
                        substitution_notice=pq.substitution_notice,
                        created_at=pq.created_at.isoformat() if pq.created_at else "",
                        expires_at=pq.expires_at.isoformat() if pq.expires_at else "",
                    ).model_dump()

            claim_payload = None
            if db_record.claim_ticket_code:
                claim_rec = (
                    await session.execute(
                        select(ClaimRecord).where(
                            ClaimRecord.claim_ticket_code == db_record.claim_ticket_code
                        )
                    )
                ).scalar_one_or_none()
                if claim_rec:
                    claim_payload = ConverterClaimSnapshot(
                        claim_ticket_code=claim_rec.claim_ticket_code,
                        amount=claim_rec.amount,
                        currency=claim_rec.currency,
                        reason_code=claim_rec.reason_code,
                        reason_message=claim_rec.reason_message,
                        status=claim_rec.status,
                        is_provisional=(claim_rec.status == "PROVISIONAL"),
                        ambiguous_amount=claim_rec.ambiguous_amount,
                    ).model_dump()
                else:
                    claim_payload = {
                        "claim_ticket_code": db_record.claim_ticket_code,
                        "amount": db_record.inserted_amount,
                        "currency": "PHP",
                        "reason_code": db_record.error_code or "CLAIM",
                        "reason_message": db_record.error_message,
                        "status": "OPEN",
                        "is_provisional": False,
                        "ambiguous_amount": 0,
                    }

            acceptance_phase = meta.get("acceptance_phase", "OPEN")
            if db_record.state in {"COMPLETE", "ERROR", "CLAIM_REQUIRED", "CANCELLED", "DISPENSING"}:
                acceptance_phase = "CLOSED"
            elif pending_quote_payload is not None:
                acceptance_phase = "CLOSED"
            elif db_record.inserted_amount >= db_record.total_due and db_record.total_due > 0:
                acceptance_phase = "CLOSING" if db_record.type == "coin-to-bill" and acceptance_phase != "CLOSED" else "CLOSED"

            is_active = (
                self._active_tx is not None
                and self._active_tx.transaction_id == db_record.id
            )
            can_continue = bool(
                is_active
                and not self._has_accounting_fault
                and db_record.state in {TransactionState.WAITING_FOR_BILL.value}
                and pending_quote_payload is None
                and db_record.inserted_amount < db_record.total_due
            )
            can_confirm = bool(
                is_active
                and not self._has_accounting_fault
                and db_record.state in {TransactionState.WAITING_FOR_CONFIRMATION.value}
                and pending_quote_payload is None
                and db_record.inserted_amount >= db_record.total_due
            )
            can_request_claim = bool(
                is_active
                and db_record.inserted_amount > 0
                and db_record.state in {TransactionState.WAITING_FOR_BILL.value, TransactionState.WAITING_FOR_CONFIRMATION.value}
                and not self._has_accounting_fault
                and db_record.state not in {
                    TransactionState.COMPLETE.value,
                    TransactionState.ERROR.value,
                    TransactionState.CLAIM_REQUIRED.value,
                    TransactionState.CANCELLED.value,
                    TransactionState.DISPENSING.value,
                }
            )

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
                "revision": meta.get("revision", 1),
                "approved_quote": approved_quote_payload,
                "pending_quote": pending_quote_payload,
                "acceptance_phase": acceptance_phase,
                "accounting_fault": self._has_accounting_fault,
                "warning_at": meta.get("warning_at"),
                "expires_at": meta.get("expires_at"),
                "server_time": datetime.now(timezone.utc).isoformat(),
                "claim": claim_payload,
                "can_continue": can_continue,
                "can_confirm": can_confirm,
                "can_request_claim": can_request_claim,
            }

        return result

    async def _broadcast_converter_snapshot(self, transaction_id: str) -> None:
        try:
            state = await self.get_transaction_state(transaction_id)
            event = WSEvent(
                type=WSEventType.CONVERTER_SNAPSHOT,
                payload=state,
            )
            await self._ws.broadcast(event)
        except Exception as exc:
            logger.error("Failed to broadcast converter snapshot: %s", exc)



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
                # Reconcile any uncredited intake operations
                uncredited_intakes = (
                    await session.execute(
                        select(ConverterIntakeOperation).where(
                            ConverterIntakeOperation.transaction_id == record.id,
                            ConverterIntakeOperation.transaction_credited == False,
                        )
                    )
                ).scalars().all()
                for op in uncredited_intakes:
                    op.state = "UNCERTAIN"
                    self._has_accounting_fault = True
                ambiguity = sum(op.value for op in uncredited_intakes)
                if self._claim_service and (record.inserted_amount > 0 or uncredited_intakes):
                    dispensing = record.state == TransactionState.DISPENSING.value
                    await self._claim_service.create(
                        source_kind="STANDARD",
                        transaction_id=record.id,
                        claim_kind="OUTPUT_SHORTFALL" if dispensing else "INPUT_REFUND",
                        amount=max(0, record.inserted_amount - record.dispensed_amount) + ambiguity,
                        currency="PHP",
                        reason_code="CRASH_RECOVERY",
                        reason_message="Recovered interrupted transaction during startup",
                        provisional=dispensing or bool(uncredited_intakes),
                        ambiguous_amount=ambiguity,
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
            ).execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def _cleanup_active(self) -> None:
        """Clean up the active transaction and session."""
        try:
            await self._set_coin_acceptor_enabled(False)
            if self._active_tx:
                self._active_tx._cancel_timeout()
                await self._broadcast_converter_snapshot(self._active_tx.transaction_id)
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
