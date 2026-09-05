import pytest
from app.services.converter_payout_planner import plan_payout


def test_exact_planning_60_with_50_and_three_20s():
    """₱60 with one ₱50 and three ₱20 bills returns three ₱20 bills (greedy fails)."""
    available_bills = {
        "PHP_50": 1,
        "PHP_20": 3,
    }
    result = plan_payout(
        service_type="bill-to-bill",
        payout_amount=60,
        available_bills=available_bills,
        available_coins={},
    )
    assert result.success is True
    assert result.total_payout == 60
    assert len(result.items) == 1
    assert result.items[0].denom == "PHP_20"
    assert result.items[0].count == 3


def test_substitutions_two_50s_with_one_100_available():
    """Two requested ₱50 bills with only one ₱100 available produce a replacement proposal."""
    available_bills = {
        "PHP_100": 1,
        "PHP_50": 0,
    }
    requested = {"50": 2}
    result = plan_payout(
        service_type="bill-to-bill",
        payout_amount=100,
        available_bills=available_bills,
        available_coins={},
        requested_counts=requested,
    )
    assert result.success is True
    assert result.total_payout == 100
    assert result.is_substitution is True
    assert result.substitution_notice is not None
    assert len(result.items) == 1
    assert result.items[0].denom == "PHP_100"
    assert result.items[0].count == 1


def test_partial_selection_90_with_requested_50():
    """₱90 payout with one requested ₱50 preserves it and adds two ₱20 bills when available."""
    available_bills = {
        "PHP_50": 1,
        "PHP_20": 3,
    }
    requested = {"PHP_50": 1}
    result = plan_payout(
        service_type="bill-to-bill",
        payout_amount=90,
        available_bills=available_bills,
        available_coins={},
        requested_counts=requested,
    )
    assert result.success is True
    assert result.total_payout == 90
    assert result.is_substitution is False  # Filling remainder is NOT a substitution!
    counts = {item.denom: item.count for item in result.items}
    assert counts == {"PHP_50": 1, "PHP_20": 2}


def test_bill_to_coin_command_limits():
    """Auto-generated plans obey 50 coins per denomination limit."""
    available_coins = {
        "PHP_1": 100,
    }
    # Requesting ₱60 payout when only 1-peso coins are available
    # Since limit is 50, it cannot dispense 60 coins.
    result = plan_payout(
        service_type="bill-to-coin",
        payout_amount=60,
        available_bills={},
        available_coins=available_coins,
    )
    assert result.success is False
    assert result.reason_code == "INSUFFICIENT_INVENTORY"


def test_rejects_negative_quantities():
    result = plan_payout(
        service_type="bill-to-bill",
        payout_amount=100,
        available_bills={"PHP_100": 1},
        available_coins={},
        requested_counts={"100": -1},
    )
    assert result.success is False
    assert result.reason_code == "INVALID_PARAM"


def test_rejects_unsupported_denominations():
    result = plan_payout(
        service_type="bill-to-bill",
        payout_amount=100,
        available_bills={"PHP_100": 1},
        available_coins={},
        requested_counts={"25": 4},
    )
    assert result.success is False
    assert result.reason_code == "INVALID_PARAM"


def test_rejects_requested_totals_above_payout():
    result = plan_payout(
        service_type="bill-to-bill",
        payout_amount=100,
        available_bills={"PHP_100": 2},
        available_coins={},
        requested_counts={"100": 2},
    )
    assert result.success is False
    assert result.reason_code == "REQUESTED_EXCEEDS_PAYOUT"


def test_tie_breaking_prefers_larger_denominations():
    """₱100 payout with 2x ₱50 and 5x ₱20 available with no preference prefers 2x ₱50 (fewer pieces, larger denoms)."""
    available_bills = {
        "PHP_50": 2,
        "PHP_20": 5,
    }
    result = plan_payout(
        service_type="bill-to-bill",
        payout_amount=100,
        available_bills=available_bills,
        available_coins={},
    )
    assert result.success is True
    assert len(result.items) == 1
    assert result.items[0].denom == "PHP_50"
    assert result.items[0].count == 2
