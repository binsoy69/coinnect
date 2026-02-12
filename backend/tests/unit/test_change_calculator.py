"""Comprehensive unit tests for the change calculator service."""

import pytest

from app.core.errors import InsufficientInventoryError
from app.services.change_calculator import (
    DispensePlan,
    DispensePlanItem,
    calculate_change,
)


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def full_bill_inventory():
    """Return a bill inventory with generous stock of every PHP denomination."""
    return {
        "PHP_1000": 50,
        "PHP_500": 50,
        "PHP_200": 50,
        "PHP_100": 100,
        "PHP_50": 100,
        "PHP_20": 200,
    }


@pytest.fixture
def full_coin_inventory():
    """Return a coin inventory with generous stock of every PHP denomination."""
    return {
        "PHP_20": 200,
        "PHP_10": 200,
        "PHP_5": 200,
        "PHP_1": 500,
    }


@pytest.fixture
def empty_bills():
    return {}


@pytest.fixture
def empty_coins():
    return {}


# ---------------------------------------------------------------------------
# 1. Basic exact change with bills only
# ---------------------------------------------------------------------------


class TestBillsOnly:
    def test_single_denomination_exact(self, full_bill_inventory, empty_coins):
        plan = calculate_change(1000, full_bill_inventory, empty_coins)
        assert plan.is_exact
        assert plan.total_amount == 1000
        assert len(plan.items) == 1
        assert plan.items[0].denom == "PHP_1000"
        assert plan.items[0].count == 1
        assert plan.items[0].denom_type == "bill"

    def test_multiple_of_single_denomination(self, full_bill_inventory, empty_coins):
        plan = calculate_change(3000, full_bill_inventory, empty_coins)
        assert plan.is_exact
        assert plan.total_amount == 3000
        assert plan.items[0].denom == "PHP_1000"
        assert plan.items[0].count == 3

    def test_multiple_denominations(self, full_bill_inventory, empty_coins):
        plan = calculate_change(1550, full_bill_inventory, empty_coins)
        assert plan.is_exact
        assert plan.total_amount == 1550
        # Greedy: 1000 + 500 + 50
        denoms = {item.denom: item.count for item in plan.items}
        assert denoms["PHP_1000"] == 1
        assert denoms["PHP_500"] == 1
        assert denoms["PHP_50"] == 1

    def test_bill_items_property(self, full_bill_inventory, empty_coins):
        plan = calculate_change(500, full_bill_inventory, empty_coins)
        assert len(plan.bill_items) == 1
        assert len(plan.coin_items) == 0

    def test_smallest_bill(self, full_bill_inventory, empty_coins):
        plan = calculate_change(20, full_bill_inventory, empty_coins)
        assert plan.is_exact
        assert plan.items[0].denom == "PHP_20"
        assert plan.items[0].count == 1


# ---------------------------------------------------------------------------
# 2. Basic exact change with coins only
# ---------------------------------------------------------------------------


class TestCoinsOnly:
    def test_single_coin(self, empty_bills, full_coin_inventory):
        plan = calculate_change(10, empty_bills, full_coin_inventory)
        assert plan.is_exact
        assert plan.total_amount == 10
        # Greedy picks PHP_20 first but 20 > 10, so picks PHP_10
        assert plan.items[0].denom == "PHP_10"
        assert plan.items[0].count == 1
        assert plan.items[0].denom_type == "coin"

    def test_multiple_coins(self, empty_bills, full_coin_inventory):
        plan = calculate_change(36, empty_bills, full_coin_inventory)
        assert plan.is_exact
        assert plan.total_amount == 36
        # Greedy: 20 + 10 + 5 + 1
        denoms = {item.denom: item.count for item in plan.items}
        assert denoms["PHP_20"] == 1
        assert denoms["PHP_10"] == 1
        assert denoms["PHP_5"] == 1
        assert denoms["PHP_1"] == 1

    def test_coin_items_property(self, empty_bills, full_coin_inventory):
        plan = calculate_change(15, empty_bills, full_coin_inventory)
        assert len(plan.coin_items) > 0
        assert len(plan.bill_items) == 0

    def test_coins_all_same_denomination(self, empty_bills, full_coin_inventory):
        plan = calculate_change(5, empty_bills, full_coin_inventory)
        assert plan.is_exact
        assert plan.items[0].denom == "PHP_5"
        assert plan.items[0].count == 1


# ---------------------------------------------------------------------------
# 3. Mixed bills and coins
# ---------------------------------------------------------------------------


