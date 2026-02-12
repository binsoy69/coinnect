"""Tests for the dispense orchestrator.

Validates bill/coin dispensing coordination, partial dispense recovery
with claim ticket generation, and progress event broadcasting.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import Settings
from app.core.errors import HardwareError
from app.models.events import WSEventType
from app.services.change_calculator import DispensePlan, DispensePlanItem
from app.services.dispense_orchestrator import DispenseOrchestrator, DispenseResult
from app.services.machine_status import MachineStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def settings():
    return Settings(
        use_mock_serial=True,
        serial_port_bill="MOCK",
        serial_port_coin="MOCK",
    )


@pytest.fixture
def machine_status(settings):
    ms = MachineStatus(settings)
    # Pre-load inventory so reserve/reconcile operations work
    ms.set_dispenser_counts({
        "PHP_20": 50, "PHP_50": 50, "PHP_100": 50,
        "PHP_200": 50, "PHP_500": 50, "PHP_1000": 50,
    })
    ms.set_coin_counts({
        "PHP_1": 200, "PHP_5": 200, "PHP_10": 200, "PHP_20": 200,
    })
    return ms


@pytest.fixture
def bill_controller():
    controller = AsyncMock()
    return controller


@pytest.fixture
def coin_controller():
    controller = AsyncMock()
    return controller


@pytest.fixture
def ws_manager():
    manager = AsyncMock()
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture
def orchestrator(bill_controller, coin_controller, machine_status, ws_manager):
    return DispenseOrchestrator(
        bill_controller=bill_controller,
        coin_controller=coin_controller,
        machine_status=machine_status,
        ws_manager=ws_manager,
    )


# ---------------------------------------------------------------------------
# Helper to build DispensePlan objects
# ---------------------------------------------------------------------------

def _bill_plan(items_dict):
    """Build a DispensePlan with bill items only.

    Args:
        items_dict: dict of denom_str -> (count, per_unit_value)
            e.g. {"PHP_100": (5, 100), "PHP_500": (2, 500)}
    """
    items = []
    total = 0
    for denom, (count, value) in items_dict.items():
        items.append(DispensePlanItem(denom=denom, denom_type="bill", count=count, value=value))
        total += count * value
    return DispensePlan(items=items, total_amount=total, is_exact=True)


def _coin_plan(items_dict):
    """Build a DispensePlan with coin items only."""
    items = []
    total = 0
    for denom, (count, value) in items_dict.items():
        items.append(DispensePlanItem(denom=denom, denom_type="coin", count=count, value=value))
        total += count * value
    return DispensePlan(items=items, total_amount=total, is_exact=True)


def _mixed_plan(bill_dict, coin_dict):
    """Build a DispensePlan with both bill and coin items."""
    items = []
    total = 0
    for denom, (count, value) in bill_dict.items():
        items.append(DispensePlanItem(denom=denom, denom_type="bill", count=count, value=value))
        total += count * value
    for denom, (count, value) in coin_dict.items():
        items.append(DispensePlanItem(denom=denom, denom_type="coin", count=count, value=value))
        total += count * value
    return DispensePlan(items=items, total_amount=total, is_exact=True)


# ---------------------------------------------------------------------------
# Test: Successful full dispense (bills only)
# ---------------------------------------------------------------------------

class TestBillOnlyDispense:
    async def test_successful_bill_dispense(self, orchestrator, bill_controller, ws_manager):
        """Dispense 5x PHP_100 bills successfully."""
        # Mock bill controller to return success
        bill_controller.dispense.return_value = MagicMock(dispensed=5)

        plan = _bill_plan({"PHP_100": (5, 100)})
        result = await orchestrator.execute_dispense(plan)

        assert result.success is True
        assert result.dispensed_bills == {"PHP_100": 5}
        assert result.dispensed_coins == {}
        assert result.total_dispensed == 500
        assert result.shortfall == 0
        assert result.claim_ticket_code is None
        assert result.error is None

    async def test_multi_denom_bill_dispense(self, orchestrator, bill_controller, ws_manager):
        """Dispense multiple bill denominations successfully."""
        bill_controller.dispense.side_effect = [
            MagicMock(dispensed=2),  # PHP_500
            MagicMock(dispensed=3),  # PHP_100
        ]

        plan = _bill_plan({"PHP_500": (2, 500), "PHP_100": (3, 100)})
        result = await orchestrator.execute_dispense(plan)

        assert result.success is True
        assert result.dispensed_bills == {"PHP_500": 2, "PHP_100": 3}
        assert result.total_dispensed == 1300
        assert result.shortfall == 0


# ---------------------------------------------------------------------------
# Test: Successful full dispense (coins only)
# ---------------------------------------------------------------------------

class TestCoinOnlyDispense:
    async def test_successful_coin_dispense(self, orchestrator, coin_controller, ws_manager):
        """Dispense coins of a single denomination."""
        coin_controller.coin_dispense.return_value = MagicMock(dispensed=10)

        plan = _coin_plan({"PHP_5": (10, 5)})
        result = await orchestrator.execute_dispense(plan)

        assert result.success is True
        assert result.dispensed_coins == {"PHP_5": 10}
        assert result.dispensed_bills == {}
        assert result.total_dispensed == 50
        assert result.shortfall == 0

    async def test_multi_denom_coin_dispense(self, orchestrator, coin_controller, ws_manager):
        """Dispense multiple coin denominations."""
        coin_controller.coin_dispense.side_effect = [
            MagicMock(dispensed=5),   # PHP_10
            MagicMock(dispensed=10),  # PHP_1
        ]

        plan = _coin_plan({"PHP_10": (5, 10), "PHP_1": (10, 1)})
        result = await orchestrator.execute_dispense(plan)

        assert result.success is True
        assert result.dispensed_coins == {"PHP_10": 5, "PHP_1": 10}
        assert result.total_dispensed == 60


# ---------------------------------------------------------------------------
# Test: Mixed bills and coins
# ---------------------------------------------------------------------------

class TestMixedDispense:
    async def test_mixed_bill_and_coin_dispense(
        self, orchestrator, bill_controller, coin_controller, ws_manager
    ):
        """Dispense a combination of bills and coins."""
        bill_controller.dispense.return_value = MagicMock(dispensed=1)
        coin_controller.coin_dispense.side_effect = [
            MagicMock(dispensed=2),  # PHP_10
            MagicMock(dispensed=5),  # PHP_1
        ]

        plan = _mixed_plan(
            {"PHP_100": (1, 100)},
            {"PHP_10": (2, 10), "PHP_1": (5, 1)},
        )
        result = await orchestrator.execute_dispense(plan)

        assert result.success is True
        assert result.dispensed_bills == {"PHP_100": 1}
        assert result.dispensed_coins == {"PHP_10": 2, "PHP_1": 5}
        assert result.total_dispensed == 125
        assert result.shortfall == 0
        assert result.claim_ticket_code is None


# ---------------------------------------------------------------------------
# Test: Partial dispense on JAM error
# ---------------------------------------------------------------------------

class TestPartialDispense:
    async def test_partial_bill_dispense_generates_claim_ticket(
        self, orchestrator, bill_controller, ws_manager
    ):
        """When a bill JAM occurs mid-dispense, a claim ticket is generated."""
        # First denomination succeeds, second jams after 1 of 3
        bill_controller.dispense.side_effect = [
            MagicMock(dispensed=2),                               # PHP_500: OK
            HardwareError(code="JAM", message="Paper jam", dispensed=1),  # PHP_100: partial
        ]

        plan = _bill_plan({"PHP_500": (2, 500), "PHP_100": (3, 100)})
        result = await orchestrator.execute_dispense(plan)

        assert result.success is False
        assert result.dispensed_bills["PHP_500"] == 2
        assert result.dispensed_bills["PHP_100"] == 1
        assert result.total_dispensed == 1100  # 2*500 + 1*100
        assert result.shortfall == 200  # 2*100 missing
        assert result.claim_ticket_code is not None
        assert len(result.claim_ticket_code) == 8
        assert result.error is not None

    async def test_partial_coin_dispense_generates_claim_ticket(
        self, orchestrator, coin_controller, ws_manager
    ):
        """When a coin dispense fails, shortfall is tracked with claim ticket."""
        coin_controller.coin_dispense.side_effect = [
            MagicMock(dispensed=3),  # PHP_10: OK
            HardwareError(code="JAM", message="Coin stuck", dispensed=2),  # PHP_5: partial
        ]

        plan = _coin_plan({"PHP_10": (3, 10), "PHP_5": (5, 5)})
        result = await orchestrator.execute_dispense(plan)

        assert result.success is False
        assert result.dispensed_coins["PHP_10"] == 3
        assert result.dispensed_coins["PHP_5"] == 2
        assert result.total_dispensed == 40  # 3*10 + 2*5
        assert result.shortfall == 15  # 3*5 missing
        assert result.claim_ticket_code is not None

    async def test_bill_jam_skips_coin_dispensing(
        self, orchestrator, bill_controller, coin_controller, ws_manager
    ):
        """When bills fail, coin dispensing is skipped entirely."""
        bill_controller.dispense.side_effect = HardwareError(
            code="JAM", message="Jam on first bill", dispensed=0
        )

        plan = _mixed_plan(
            {"PHP_100": (2, 100)},
            {"PHP_10": (5, 10)},
        )
        result = await orchestrator.execute_dispense(plan)

        assert result.success is False
        assert result.dispensed_bills == {"PHP_100": 0}
        # Coins should not have been attempted
        coin_controller.coin_dispense.assert_not_called()
        assert result.total_dispensed == 0
        assert result.shortfall == 250  # 2*100 + 5*10
        assert result.claim_ticket_code is not None


# ---------------------------------------------------------------------------
# Test: Progress events broadcasted
# ---------------------------------------------------------------------------

class TestProgressBroadcast:
    async def test_progress_events_for_each_denomination(
        self, orchestrator, bill_controller, coin_controller, ws_manager
    ):
        """A DISPENSE_PROGRESS event is broadcast after each denomination is dispensed."""
        bill_controller.dispense.return_value = MagicMock(dispensed=2)
        coin_controller.coin_dispense.return_value = MagicMock(dispensed=5)

        plan = _mixed_plan(
            {"PHP_100": (2, 100)},
            {"PHP_5": (5, 5)},
        )
        result = await orchestrator.execute_dispense(plan)

        assert result.success is True

        # broadcast should have been called for:
        # 1 progress after PHP_100 bills, 1 progress after PHP_5 coins, 1 final DISPENSE_COMPLETE
        assert ws_manager.broadcast.call_count == 3

        # Check that the first two calls are progress events
        progress_calls = ws_manager.broadcast.call_args_list[:2]
        for call in progress_calls:
            event = call[0][0]
            assert event.type == WSEventType.DISPENSE_PROGRESS
            assert "completed_items" in event.payload
            assert "total_items" in event.payload

    async def test_completion_event_broadcast(
        self, orchestrator, bill_controller, ws_manager
    ):
        """A DISPENSE_COMPLETE event is always broadcast at the end."""
        bill_controller.dispense.return_value = MagicMock(dispensed=1)

        plan = _bill_plan({"PHP_500": (1, 500)})
        result = await orchestrator.execute_dispense(plan)

        # Last broadcast call should be DISPENSE_COMPLETE
        event = ws_manager.broadcast.call_args_list[-1][0][0]
        assert event.type == WSEventType.DISPENSE_COMPLETE
        assert event.payload["success"] is True
        assert event.payload["total_dispensed"] == 500

    async def test_failure_completion_event_includes_claim_ticket(
        self, orchestrator, bill_controller, ws_manager
    ):
        """On partial dispense, the completion event includes the claim ticket code."""
        bill_controller.dispense.side_effect = HardwareError(
            code="JAM", message="Jam", dispensed=0
        )

        plan = _bill_plan({"PHP_100": (3, 100)})
        result = await orchestrator.execute_dispense(plan)

        event = ws_manager.broadcast.call_args_list[-1][0][0]
        assert event.type == WSEventType.DISPENSE_COMPLETE
        assert event.payload["success"] is False
        assert event.payload["claim_ticket_code"] is not None
