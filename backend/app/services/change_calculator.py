"""Change calculation algorithm for bill and coin dispensing.

Uses a greedy algorithm: dispense largest denominations first,
preferring user-selected denominations when available.
Bills are dispensed before coins.
"""

import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.core.constants import BILL_DENOM_VALUES, COIN_DENOM_VALUES, BillDenom, CoinDenom
from app.core.errors import InsufficientInventoryError

logger = logging.getLogger(__name__)


class DispensePlanItem(BaseModel):
    """A single item in the dispense plan."""

    denom: str  # e.g., "PHP_100" or "PHP_5"
    denom_type: str  # "bill" or "coin"
    count: int
    value: int  # Per-unit value in PHP


class DispensePlan(BaseModel):
    """Complete dispense plan with bills and coins."""

    items: List[DispensePlanItem]
    total_amount: int
    is_exact: bool  # True if exact amount is achievable

    @property
    def bill_items(self) -> List[DispensePlanItem]:
        return [i for i in self.items if i.denom_type == "bill"]

    @property
    def coin_items(self) -> List[DispensePlanItem]:
        return [i for i in self.items if i.denom_type == "coin"]


# Bill denominations sorted descending by value, per currency
_PHP_BILL_DENOMS = [
    (BillDenom.PHP_1000, 1000),
    (BillDenom.PHP_500, 500),
    (BillDenom.PHP_200, 200),
    (BillDenom.PHP_100, 100),
    (BillDenom.PHP_50, 50),
    (BillDenom.PHP_20, 20),
]

_USD_BILL_DENOMS = [
    (BillDenom.USD_50, 50),
    (BillDenom.USD_10, 10),
]

_EUR_BILL_DENOMS = [
    (BillDenom.EUR_10, 10),
    (BillDenom.EUR_5, 5),
]

_BILL_DENOMS_BY_CURRENCY = {
    "PHP": _PHP_BILL_DENOMS,
    "USD": _USD_BILL_DENOMS,
    "EUR": _EUR_BILL_DENOMS,
}

# PHP coin denominations sorted descending by value
_PHP_COIN_DENOMS = [
    (CoinDenom.PHP_20, 20),
    (CoinDenom.PHP_10, 10),
    (CoinDenom.PHP_5, 5),
    (CoinDenom.PHP_1, 1),
]


def calculate_change(
    amount: int,
    available_bills: Dict[str, int],
    available_coins: Dict[str, int],
    preferred_denoms: Optional[List[int]] = None,
    currency: str = "PHP",
    requested_counts: Optional[Dict[int, int]] = None,
) -> DispensePlan:
    """Calculate optimal change dispensing plan.

    Args:
        amount: Total amount to dispense.
        available_bills: Available bill counts by denomination string
            (e.g., {"PHP_100": 50, "PHP_500": 20}).
        available_coins: Available coin counts by denomination string
            (e.g., {"PHP_20": 100, "PHP_10": 200}).
        preferred_denoms: User-selected denomination values to prefer.
        currency: Currency code ("PHP", "USD", or "EUR").
        requested_counts: Dict mapping denomination value (e.g. 500) to exact requested count.

    Returns:
        DispensePlan with items, total, and exactness flag.

    Raises:
        InsufficientInventoryError: If exact change cannot be made.
    """
    try:
        return _calculate_change_with_order(
            amount, available_bills, available_coins, preferred_denoms, currency, requested_counts
        )
    except InsufficientInventoryError:
        if requested_counts or preferred_denoms:
            logger.info("Preferred/requested change calculation failed. Falling back to standard greedy change.")
            return _calculate_change_with_order(
                amount, available_bills, available_coins, None, currency, None
            )
        raise