class TestMixedBillsAndCoins:
    def test_bills_and_coins_combined(self, full_bill_inventory, full_coin_inventory):
        # 1025 = 1000 bill + 20 coin + 5 coin
        plan = calculate_change(1025, full_bill_inventory, full_coin_inventory)
        assert plan.is_exact
        assert plan.total_amount == 1025
        assert len(plan.bill_items) >= 1
        assert len(plan.coin_items) >= 1

    def test_bills_before_coins(self, full_bill_inventory, full_coin_inventory):
        """Bills should appear before coins in the items list."""
        plan = calculate_change(1025, full_bill_inventory, full_coin_inventory)
        bill_indices = [
            i for i, item in enumerate(plan.items) if item.denom_type == "bill"
        ]
        coin_indices = [
            i for i, item in enumerate(plan.items) if item.denom_type == "coin"
        ]
        if bill_indices and coin_indices:
            assert max(bill_indices) < min(coin_indices), (
                "All bill items should come before all coin items"
            )

    def test_bill_used_when_available_over_coins(
        self, full_bill_inventory, full_coin_inventory
    ):
        """For PHP 20, bill should be used (bills are dispensed first)."""
        plan = calculate_change(20, full_bill_inventory, full_coin_inventory)
        assert plan.is_exact
        assert plan.items[0].denom_type == "bill"
        assert plan.items[0].denom == "PHP_20"

    def test_remainder_after_bills_goes_to_coins(self):
        bills = {"PHP_100": 10}
        coins = {"PHP_5": 100, "PHP_1": 100}
        plan = calculate_change(106, bills, coins)
        assert plan.is_exact
        assert plan.total_amount == 106
        denoms = {item.denom: item.count for item in plan.items}
        assert denoms["PHP_100"] == 1
        assert denoms["PHP_5"] == 1
        assert denoms["PHP_1"] == 1


# ---------------------------------------------------------------------------
# 4. Preferred denominations ordering
# ---------------------------------------------------------------------------


class TestPreferredDenoms:
    def test_preferred_bill_used_first(self, full_bill_inventory, empty_coins):
        """If user prefers 200, use 200s before 1000/500/100."""
        plan = calculate_change(
            400, full_bill_inventory, empty_coins, preferred_denoms=[200]
        )
        assert plan.is_exact
        assert plan.items[0].denom == "PHP_200"
        assert plan.items[0].count == 2

    def test_preferred_over_greedy_larger(self, full_bill_inventory, empty_coins):
        """Prefer PHP_100 over PHP_500 for amount=500."""
        plan = calculate_change(
            500, full_bill_inventory, empty_coins, preferred_denoms=[100]
        )
        assert plan.is_exact
        assert plan.items[0].denom == "PHP_100"
        assert plan.items[0].count == 5

    def test_preferred_coins(self, empty_bills, full_coin_inventory):
        """Prefer PHP_5 coins over PHP_20/PHP_10."""
        plan = calculate_change(
            15, empty_bills, full_coin_inventory, preferred_denoms=[5]
        )
        assert plan.is_exact
        assert plan.items[0].denom == "PHP_5"
        assert plan.items[0].count == 3

    def test_preferred_with_fallback(self, full_bill_inventory, full_coin_inventory):
        """Preferred denom used first, then falls back to greedy for remainder."""
        plan = calculate_change(
            750, full_bill_inventory, full_coin_inventory, preferred_denoms=[200]
        )
        assert plan.is_exact
        assert plan.total_amount == 750
        # Should dispense 200*3=600 first, then 100+50 from remaining
        denoms = {item.denom: item.count for item in plan.items}
        assert denoms.get("PHP_200") == 3

    def test_preferred_denom_not_in_inventory_ignored(self, empty_coins):
        """Preferred denom not in inventory falls through to others."""
        bills = {"PHP_100": 10}
        plan = calculate_change(300, bills, empty_coins, preferred_denoms=[500])
        assert plan.is_exact
        assert plan.items[0].denom == "PHP_100"
        assert plan.items[0].count == 3

    def test_multiple_preferred_denoms(self, full_bill_inventory, empty_coins):
        """Multiple preferred denoms are tried in descending order."""
        plan = calculate_change(
            250, full_bill_inventory, empty_coins, preferred_denoms=[50, 200]
        )
        assert plan.is_exact
        # Preferred order is descending: 200 first, then 50
        assert plan.items[0].denom == "PHP_200"
        assert plan.items[0].count == 1
        assert plan.items[1].denom == "PHP_50"
        assert plan.items[1].count == 1


# ---------------------------------------------------------------------------
# 5. Amount = 0 returns empty plan
# ---------------------------------------------------------------------------


