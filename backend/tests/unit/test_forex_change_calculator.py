"""Unit tests for forex change calculator."""

import pytest
from datetime import datetime

from app.core.errors import InsufficientInventoryError
from app.models.forex import ForexQuote
from app.services.forex_change_calculator import calculate_forex_dispense


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def usd_to_php_quote():
    """100 USD -> PHP, rate=58.76, 5% fee -> output 5582 PHP."""
    return ForexQuote(
        from_currency="USD",
        to_currency="PHP",
        rate=58.76,
        input_amount=100,
        converted_amount=5876,
        fee_percentage=5.0,
        fee_amount=294,
        output_amount=5582,
        locked_at=datetime.utcnow(),
    )


@pytest.fixture
def php_to_usd_quote():
    """50 USD out, PHP -> USD."""
    return ForexQuote(
        from_currency="PHP",
        to_currency="USD",
        rate=0.017,
        input_amount=3086,
        converted_amount=2938,
        fee_percentage=5.0,
        fee_amount=147,
        output_amount=50,
        locked_at=datetime.utcnow(),
    )


@pytest.fixture
def eur_to_php_quote():
    """20 EUR -> PHP, rate=61.72, 4% fee."""
    return ForexQuote(
        from_currency="EUR",
        to_currency="PHP",
        rate=61.72,
        input_amount=20,
        converted_amount=1234,
        fee_percentage=4.0,
        fee_amount=49,
        output_amount=1185,
        locked_at=datetime.utcnow(),
    )


@pytest.fixture
def php_to_eur_quote():
    """10 EUR out."""
    return ForexQuote(
        from_currency="PHP",
        to_currency="EUR",
        rate=0.016,
        input_amount=646,
        converted_amount=617,
        fee_percentage=4.0,
        fee_amount=25,
        output_amount=10,
        locked_at=datetime.utcnow(),
    )


@pytest.fixture
def full_php_bill_inventory():
    return {
        "PHP_1000": 50, "PHP_500": 50, "PHP_200": 50,
        "PHP_100": 100, "PHP_50": 100, "PHP_20": 200,
    }


@pytest.fixture
def full_php_coin_inventory():
    return {"PHP_20": 200, "PHP_10": 200, "PHP_5": 200, "PHP_1": 500}


@pytest.fixture
def full_usd_bill_inventory():
    return {"USD_100": 20, "USD_50": 20, "USD_10": 50}


@pytest.fixture
def full_eur_bill_inventory():
    return {"EUR_20": 30, "EUR_10": 30, "EUR_5": 50}


@pytest.fixture
def mixed_inventory():
    """Inventory with PHP, USD, and EUR bills."""
    return {
        "PHP_1000": 50, "PHP_500": 50, "PHP_200": 50,
        "PHP_100": 100, "PHP_50": 100, "PHP_20": 200,
        "USD_100": 20, "USD_50": 20, "USD_10": 50,
        "EUR_20": 30, "EUR_10": 30, "EUR_5": 50,
    }


# ---------------------------------------------------------------------------
# 1. Dispense PHP from foreign input
# ---------------------------------------------------------------------------


