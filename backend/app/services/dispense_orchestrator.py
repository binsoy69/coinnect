"""Dispense orchestrator for coordinating bill and coin dispensing.

Handles inventory reservation, sequential dispensing through hardware
controllers, progress broadcasting, and partial dispense recovery.
"""

import asyncio
import logging
import secrets
import string
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from app.core.config import get_settings

from pydantic import BaseModel

from app.api.ws import ConnectionManager
from app.core.errors import HardwareError, SerialError, TimeoutError as CommandTimeoutError
from sqlalchemy import or_, select
from app.drivers.bill_controller import BillController
from app.drivers.coin_security_controller import CoinSecurityController
from app.models.events import WSEvent, WSEventType
from app.services.change_calculator import DispensePlan, DispensePlanItem
from app.services.machine_status import MachineStatus
from app.services.inventory_service import InventoryService
from app.models.db_models import (
    EWalletTransactionRecord,
    ClaimRecord,
    DispenseExecution,
    DispenseExecutionState,
    PhysicalOperation,
    PhysicalOperationState,
    TransactionRecord,
)

logger = logging.getLogger(__name__)

class DispenseResult(BaseModel):
    """Result of a dispense operation."""

    success: bool = False
    dispensed_bills: Dict[str, int] = {}
    dispensed_coins: Dict[str, int] = {}
    total_dispensed: int = 0
    shortfall: int = 0
    error: Optional[str] = None
    claim_ticket_code: Optional[str] = None
    ambiguous_amount: int = 0