class TestZeroAmount:
    def test_zero_amount_returns_empty(
        self, full_bill_inventory, full_coin_inventory
    ):
        plan = calculate_change(0, full_bill_inventory, full_coin_inventory)
        assert plan.is_exact
        assert plan.total_amount == 0
        assert plan.items == []

    def test_negative_amount_returns_empty(
        self, full_bill_inventory, full_coin_inventory
    ):
        plan = calculate_change(-100, full_bill_inventory, full_coin_inventory)
        assert plan.is_exact
        assert plan.total_amount == 0
        assert plan.items == []


# ---------------------------------------------------------------------------
# 6. InsufficientInventoryError when cannot make change
# ---------------------------------------------------------------------------


class TestInsufficientInventory:
    def test_no_inventory_at_all(self, empty_bills, empty_coins):
        with pytest.raises(InsufficientInventoryError) as exc_info:
            calculate_change(100, empty_bills, empty_coins)
        assert exc_info.value.requested == 100
        assert exc_info.value.available == 0
        assert exc_info.value.shortfall == 100

    def test_insufficient_bills_no_coins(self, empty_coins):
        bills = {"PHP_100": 2}
        with pytest.raises(InsufficientInventoryError) as exc_info:
            calculate_change(500, bills, empty_coins)
        assert exc_info.value.requested == 500
        assert exc_info.value.available == 200
        assert exc_info.value.shortfall == 300

    def test_cant_make_exact_change(self, empty_coins):
        """Only PHP_500 bills, requesting 750 -- cannot make exact."""
        bills = {"PHP_500": 10}
        with pytest.raises(InsufficientInventoryError) as exc_info:
            calculate_change(750, bills, empty_coins)
        assert exc_info.value.requested == 750
        assert exc_info.value.shortfall == 250

    def test_partial_inventory(self):
        """Have some but not enough to cover the full amount."""
        bills = {"PHP_100": 1}
        coins = {"PHP_10": 2}
        with pytest.raises(InsufficientInventoryError) as exc_info:
            calculate_change(200, bills, coins)
        assert exc_info.value.requested == 200
        assert exc_info.value.available == 120
        assert exc_info.value.shortfall == 80

    def test_error_message_format(self, empty_bills, empty_coins):
        with pytest.raises(
            InsufficientInventoryError, match="Insufficient inventory"
        ):
            calculate_change(50, empty_bills, empty_coins)


# ---------------------------------------------------------------------------
# 7. Greedy algorithm correctness
# ---------------------------------------------------------------------------


class TestGreedyAlgorithm:
    def test_350_uses_200_100_50(self, full_bill_inventory, empty_coins):
        plan = calculate_change(350, full_bill_inventory, empty_coins)
        assert plan.is_exact
        denoms = {item.denom: item.count for item in plan.items}
        assert denoms.get("PHP_200") == 1
        assert denoms.get("PHP_100") == 1
        assert denoms.get("PHP_50") == 1

    def test_greedy_picks_largest_first(
        self, full_bill_inventory, full_coin_inventory
    ):
        """1770 = 1000 + 500 + 200 + 50 + 20(bill)."""
        plan = calculate_change(1770, full_bill_inventory, full_coin_inventory)
        assert plan.is_exact
        denoms = {item.denom: item.count for item in plan.items}
        assert denoms.get("PHP_1000") == 1
        assert denoms.get("PHP_500") == 1
        assert denoms.get("PHP_200") == 1
        assert denoms.get("PHP_50") == 1
        assert denoms.get("PHP_20") == 1

    def test_1111_greedy_decomposition(
        self, full_bill_inventory, full_coin_inventory
    ):
        """1111 = 1000 + 100 + 10 + 1."""
        plan = calculate_change(1111, full_bill_inventory, full_coin_inventory)
        assert plan.is_exact
        denoms = {item.denom: item.count for item in plan.items}
        assert denoms.get("PHP_1000") == 1
        assert denoms.get("PHP_100") == 1
        assert denoms.get("PHP_10") == 1
        assert denoms.get("PHP_1") == 1

    def test_greedy_uses_multiple_of_same_denom(
        self, full_bill_inventory, empty_coins
    ):
        """5000 = 5 x PHP_1000."""
        plan = calculate_change(5000, full_bill_inventory, empty_coins)
        assert plan.is_exact
        assert len(plan.items) == 1
        assert plan.items[0].denom == "PHP_1000"
        assert plan.items[0].count == 5

    def test_value_field_correctness(
        self, full_bill_inventory, full_coin_inventory
    ):
        """Ensure DispensePlanItem.value is per-unit, not total."""
        plan = calculate_change(2000, full_bill_inventory, full_coin_inventory)
        for item in plan.items:
            assert item.value * item.count <= plan.total_amount
            if item.denom == "PHP_1000":
                assert item.value == 1000
            elif item.denom == "PHP_500":
                assert item.value == 500