def _calculate_change_with_order(
    amount: int,
    available_bills: Dict[str, int],
    available_coins: Dict[str, int],
    preferred_denoms: Optional[List[int]] = None,
    currency: str = "PHP",
    requested_counts: Optional[Dict[int, int]] = None,
) -> DispensePlan:
    if amount <= 0:
        return DispensePlan(items=[], total_amount=0, is_exact=True)

    if currency not in _BILL_DENOMS_BY_CURRENCY:
        raise ValueError(f"Unsupported currency for change: {currency}")

    remaining = amount
    items_dict: Dict[str, DispensePlanItem] = {}

    # Build working copies of available inventory
    bills_avail = dict(available_bills)
    coins_avail = dict(available_coins)

    def add_item(denom_key: str, denom_type: str, count: int, val: int):
        if count <= 0:
            return
        if denom_key in items_dict:
            items_dict[denom_key].count += count
        else:
            items_dict[denom_key] = DispensePlanItem(
                denom=denom_key,
                denom_type=denom_type,
                count=count,
                value=val,
            )

    # Phase 0: Fulfill explicit requested counts first (if provided)
    if requested_counts:
        # Sort requested denoms descending by value
        sorted_req = sorted(requested_counts.items(), key=lambda x: int(x[0]), reverse=True)
        for d_val, req_qty in sorted_req:
            val = int(d_val)
            req_qty = int(req_qty)
            if remaining <= 0 or req_qty <= 0 or val > remaining:
                continue

            denom_key = f"{currency}_{val}" if currency != "PHP" or val >= 20 else f"PHP_{val}"
            # Check if this denom is a bill or a coin
            # For PHP, 20 can be bill or coin; prioritize bill dispenser first
            if denom_key in bills_avail or currency != "PHP":
                avail = bills_avail.get(denom_key, 0)
                count = min(req_qty, avail, remaining // val)
                if count > 0:
                    add_item(denom_key, "bill", count, val)
                    remaining -= count * val
                    bills_avail[denom_key] = avail - count
                    req_qty -= count

            if req_qty > 0 and currency == "PHP" and remaining >= val:
                coin_key = f"PHP_{val}"
                avail = coins_avail.get(coin_key, 0)
                count = min(req_qty, avail, remaining // val)
                if count > 0:
                    add_item(coin_key, "coin", count, val)
                    remaining -= count * val
                    coins_avail[coin_key] = avail - count

    # Determine denomination ordering based on user preferences for remaining shortfall
    bill_order = _get_bill_order(preferred_denoms, currency)

    # Phase 1: Dispense bills (largest preferred first, then remaining)
    for denom, value in bill_order:
        if remaining <= 0:
            break
        denom_key = denom.value
        avail = bills_avail.get(denom_key, 0)
        if avail <= 0 or value > remaining:
            continue
        count = min(remaining // value, avail)
        if count > 0:
            add_item(denom_key, "bill", count, value)
            remaining -= count * value
            bills_avail[denom_key] = avail - count

    # Phase 2: Dispense coins (only for PHP)
    if currency == "PHP":
        coin_order = _get_coin_order(preferred_denoms)
        for denom, value in coin_order:
            if remaining <= 0:
                break
            denom_key = f"PHP_{value}"
            avail = coins_avail.get(denom_key, 0)
            if avail <= 0 or value > remaining:
                continue
            count = min(remaining // value, avail)
            if count > 0:
                add_item(denom_key, "coin", count, value)
                remaining -= count * value
                coins_avail[denom_key] = avail - count

    items = list(items_dict.values())


    total_dispensed = amount - remaining
    is_exact = remaining == 0

    if not is_exact:
        raise InsufficientInventoryError(
            requested=amount,
            available=total_dispensed,
            shortfall=remaining,
        )

    return DispensePlan(
        items=items,
        total_amount=total_dispensed,
        is_exact=is_exact,
    )


def _get_bill_order(
    preferred_denoms: Optional[List[int]],
    currency: str = "PHP",
) -> List[tuple]:
    """Get bill denominations in dispensing order.

    If preferred_denoms is provided, those denominations come first
    (in descending order), followed by remaining denominations.
    """
    base_denoms = _BILL_DENOMS_BY_CURRENCY.get(currency, _PHP_BILL_DENOMS)

    if not preferred_denoms:
        return list(base_denoms)

    preferred_set = set(preferred_denoms)
    preferred = []
    others = []

    for denom, value in base_denoms:
        if value in preferred_set:
            preferred.append((denom, value))
        else:
            others.append((denom, value))

    return preferred + others


def _get_coin_order(
    preferred_denoms: Optional[List[int]],
) -> List[tuple]:
    """Get coin denominations in dispensing order.

    If preferred_denoms includes coin values, those come first.
    """
    if not preferred_denoms:
        return list(_PHP_COIN_DENOMS)

    preferred_set = set(preferred_denoms)
    preferred = []
    others = []

    for denom, value in _PHP_COIN_DENOMS:
        if value in preferred_set:
            preferred.append((denom, value))
        else:
            others.append((denom, value))

    return preferred + others