def _generate_claim_ticket() -> str:
    """Generate a unique 8-character alphanumeric claim ticket code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(8))

class DispenseOrchestrator:
    """Coordinates bill and coin dispensing with inventory management.

    Dispense order: bills first (one denomination at a time), then coins.
    On hardware error (JAM), stops and records partial dispense.
    """

    def __init__(
        self,
        bill_controller: BillController,
        coin_controller: CoinSecurityController,
        machine_status: MachineStatus,
        ws_manager: ConnectionManager,
        inventory_service: InventoryService | None = None,
        db_session_factory=None,
    ):
        self._bill = bill_controller
        self._coin = coin_controller
        self._status = machine_status
        self._ws = ws_manager
        self._inventory = inventory_service
        self._db_factory = db_session_factory

    async def execute_dispense(
        self,
        plan: DispensePlan,
        reference_id: str | None = None,
        source_kind: str = "STANDARD",
    ) -> DispenseResult:
        """Execute the full dispense plan.

        Args:
            plan: DispensePlan with bill and coin items to dispense.

        Returns:
            DispenseResult with actual dispensed amounts.
        """
        if self._status.should_block_dispensing_for_inventory_reconciliation():
            error = "Inventory reconciliation is required; dispensing is disabled"
            logger.error(
                "Dispense blocked reference_id=%s: %s", reference_id, error
            )
            return DispenseResult(
                success=False,
                shortfall=plan.total_amount,
                error=error,
                claim_ticket_code=_generate_claim_ticket(),
            )

        dispensed_bills: Dict[str, int] = {}
        dispensed_coins: Dict[str, int] = {}
        total_dispensed = 0
        error_msg = None
        reserved = False
        execution_id = None
        operations: dict[tuple[str, str], str] = {}
        ambiguous = False
        ambiguous_keys: set[tuple[str, str]] = set()

        total_items = len(plan.bill_items) + len(plan.coin_items)
        completed_items = 0

        logger.info(
            "Dispense started reference_id=%s total_amount=%s items=%s",
            reference_id,
            plan.total_amount,
            [item.model_dump() for item in plan.items],
        )

        try:
            execution_id, operations, replay, atomically_reserved = await self._create_execution(
                plan, reference_id, source_kind
            )
            if replay is not None:
                return replay
            # Phase 1: Reserve inventory
            if not atomically_reserved:
                await self._reserve_inventory(plan, reference_id)
            reserved = True

            # Give UI time to transition to "Dispensing" screen and display initial status
            settings = get_settings()
            ui_delay = getattr(settings, "dispense_ui_delay", 1.0)
            if ui_delay > 0:
                await asyncio.sleep(ui_delay)

            # Phase 2: Dispense bills
            for item in plan.bill_items:
                if self._status.snapshot().security.tamper_active:
                    error_msg = "LOCKED_OUT"
                    break
                operation_id = operations.get(("BILL", item.denom))
                try:
                    await self._mark_operation_started(operation_id, execution_id)
                    actual, hardware_error = await self._dispense_bill_denom(
                        item, reference_id, operation_id
                    )
                    await self._mark_operation_result(
                        operation_id, execution_id, actual, hardware_error
                    )
                    dispensed_bills[item.denom] = actual
                    total_dispensed += actual * item.value
                    completed_items += 1
                except Exception as e:
                    if isinstance(e, CommandTimeoutError):
                        recovered = await self._recover_timed_out_operation(
                            self._bill, operation_id, execution_id
                        )
                        if recovered is not None:
                            actual, hardware_error = recovered
                            dispensed_bills[item.denom] = actual
                            total_dispensed += actual * item.value
                            completed_items += 1
                            if hardware_error:
                                error_msg = hardware_error
                                break
                            continue
                    ambiguous = True
                    ambiguous_keys.add(("BILL", item.denom))
                    await self._mark_operation_ambiguous(operation_id, execution_id, str(e), getattr(e, "dispensed", 0) or 0)
                    actual = getattr(e, "dispensed", 0) or 0
                    dispensed_bills[item.denom] = actual
                    total_dispensed += actual * item.value
                    completed_items += 1
                    raise

                await self._broadcast_progress(
                    completed_items,
                    total_items,
                    dispensed_bills,
                    dispensed_coins,
                    total_dispensed,
                    reference_id,
                )

                if actual < item.count:
                    cause = f" ({hardware_error})" if hardware_error else ""
                    error_msg = (
                        f"Partial bill dispense: {item.denom} "
                        f"({actual}/{item.count}){cause}"
                    )
                    logger.error(
                        "%s reference_id=%s", error_msg, reference_id
                    )
                    break

            # Phase 3: Dispense coins (only if bills succeeded)
            if error_msg is None:
                for item in plan.coin_items:
                    if self._status.snapshot().security.tamper_active:
                        error_msg = "LOCKED_OUT"
                        break
                    operation_id = operations.get(("COIN", item.denom))
                    try:
                        await self._mark_operation_started(operation_id, execution_id)
                        actual, hardware_error = await self._dispense_coin_denom(
                            item, reference_id, operation_id
                        )
                        await self._mark_operation_result(
                            operation_id, execution_id, actual, hardware_error
                        )
                        dispensed_coins[item.denom] = actual
                        total_dispensed += actual * item.value
                        completed_items += 1
                    except Exception as e:
                        if isinstance(e, CommandTimeoutError):
                            recovered = await self._recover_timed_out_operation(
                                self._coin, operation_id, execution_id
                            )
                            if recovered is not None:
                                actual, hardware_error = recovered
                                dispensed_coins[item.denom] = actual
                                total_dispensed += actual * item.value
                                completed_items += 1
                                if hardware_error:
                                    error_msg = hardware_error
                                    break
                                continue
                        ambiguous = True
                        ambiguous_keys.add(("COIN", item.denom))
                        await self._mark_operation_ambiguous(operation_id, execution_id, str(e), getattr(e, "dispensed", 0) or 0)
                        actual = getattr(e, "dispensed", 0) or 0
                        dispensed_coins[item.denom] = actual
                        total_dispensed += actual * item.value
                        completed_items += 1
                        raise

                    await self._broadcast_progress(
                        completed_items,
                        total_items,
                        dispensed_bills,
                        dispensed_coins,
                        total_dispensed,
                        reference_id,
                    )

                    if actual < item.count:
                        cause = f" ({hardware_error})" if hardware_error else ""
                        error_msg = (
                            f"Partial coin dispense: {item.denom} "
                            f"({actual}/{item.count}){cause}"
                        )
                        logger.error(
                            "%s reference_id=%s", error_msg, reference_id
                        )
                        break

        except Exception as e:
            error_msg = str(e)
            logger.error(
                "Dispense error reference_id=%s: %s",
                reference_id,
                e,
                exc_info=True,
            )


        # Phase 4: Reconcile
        shortfall = plan.total_amount - total_dispensed
        success = shortfall == 0 and error_msg is None

        # Restore unreserved inventory for items not dispensed
        if reserved:
            try:
                await self._reconcile_inventory(
                    plan,
                    dispensed_bills,
                    dispensed_coins,
                    reference_id,
                    ambiguous_keys,
                    execution_id,
                )
                if self._inventory is None or self._db_factory is None:
                    await self._mark_inventory_reconciled(execution_id, ambiguous_keys)
            except Exception as exc:
                self._status.set_inventory_consistent(False)
                error_msg = error_msg or f"Inventory reconciliation failed: {exc}"
                logger.error(error_msg, exc_info=True)

        # Generate claim ticket if partial
        claim_ticket = None
        if shortfall > 0:
            claim_ticket = _generate_claim_ticket()
            logger.warning(
                "Partial dispense reference_id=%s dispensed=%s planned=%s "
                "shortfall=%s claim_ticket=%s error=%s",
                reference_id,
                total_dispensed,
                plan.total_amount,
                shortfall,
                claim_ticket,
                error_msg,
            )

        result = DispenseResult(
            success=success,
            dispensed_bills=dispensed_bills,
            dispensed_coins=dispensed_coins,
            total_dispensed=total_dispensed,
            shortfall=shortfall,
            error=error_msg,
            claim_ticket_code=claim_ticket,
            ambiguous_amount=sum(
                max(0, item.count - (dispensed_bills if item.denom_type == "bill" else dispensed_coins).get(item.denom, 0)) * item.value
                for item in plan.items
                if ("BILL" if item.denom_type == "bill" else "COIN", item.denom) in ambiguous_keys
            ),
        )
        await self._finish_execution(
            execution_id,
            (
                DispenseExecutionState.COMPLETE.value
                if success
                else DispenseExecutionState.AMBIGUOUS.value
                if ambiguous
                else DispenseExecutionState.FAILED.value
            ),
            total_dispensed,
        )

        # Broadcast completion
        event_type = WSEventType.DISPENSE_COMPLETE
        event = WSEvent(
            type=event_type,
            payload={
                "success": success,
                "total_dispensed": total_dispensed,
                "shortfall": shortfall,
                "dispensed_bills": dispensed_bills,
                "dispensed_coins": dispensed_coins,
                "claim_ticket_code": claim_ticket,
                "transaction_id": reference_id,
                "error": error_msg,
            },
        )
        await self._ws.broadcast(event)

        logger.info(
            "Dispense finished reference_id=%s success=%s dispensed=%s "
            "shortfall=%s claim_ticket=%s",
            reference_id,
            success,
            total_dispensed,
            shortfall,
            claim_ticket,
        )
        return result

    async def _dispense_bill_denom(
        self, item: DispensePlanItem, reference_id: str | None, operation_id: str | None = None
    ) -> tuple[int, str | None]:
        """Dispense one bill denomination and retain any controller error."""
        from app.core.constants import BillDenom

        try:
            denom = BillDenom(item.denom)
            response = await self._bill.dispense(denom, item.count, operation_id=operation_id)
            logger.info(
                "Bill dispense result reference_id=%s denom=%s requested=%s actual=%s",
                reference_id,
                item.denom,
                item.count,
                response.dispensed,
            )
            return response.dispensed, None
        except HardwareError as e:
            if e.code in {"AMBIGUOUS", "LOCKED_OUT"}:
                raise
            # Partial dispense - some bills may have been dispensed
            actual = e.dispensed or 0
            logger.error(
                "Bill dispense hardware error reference_id=%s denom=%s "
                "code=%s requested=%s actual=%s message=%s",
                reference_id,
                item.denom,
                e.code,
                item.count,
                actual,
                str(e),
            )
            return actual, f"{e.code}: {e}"

    async def _dispense_coin_denom(
        self, item: DispensePlanItem, reference_id: str | None, operation_id: str | None = None
    ) -> tuple[int, str | None]:
        """Dispense one coin denomination and retain any controller error."""
        try:
            # Extract integer value from denom string (e.g., "PHP_5" -> 5)
            denom_value = int(item.denom.split("_")[1])
            response = await self._coin.coin_dispense(denom_value, item.count, operation_id=operation_id)
            logger.info(
                "Coin dispense result reference_id=%s denom=%s requested=%s actual=%s",
                reference_id,
                item.denom,
                item.count,
                response.dispensed,
            )
            return response.dispensed, None
        except HardwareError as e:
            if e.code in {"AMBIGUOUS", "LOCKED_OUT"}:
                raise
            actual = e.dispensed or 0
            logger.error(
                "Coin dispense hardware error reference_id=%s denom=%s "
                "code=%s requested=%s actual=%s message=%s",
                reference_id,
                item.denom,
                e.code,
                item.count,
                actual,
                str(e),
            )
            return actual, f"{e.code}: {e}"

    async def _reserve_inventory(
        self, plan: DispensePlan, reference_id: str | None
    ) -> None:
        """Decrement inventory for all planned items before dispensing."""
        if self._inventory is not None:
            quantities = {
                ("BILL_DISPENSER", item.denom): item.count
                for item in plan.bill_items
            }
            quantities.update(
                {
                    ("COIN_DISPENSER", item.denom): item.count
                    for item in plan.coin_items
                }
            )
            await self._inventory.reserve(
                quantities, reference_id=reference_id
            )
            return
        for item in plan.bill_items:
            self._status.decrement_bill_dispenser(item.denom, item.count)
        for item in plan.coin_items:
            self._status.decrement_coin(item.denom, item.count)

    async def _reconcile_inventory(
        self,
        plan: DispensePlan,
        actual_bills: Dict[str, int],
        actual_coins: Dict[str, int],
        reference_id: str | None,
        ambiguous_keys: set[tuple[str, str]] | None = None,
        execution_id: str | None = None,
    ) -> None:
        """Restore inventory for items that were reserved but not dispensed."""
        if self._inventory is not None:
            quantities = {}
            for item in plan.bill_items:
                if ("BILL", item.denom) in (ambiguous_keys or set()):
                    continue
                not_dispensed = item.count - actual_bills.get(item.denom, 0)
                if not_dispensed > 0:
                    quantities[("BILL_DISPENSER", item.denom)] = not_dispensed
            for item in plan.coin_items:
                if ("COIN", item.denom) in (ambiguous_keys or set()):
                    continue
                not_dispensed = item.count - actual_coins.get(item.denom, 0)
                if not_dispensed > 0:
                    quantities[("COIN_DISPENSER", item.denom)] = not_dispensed
            if quantities:
                if self._db_factory is not None and execution_id is not None:
                    async with self._db_factory() as session:
                        await self._inventory.restore_in_session(
                            session, quantities, reference_id=reference_id
                        )
                        operations = list((await session.execute(
                            select(PhysicalOperation).where(
                                PhysicalOperation.execution_id == execution_id
                            )
                        )).scalars().all())
                        for operation in operations:
                            if (operation.controller, operation.denomination) not in (ambiguous_keys or set()):
                                operation.inventory_reconciled = True
                        await session.commit()
                    await self._inventory._refresh_runtime()
                else:
                    await self._inventory.restore(
                        quantities, reference_id=reference_id
                    )
            elif self._db_factory is not None and execution_id is not None:
                await self._mark_inventory_reconciled(execution_id, ambiguous_keys or set())
            return
        # For bills: reserved full count, dispensed actual. Restore difference.
        for item in plan.bill_items:
            if ("BILL", item.denom) in (ambiguous_keys or set()):
                continue
            actual = actual_bills.get(item.denom, 0)
            not_dispensed = item.count - actual
            if not_dispensed > 0:
                # Add back to dispenser (increment = negative decrement)
                # Use set_dispenser_counts is too coarse; we need increment
                # Since MachineStatus doesn't have increment_bill_dispenser,
                # we work around by getting current and setting
                snapshot = self._status.snapshot()
                current = snapshot.consumables.bill_dispenser_counts.get(
                    item.denom, 0
                )
                self._status.set_dispenser_counts(
                    {item.denom: current + not_dispensed}
                )

        # For coins: same logic
        for item in plan.coin_items:
            if ("COIN", item.denom) in (ambiguous_keys or set()):
                continue
            actual = actual_coins.get(item.denom, 0)
            not_dispensed = item.count - actual
            if not_dispensed > 0:
                snapshot = self._status.snapshot()
                current = snapshot.consumables.coin_counts.get(item.denom, 0)
                self._status.set_coin_counts(
                    {item.denom: current + not_dispensed}
                )

    async def _broadcast_progress(
        self,
        completed: int,
        total: int,
        bills: Dict[str, int],
        coins: Dict[str, int],
        amount: int,
        reference_id: str | None,
    ) -> None:
        """Broadcast dispense progress via WebSocket."""
        event = WSEvent(
            type=WSEventType.DISPENSE_PROGRESS,
            payload={
                "completed_items": completed,
                "total_items": total,
                "dispensed_bills": bills,
                "dispensed_coins": coins,
                "dispensed_amount": amount,
                "transaction_id": reference_id,
            },
        )
        await self._ws.broadcast(event)

    async def _create_execution(self, plan, reference_id, source_kind):
        if self._db_factory is None or reference_id is None:
            return None, {}, None, False
        async with self._db_factory() as session:
            existing = (
                await session.execute(
                    select(DispenseExecution).where(
                        DispenseExecution.source_kind == source_kind,
                        DispenseExecution.transaction_id == reference_id,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                operations = (
                    await session.execute(
                        select(PhysicalOperation).where(
                            PhysicalOperation.execution_id == existing.id
                        )
                    )
                ).scalars().all()
                if existing.state == DispenseExecutionState.COMPLETE.value:
                    bills = {
                        op.denomination: op.confirmed_count
                        for op in operations if op.controller == "BILL"
                    }
                    coins = {
                        op.denomination: op.confirmed_count
                        for op in operations if op.controller == "COIN"
                    }
                    return existing.id, {}, DispenseResult(
                        success=True,
                        dispensed_bills=bills,
                        dispensed_coins=coins,
                        total_dispensed=existing.confirmed_amount,
                        shortfall=0,
                    ), True
                return existing.id, {}, DispenseResult(
                    success=False,
                    total_dispensed=existing.confirmed_amount,
                    shortfall=max(0, existing.requested_amount - existing.confirmed_amount),
                    error="Dispense execution already exists and requires recovery",
                ), True
            execution_id = str(uuid.uuid4())
            execution = DispenseExecution(
                id=execution_id,
                source_kind=source_kind,
                transaction_id=reference_id,
                state=DispenseExecutionState.PLANNED.value,
                plan={"items": [item.model_dump() for item in plan.items]},
                requested_amount=plan.total_amount,
            )
            session.add(execution)
            operations = {}
            for sequence, item in enumerate(plan.items):
                controller = "BILL" if item.denom_type == "bill" else "COIN"
                operation_id = str(uuid.uuid4())
                session.add(PhysicalOperation(
                    id=operation_id,
                    execution_id=execution_id,
                    transaction_id=reference_id,
                    sequence=sequence,
                    controller=controller,
                    denomination=item.denom,
                    requested_count=item.count,
                    denomination_value=item.value,
                ))
                operations[(controller, item.denom)] = operation_id
            atomically_reserved = self._inventory is not None
            if atomically_reserved:
                quantities = {
                    ("BILL_DISPENSER", item.denom): item.count
                    for item in plan.bill_items
                }
                quantities.update({
                    ("COIN_DISPENSER", item.denom): item.count
                    for item in plan.coin_items
                })
                await self._inventory.reserve_in_session(
                    session, quantities, reference_id=reference_id
                )
            source_model = EWalletTransactionRecord if source_kind == "EWALLET" else TransactionRecord
            source = await session.get(source_model, reference_id)
            if source is not None:
                source.state = "DISPENSING"
            await session.commit()
            if atomically_reserved:
                await self._inventory._refresh_runtime()
            return execution_id, operations, None, atomically_reserved

    async def _mark_operation_started(self, operation_id, execution_id):
        if self._db_factory is None or operation_id is None:
            return
        async with self._db_factory() as session:
            operation = await session.get(PhysicalOperation, operation_id)
            execution = await session.get(DispenseExecution, execution_id)
            if operation.state == PhysicalOperationState.COMPLETED.value:
                return
            operation.state = PhysicalOperationState.STARTED.value
            operation.started_at = datetime.utcnow()
            execution.state = DispenseExecutionState.RUNNING.value
            await session.commit()

    async def _mark_operation_result(self, operation_id, execution_id, actual, error):
        if self._db_factory is None or operation_id is None:
            return
        async with self._db_factory() as session:
            operation = await session.get(PhysicalOperation, operation_id)
            operation.confirmed_count = actual
            operation.inventory_reconciled = actual == operation.requested_count
            operation.completed_at = datetime.utcnow()
            if error:
                operation.state = PhysicalOperationState.FAILED.value
                operation.error_code = str(error).split(":", 1)[0]
                operation.error_message = str(error)
            else:
                operation.state = PhysicalOperationState.COMPLETED.value
            await session.commit()

    async def _mark_inventory_reconciled(self, execution_id, ambiguous_keys):
        if self._db_factory is None or execution_id is None:
            return
        async with self._db_factory() as session:
            operations = list((await session.execute(
                select(PhysicalOperation).where(PhysicalOperation.execution_id == execution_id)
            )).scalars().all())
            for operation in operations:
                if (operation.controller, operation.denomination) not in ambiguous_keys:
                    operation.inventory_reconciled = True
            await session.commit()

    async def _mark_operation_ambiguous(self, operation_id, execution_id, message, confirmed_count=0):
        if self._db_factory is None or operation_id is None:
            return
        async with self._db_factory() as session:
            operation = await session.get(PhysicalOperation, operation_id)
            execution = await session.get(DispenseExecution, execution_id)
            operation.state = PhysicalOperationState.AMBIGUOUS.value
            operation.confirmed_count = min(operation.requested_count, max(0, confirmed_count))
            operation.error_code = "COMMAND_TIMEOUT"
            operation.error_message = message
            execution.state = DispenseExecutionState.AMBIGUOUS.value
            execution.ambiguous_amount += (operation.requested_count - operation.confirmed_count) * operation.denomination_value
            await session.commit()

    async def _recover_timed_out_operation(self, controller, operation_id, execution_id):
        """Resolve a serial timeout without ever replaying the motion command."""
        try:
            status = await controller.operation_status(operation_id)
        except Exception:
            return None
        if status.operation_status == "COMPLETED":
            await self._mark_operation_result(
                operation_id, execution_id, status.dispensed, None
            )
            return status.dispensed, None
        if status.operation_status == "FAILED":
            error = status.code or "CONTROLLER_REPORTED_FAILURE"
            await self._mark_operation_result(
                operation_id, execution_id, status.dispensed, error
            )
            return status.dispensed, error
        return None

    async def recover_started_operations(self, claim_service=None) -> None:
        """Reconcile committed send intents before gateway work resumes."""
        if self._db_factory is None:
            return
        async with self._db_factory() as session:
            operations = list((await session.execute(
                select(PhysicalOperation).where(
                    or_(
                        PhysicalOperation.state.in_({
                            PhysicalOperationState.PLANNED.value,
                            PhysicalOperationState.STARTED.value,
                            PhysicalOperationState.AMBIGUOUS.value,
                        }),
                        PhysicalOperation.inventory_reconciled.is_(False),
                    )
                ).order_by(PhysicalOperation.execution_id, PhysicalOperation.sequence)
            )).scalars().all())

        affected: set[str] = set()
        acknowledgements: list[tuple[object, str]] = []
        restorations: list[tuple[str, str, int, str]] = []
        for operation in operations:
            controller = self._bill if operation.controller == "BILL" else self._coin
            if operation.state == PhysicalOperationState.PLANNED.value:
                reported = "NEVER_SENT"
            elif operation.state in {
                PhysicalOperationState.COMPLETED.value,
                PhysicalOperationState.FAILED.value,
                PhysicalOperationState.RECONCILED.value,
            }:
                reported = "DEFINITIVE"
            else:
                try:
                    reported = await controller.operation_status(operation.id)
                except Exception:
                    reported = None
            async with self._db_factory() as session:
                durable = await session.get(PhysicalOperation, operation.id)
                if reported == "NEVER_SENT":
                    durable.state = PhysicalOperationState.FAILED.value
                    durable.error_code = "NOT_SENT_BEFORE_RESTART"
                    durable.error_message = "Operation was reserved but never sent"
                    durable.completed_at = datetime.utcnow()
                elif reported == "DEFINITIVE":
                    pass
                elif reported and reported.operation_status in {"COMPLETED", "FAILED"}:
                    durable.confirmed_count = reported.dispensed
                    durable.state = (
                        PhysicalOperationState.COMPLETED.value
                        if reported.operation_status == "COMPLETED"
                        else PhysicalOperationState.FAILED.value
                    )
                    durable.error_code = reported.code
                    durable.completed_at = datetime.utcnow()
                else:
                    durable.state = PhysicalOperationState.AMBIGUOUS.value
                    durable.error_code = "STARTUP_RECOVERY_AMBIGUOUS"
                    durable.error_message = (
                        reported.operation_status if reported else "Controller unavailable"
                    )
                    acknowledgements.append((controller, durable.id))
                undispensed = durable.requested_count - durable.confirmed_count
                if (
                    durable.state != PhysicalOperationState.AMBIGUOUS.value
                    and not durable.inventory_reconciled
                ):
                    if undispensed > 0 and self._inventory is not None:
                        location = "BILL_DISPENSER" if durable.controller == "BILL" else "COIN_DISPENSER"
                        await self._inventory.restore_in_session(
                            session,
                            {(location, durable.denomination): undispensed},
                            reference_id=durable.transaction_id,
                        )
                    elif undispensed > 0:
                        restorations.append((durable.controller, durable.denomination, undispensed, durable.transaction_id))
                    durable.inventory_reconciled = True
                affected.add(durable.execution_id)
                await session.commit()

        for controller_name, denomination, count, transaction_id in restorations:
            location = "BILL_DISPENSER" if controller_name == "BILL" else "COIN_DISPENSER"
            if self._inventory is not None:
                await self._inventory.restore(
                    {(location, denomination): count}, reference_id=transaction_id
                )
            elif controller_name == "BILL":
                snapshot = self._status.snapshot()
                current = snapshot.consumables.bill_dispenser_counts.get(denomination, 0)
                self._status.set_dispenser_counts({denomination: current + count})
            else:
                snapshot = self._status.snapshot()
                current = snapshot.consumables.coin_counts.get(denomination, 0)
                self._status.set_coin_counts({denomination: current + count})
        if self._inventory is not None and operations:
            await self._inventory._refresh_runtime()

        for execution_id in affected:
            await self._finalize_recovered_execution(execution_id, claim_service)
        acknowledgement_failures: list[str] = []
        for controller, operation_id in acknowledgements:
            try:
                await controller.acknowledge_operation(operation_id)
            except Exception as exc:
                logger.warning("Operation acknowledgement failed for %s: %s", operation_id, exc)
                acknowledgement_failures.append(f"{operation_id}: {exc}")

        if acknowledgement_failures:
            self._status.set_inventory_consistent(False)
            raise SerialError(
                "Controller recovery acknowledgement failed; the controller and "
                "durable operation state require reconciliation "
                f"({'; '.join(acknowledgement_failures)})"
            )

    async def _finalize_recovered_execution(self, execution_id, claim_service):
        async with self._db_factory() as session:
            execution = await session.get(DispenseExecution, execution_id)
            operations = list((await session.execute(
                select(PhysicalOperation).where(PhysicalOperation.execution_id == execution_id)
            )).scalars().all())
            confirmed = sum(op.confirmed_count * op.denomination_value for op in operations)
            ambiguous_amount = sum(
                op.requested_count * op.denomination_value
                for op in operations if op.state == PhysicalOperationState.AMBIGUOUS.value
            )
            execution.confirmed_amount = confirmed
            execution.ambiguous_amount = ambiguous_amount
            execution.state = (
                DispenseExecutionState.AMBIGUOUS.value
                if ambiguous_amount
                else DispenseExecutionState.COMPLETE.value
                if confirmed == execution.requested_amount
                else DispenseExecutionState.FAILED.value
            )
            execution.completed_at = datetime.utcnow()
            record = (
                await session.get(EWalletTransactionRecord, execution.transaction_id)
                if execution.source_kind == "EWALLET"
                else await session.get(TransactionRecord, execution.transaction_id)
            )
            shortfall = max(0, execution.requested_amount - confirmed)
            if record is not None:
                record.dispensed_amount = confirmed
            existing_claim = (await session.execute(
                select(ClaimRecord).where(
                    ClaimRecord.source_kind == execution.source_kind,
                    ClaimRecord.transaction_id == execution.transaction_id,
                    ClaimRecord.status != "RESOLVED",
                ).limit(1)
            )).scalar_one_or_none()
            if record is not None and shortfall == 0 and existing_claim is not None:
                existing_claim.confirmed_dispensed_amount = confirmed
                existing_claim.ambiguous_amount = 0
                existing_claim.amount = 0
                existing_claim.reason_code = "LATE_PHYSICAL_COMPLETION"
                existing_claim.reason_message = "Controller reported completion after a claim was issued; operator review is required"
                existing_claim.status = "PROVISIONAL"
                record.state = "CLAIM_REQUIRED"
                await session.commit()
            elif record is not None and shortfall == 0:
                record.state = "COMPLETE"
                record.completed_at = datetime.utcnow()
                await session.commit()
            elif claim_service and record is not None:
                currency = getattr(record, "to_currency", None) or "PHP"
                await claim_service.create(
                    source_kind=execution.source_kind,
                    transaction_id=execution.transaction_id,
                    claim_kind="OUTPUT_SHORTFALL",
                    amount=shortfall,
                    currency=currency,
                    reason_code="STARTUP_RECOVERY_AMBIGUOUS",
                    reason_message="A dispense command requires physical reconciliation",
                    confirmed_dispensed_amount=confirmed,
                    ambiguous_amount=ambiguous_amount,
                    provisional=bool(ambiguous_amount),
                    record=record,
                    session=session,
                )
            else:
                await session.commit()

    async def _finish_execution(self, execution_id, state, confirmed_amount):
        if self._db_factory is None or execution_id is None:
            return
        async with self._db_factory() as session:
            execution = await session.get(DispenseExecution, execution_id)
            execution.state = state
            execution.confirmed_amount = confirmed_amount
            execution.completed_at = datetime.utcnow()
            await session.commit()