# ---------------------------------------------------------------------------
# 8. Large amount dispensing
# ---------------------------------------------------------------------------


class TestLargeAmounts:
    def test_large_amount_50000(
        self, full_bill_inventory, full_coin_inventory
    ):
        plan = calculate_change(
            50000, full_bill_inventory, full_coin_inventory
        )
        assert plan.is_exact
        assert plan.total_amount == 50000

    def test_large_amount_uses_biggest_denoms(
        self, full_bill_inventory, empty_coins
    ):
        plan = calculate_change(30000, full_bill_inventory, empty_coins)
        assert plan.is_exact
        assert plan.items[0].denom == "PHP_1000"
        assert plan.items[0].count == 30

    def test_large_mixed_amount(self):
        """99999 PHP: uses all denominations including coins."""
        bills = {
            "PHP_1000": 100,
            "PHP_500": 100,
            "PHP_200": 100,
            "PHP_100": 100,
            "PHP_50": 100,
            "PHP_20": 100,
        }
        coins = {
            "PHP_20": 500,
            "PHP_10": 500,
            "PHP_5": 500,
            "PHP_1": 500,
        }
        plan = calculate_change(99999, bills, coins)
        assert plan.is_exact
        assert plan.total_amount == 99999

    def test_sum_of_items_equals_total(
        self, full_bill_inventory, full_coin_inventory
    ):
        """Verify the sum of (count * value) for all items equals total."""
        plan = calculate_change(
            12345, full_bill_inventory, full_coin_inventory
        )
        computed_total = sum(
            item.count * item.value for item in plan.items
        )
        assert computed_total == plan.total_amount
        assert computed_total == 12345


# ---------------------------------------------------------------------------
# 9. Inventory limits respected
# ---------------------------------------------------------------------------


class TestInventoryLimits:
    def test_limited_bills_forces_smaller_denoms(self, full_coin_inventory):
        """Only 1 x PHP_1000, need 2000 -> uses 1000 + fallback."""
        bills = {
            "PHP_1000": 1,
            "PHP_500": 10,
            "PHP_200": 10,
            "PHP_100": 10,
        }
        plan = calculate_change(2000, bills, full_coin_inventory)
        assert plan.is_exact
        denoms = {item.denom: item.count for item in plan.items}
        assert denoms.get("PHP_1000") == 1
        # Remaining 1000 should be covered by 500s
        assert denoms.get("PHP_500") == 2

    def test_zero_stock_denom_skipped(self, empty_coins):
        bills = {"PHP_1000": 0, "PHP_500": 5, "PHP_100": 10}
        plan = calculate_change(1000, bills, empty_coins)
        assert plan.is_exact
        assert all(item.denom != "PHP_1000" for item in plan.items)
        denoms = {item.denom: item.count for item in plan.items}
        assert denoms["PHP_500"] == 2

    def test_exact_inventory_consumed(self, empty_coins):
        """Use every available bill to make exact change."""
        bills = {"PHP_100": 3, "PHP_50": 1}
        plan = calculate_change(350, bills, empty_coins)
        assert plan.is_exact
        denoms = {item.denom: item.count for item in plan.items}
        assert denoms["PHP_100"] == 3
        assert denoms["PHP_50"] == 1

    def test_inventory_not_mutated(self, empty_coins):
        """The original inventory dicts should not be modified."""
        bills = {"PHP_100": 5}
        coins = {"PHP_10": 10}
        original_bills = dict(bills)
        original_coins = dict(coins)
        calculate_change(110, bills, coins)
        assert bills == original_bills
        assert coins == original_coins

    def test_limited_coins_forces_smaller(self, empty_bills):
        """Only 1 x PHP_20, need 30 -> uses 20 + 10."""
        coins = {
            "PHP_20": 1,
            "PHP_10": 5,
            "PHP_5": 5,
            "PHP_1": 10,
        }
        plan = calculate_change(30, empty_bills, coins)
        assert plan.is_exact
        denoms = {item.denom: item.count for item in plan.items}
        assert denoms["PHP_20"] == 1
        assert denoms["PHP_10"] == 1

    def test_dispense_count_never_exceeds_available(self):
        """No item count should exceed what was available."""
        bills = {"PHP_500": 2, "PHP_100": 3}
        coins = {"PHP_10": 5}
        plan = calculate_change(1350, bills, coins)
        assert plan.is_exact
        for item in plan.items:
            if item.denom == "PHP_500":
                assert item.count <= 2
            elif item.denom == "PHP_100":
                assert item.count <= 3
            elif item.denom == "PHP_10":
                assert item.count <= 5