class TestDispensePhp:
    def test_usd_to_php_basic(
        self, usd_to_php_quote, full_php_bill_inventory, full_php_coin_inventory
    ):
        """Should dispense 5582 PHP using PHP bills + coins."""
        plan = calculate_forex_dispense(
            usd_to_php_quote, full_php_bill_inventory, full_php_coin_inventory
        )
        assert plan.is_exact
        assert plan.total_amount == 5582

    def test_eur_to_php_basic(
        self, eur_to_php_quote, full_php_bill_inventory, full_php_coin_inventory
    ):
        """Should dispense 1185 PHP."""
        plan = calculate_forex_dispense(
            eur_to_php_quote, full_php_bill_inventory, full_php_coin_inventory
        )
        assert plan.is_exact
        assert plan.total_amount == 1185

    def test_php_dispense_uses_coins_for_remainder(
        self, usd_to_php_quote, full_php_bill_inventory, full_php_coin_inventory
    ):
        """PHP dispensing should use coins for sub-20 amounts."""
        plan = calculate_forex_dispense(
            usd_to_php_quote, full_php_bill_inventory, full_php_coin_inventory
        )
        # 5582 = 5000 + 500 + 50 + 20 + 10 + 2*1
        assert plan.total_amount == 5582
        assert len(plan.coin_items) > 0

    def test_only_uses_php_bills_not_foreign(
        self, usd_to_php_quote, mixed_inventory, full_php_coin_inventory
    ):
        """When dispensing PHP, should not use USD/EUR bills."""
        plan = calculate_forex_dispense(
            usd_to_php_quote, mixed_inventory, full_php_coin_inventory
        )
        for item in plan.items:
            assert item.denom.startswith("PHP_")


# ---------------------------------------------------------------------------
# 2. Dispense foreign currency from PHP input
# ---------------------------------------------------------------------------


class TestDispenseForeign:
    def test_php_to_usd_basic(self, php_to_usd_quote, full_usd_bill_inventory):
        """Should dispense 50 USD using USD bills only."""
        plan = calculate_forex_dispense(
            php_to_usd_quote, full_usd_bill_inventory, {}
        )
        assert plan.is_exact
        assert plan.total_amount == 50

    def test_php_to_eur_basic(self, php_to_eur_quote, full_eur_bill_inventory):
        """Should dispense 10 EUR."""
        plan = calculate_forex_dispense(
            php_to_eur_quote, full_eur_bill_inventory, {}
        )
        assert plan.is_exact
        assert plan.total_amount == 10

    def test_foreign_dispense_no_coins(
        self, php_to_usd_quote, full_usd_bill_inventory, full_php_coin_inventory
    ):
        """Foreign currency dispensing should never use coins."""
        plan = calculate_forex_dispense(
            php_to_usd_quote, full_usd_bill_inventory, full_php_coin_inventory
        )
        assert len(plan.coin_items) == 0

    def test_only_uses_target_currency_bills(
        self, php_to_usd_quote, mixed_inventory, full_php_coin_inventory
    ):
        """When dispensing USD, should not use PHP/EUR bills."""
        plan = calculate_forex_dispense(
            php_to_usd_quote, mixed_inventory, full_php_coin_inventory
        )
        for item in plan.items:
            assert item.denom.startswith("USD_")


# ---------------------------------------------------------------------------
# 3. Insufficient inventory
# ---------------------------------------------------------------------------


class TestInsufficientInventory:
    def test_insufficient_php_bills(self, usd_to_php_quote):
        """Not enough PHP to dispense."""
        small_php = {"PHP_100": 1}
        with pytest.raises(InsufficientInventoryError):
            calculate_forex_dispense(usd_to_php_quote, small_php, {})

    def test_insufficient_usd_bills(self, php_to_usd_quote):
        """Not enough USD to dispense."""
        small_usd = {"USD_10": 1}
        with pytest.raises(InsufficientInventoryError):
            calculate_forex_dispense(php_to_usd_quote, small_usd, {})


# ---------------------------------------------------------------------------
# 4. Preferred denominations
# ---------------------------------------------------------------------------


class TestPreferredDenoms:
    def test_preferred_php_denom(
        self, usd_to_php_quote, full_php_bill_inventory, full_php_coin_inventory
    ):
        """Prefer PHP_200 over PHP_500/PHP_1000."""
        plan = calculate_forex_dispense(
            usd_to_php_quote,
            full_php_bill_inventory,
            full_php_coin_inventory,
            preferred_denoms=[200],
        )
        assert plan.is_exact
        # PHP_200 should appear in the plan
        denom_names = [item.denom for item in plan.items]
        assert "PHP_200" in denom_names
