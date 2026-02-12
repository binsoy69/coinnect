"""Dispense orchestrator for coordinating bill and coin dispensing.

Handles inventory reservation, sequential dispensing through hardware
controllers, progress broadcasting, and partial dispense recovery.
"""

import logging
import secrets
import string
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.api.ws import ConnectionManager
from app.core.errors import HardwareError
from app.drivers.bill_controller import BillController
from app.drivers.coin_security_controller import CoinSecurityController
from app.models.events import WSEvent, WSEventType
from app.services.change_calculator import DispensePlan, DispensePlanItem
from app.services.machine_status import MachineStatus

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
    ):
        self._bill = bill_controller
        self._coin = coin_controller
        self._status = machine_status
        self._ws = ws_manager

    async def execute_dispense(self, plan: DispensePlan) -> DispenseResult:
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

        total_items = len(plan.bill_items) + len(plan.coin_items)
        completed_items = 0

        try:
            # Phase 1: Reserve inventory
            self._reserve_inventory(plan)

            # Phase 2: Dispense bills
            for item in plan.bill_items:
                actual = await self._dispense_bill_denom(item)
                dispensed_bills[item.denom] = actual
                total_dispensed += actual * item.value
                completed_items += 1

                await self._broadcast_progress(
                    completed_items, total_items, dispensed_bills, dispensed_coins, total_dispensed
                )

                if actual < item.count:
                    # Partial dispense - hardware error occurred
                    error_msg = f"Partial bill dispense: {item.denom} ({actual}/{item.count})"
                    logger.error(error_msg)
                    break

            # Phase 3: Dispense coins (only if bills succeeded)
            if error_msg is None:
                for item in plan.coin_items:
                    actual = await self._dispense_coin_denom(item)
                    dispensed_coins[item.denom] = actual
                    total_dispensed += actual * item.value
                    completed_items += 1

                    await self._broadcast_progress(
                        completed_items, total_items, dispensed_bills, dispensed_coins, total_dispensed
                    )

                    if actual < item.count:
                        error_msg = f"Partial coin dispense: {item.denom} ({actual}/{item.count})"
                        logger.error(error_msg)
                        break

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Dispense error: {e}", exc_info=True)

        # Phase 4: Reconcile
        shortfall = plan.total_amount - total_dispensed
        success = shortfall == 0 and error_msg is None

        # Restore unreserved inventory for items not dispensed
        self._reconcile_inventory(plan, dispensed_bills, dispensed_coins)

        # Generate claim ticket if partial
        claim_ticket = None
        if shortfall > 0:
            claim_ticket = _generate_claim_ticket()
            logger.warning(
                f"Partial dispense: {total_dispensed}/{plan.total_amount}, "
                f"shortfall={shortfall}, claim_ticket={claim_ticket}"
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
            },
        )
        await self._ws.broadcast(event)

        return result

    async def _dispense_bill_denom(self, item: DispensePlanItem) -> int:
        """Dispense bills for a single denomination. Returns actual count dispensed."""
        from app.core.constants import BillDenom

        try:
            denom = BillDenom(item.denom)
            response = await self._bill.dispense(denom, item.count)
            return response.dispensed
        except HardwareError as e:
            # Partial dispense - some bills may have been dispensed
            actual = e.dispensed or 0
            logger.error(
                f"Bill dispense error for {item.denom}: {e.code} "
                f"(dispensed {actual}/{item.count})"
            )
            return actual

    async def _dispense_coin_denom(self, item: DispensePlanItem) -> int:
        """Dispense coins for a single denomination. Returns actual count dispensed."""
        try:
            # Extract integer value from denom string (e.g., "PHP_5" -> 5)
            denom_value = int(item.denom.split("_")[1])
            response = await self._coin.coin_dispense(denom_value, item.count)
            return response.dispensed
        except HardwareError as e:
            actual = e.dispensed or 0
            logger.error(
                f"Coin dispense error for {item.denom}: {e.code} "
                f"(dispensed {actual}/{item.count})"
            )
            return actual

    def _reserve_inventory(self, plan: DispensePlan) -> None:
        """Decrement inventory for all planned items before dispensing."""
        for item in plan.bill_items:
            self._status.decrement_bill_dispenser(item.denom, item.count)
        for item in plan.coin_items:
            self._status.decrement_coin(item.denom, item.count)

    def _reconcile_inventory(
        self,
        plan: DispensePlan,
        actual_bills: Dict[str, int],
        actual_coins: Dict[str, int],
    ) -> None:
        """Restore inventory for items that were reserved but not dispensed."""
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
            },
        )
        await self._ws.broadcast(event)