# ---------------------------------------------------------------------------
# 10. Edge case: amount=1 (only PHP_1 coin)
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_amount_one_with_php1_coin(self, empty_bills):
        coins = {"PHP_1": 10}
        plan = calculate_change(1, empty_bills, coins)
        assert plan.is_exact
        assert plan.total_amount == 1
        assert len(plan.items) == 1
        assert plan.items[0].denom == "PHP_1"
        assert plan.items[0].count == 1
        assert plan.items[0].denom_type == "coin"

    def test_amount_one_without_php1_fails(self, empty_bills):
        coins = {"PHP_5": 10, "PHP_10": 10}
        with pytest.raises(InsufficientInventoryError):
            calculate_change(1, empty_bills, coins)

    def test_minimum_bill_value(self, empty_coins):
        """Smallest possible bill-only transaction."""
        bills = {"PHP_20": 1}
        plan = calculate_change(20, bills, empty_coins)
        assert plan.is_exact
        assert plan.total_amount == 20

    def test_all_ones(self, empty_bills):
        """Dispense 10 PHP entirely in PHP_1 coins."""
        coins = {"PHP_1": 20}
        plan = calculate_change(10, empty_bills, coins)
        assert plan.is_exact
        assert plan.items[0].denom == "PHP_1"
        assert plan.items[0].count == 10

    def test_dispense_plan_item_model(self):
        """Verify DispensePlanItem fields."""
        item = DispensePlanItem(
            denom="PHP_100", denom_type="bill", count=5, value=100
        )
        assert item.denom == "PHP_100"
        assert item.denom_type == "bill"
        assert item.count == 5
        assert item.value == 100

    def test_dispense_plan_model_properties(self):
        """Verify DispensePlan bill_items/coin_items filtering."""
        items = [
            DispensePlanItem(
                denom="PHP_100", denom_type="bill", count=1, value=100
            ),
            DispensePlanItem(
                denom="PHP_10", denom_type="coin", count=1, value=10
            ),
        ]
        plan = DispensePlan(
            items=items, total_amount=110, is_exact=True
        )
        assert len(plan.bill_items) == 1
        assert len(plan.coin_items) == 1
        assert plan.bill_items[0].denom == "PHP_100"
        assert plan.coin_items[0].denom == "PHP_10"


# ---------------------------------------------------------------------------
# 11. Currency validation
# ---------------------------------------------------------------------------


class TestCurrencyValidation:
    def test_php_is_accepted(
        self, full_bill_inventory, full_coin_inventory
    ):
        plan = calculate_change(
            100, full_bill_inventory, full_coin_inventory, currency="PHP"
        )
        assert plan.is_exact

    def test_usd_raises_value_error(
        self, full_bill_inventory, full_coin_inventory
    ):
        with pytest.raises(ValueError, match="Unsupported currency"):
            calculate_change(
                100,
                full_bill_inventory,
                full_coin_inventory,
                currency="USD",
            )

    def test_eur_raises_value_error(
        self, full_bill_inventory, full_coin_inventory
    ):
        with pytest.raises(ValueError, match="Unsupported currency"):
            calculate_change(
                100,
                full_bill_inventory,
                full_coin_inventory,
                currency="EUR",
            )

    def test_empty_currency_raises_value_error(
        self, full_bill_inventory, full_coin_inventory
    ):
        with pytest.raises(ValueError, match="Unsupported currency"):
            calculate_change(
                100,
                full_bill_inventory,
                full_coin_inventory,
                currency="",
            )

    def test_random_string_currency_raises_value_error(
        self, full_bill_inventory, full_coin_inventory
    ):
        with pytest.raises(ValueError, match="Unsupported currency"):
            calculate_change(
                100,
                full_bill_inventory,
                full_coin_inventory,
                currency="XYZ",
            )

    def test_lowercase_php_raises_value_error(
        self, full_bill_inventory, full_coin_inventory
    ):
        """Currency check is case-sensitive; php != PHP."""
        with pytest.raises(ValueError, match="Unsupported currency"):
            calculate_change(
                100,
                full_bill_inventory,
                full_coin_inventory,
                currency="php",
            )

