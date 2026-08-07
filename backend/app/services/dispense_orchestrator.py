"""Dispense orchestrator for coordinating bill and coin dispensing.

Handles inventory reservation, sequential dispensing through hardware
controllers, progress broadcasting, and partial dispense recovery.
"""

import asyncio
import logging
import secrets
import string
from typing import Dict, List, Optional

from app.core.config import get_settings

from pydantic import BaseModel

from app.api.ws import ConnectionManager
from app.core.errors import HardwareError
from app.drivers.bill_controller import BillController
from app.drivers.coin_security_controller import CoinSecurityController
from app.models.events import WSEvent, WSEventType
from app.services.change_calculator import DispensePlan, DispensePlanItem
from app.services.machine_status import MachineStatus
from app.services.inventory_service import InventoryService

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
    ):
        self._bill = bill_controller
        self._coin = coin_controller
        self._status = machine_status
        self._ws = ws_manager
        self._inventory = inventory_service

    async def execute_dispense(
        self, plan: DispensePlan, reference_id: str | None = None
    ) -> DispenseResult:
        """Execute the full dispense plan.

        Args:
            plan: DispensePlan with bill and coin items to dispense.

        Returns:
            DispenseResult with actual dispensed amounts.
        """
        dispensed_bills: Dict[str, int] = {}
        dispensed_coins: Dict[str, int] = {}
        total_dispensed = 0
        error_msg = None
        reserved = False

        total_items = len(plan.bill_items) + len(plan.coin_items)
        completed_items = 0

        logger.info(
            "Dispense started reference_id=%s total_amount=%s items=%s",
            reference_id,
            plan.total_amount,
            [item.model_dump() for item in plan.items],
        )

        try:
            # Phase 1: Reserve inventory
            await self._reserve_inventory(plan, reference_id)
            reserved = True

            # Give UI time to transition to "Dispensing" screen and display initial status
            settings = get_settings()
            ui_delay = getattr(settings, "dispense_ui_delay", 1.0)
            if ui_delay > 0:
                await asyncio.sleep(ui_delay)

            # Phase 2: Dispense bills
            for item in plan.bill_items:
                try:
                    actual, hardware_error = await self._dispense_bill_denom(
                        item, reference_id
                    )
                    dispensed_bills[item.denom] = actual
                    total_dispensed += actual * item.value
                    completed_items += 1
                except Exception as e:
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
                    try:
                        actual, hardware_error = await self._dispense_coin_denom(
                            item, reference_id
                        )
                        dispensed_coins[item.denom] = actual
                        total_dispensed += actual * item.value
                        completed_items += 1
                    except Exception as e:
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
                )
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
        self, item: DispensePlanItem, reference_id: str | None
    ) -> tuple[int, str | None]:
        """Dispense one bill denomination and retain any controller error."""
        from app.core.constants import BillDenom

        try:
            denom = BillDenom(item.denom)
            response = await self._bill.dispense(denom, item.count)
            logger.info(
                "Bill dispense result reference_id=%s denom=%s requested=%s actual=%s",
                reference_id,
                item.denom,
                item.count,
                response.dispensed,
            )
            return response.dispensed, None
        except HardwareError as e:
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
        self, item: DispensePlanItem, reference_id: str | None
    ) -> tuple[int, str | None]:
        """Dispense one coin denomination and retain any controller error."""
        try:
            # Extract integer value from denom string (e.g., "PHP_5" -> 5)
            denom_value = int(item.denom.split("_")[1])
            response = await self._coin.coin_dispense(denom_value, item.count)
            logger.info(
                "Coin dispense result reference_id=%s denom=%s requested=%s actual=%s",
                reference_id,
                item.denom,
                item.count,
                response.dispensed,
            )
            return response.dispensed, None
        except HardwareError as e:
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
    ) -> None:
        """Restore inventory for items that were reserved but not dispensed."""
        if self._inventory is not None:
            quantities = {}
            for item in plan.bill_items:
                not_dispensed = item.count - actual_bills.get(item.denom, 0)
                if not_dispensed > 0:
                    quantities[("BILL_DISPENSER", item.denom)] = not_dispensed
            for item in plan.coin_items:
                not_dispensed = item.count - actual_coins.get(item.denom, 0)
                if not_dispensed > 0:
                    quantities[("COIN_DISPENSER", item.denom)] = not_dispensed
            if quantities:
                await self._inventory.restore(
                    quantities, reference_id=reference_id
                )
            return
        # For bills: reserved full count, dispensed actual. Restore difference.
        for item in plan.bill_items:
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
