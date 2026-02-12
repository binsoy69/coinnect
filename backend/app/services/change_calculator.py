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


# PHP bill denominations sorted descending by value
_PHP_BILL_DENOMS = [
    (BillDenom.PHP_1000, 1000),
    (BillDenom.PHP_500, 500),
    (BillDenom.PHP_200, 200),
    (BillDenom.PHP_100, 100),
    (BillDenom.PHP_50, 50),
    (BillDenom.PHP_20, 20),
]

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
) -> DispensePlan:
    """Calculate optimal change dispensing plan.

    Args:
        amount: Total amount to dispense in PHP.
        available_bills: Available bill counts by denomination string
            (e.g., {"PHP_100": 50, "PHP_500": 20}).
        available_coins: Available coin counts by denomination string
            (e.g., {"PHP_20": 100, "PHP_10": 200}).
        preferred_denoms: User-selected denomination values to prefer
            (e.g., [50, 100]). These are tried first.
        currency: Currency code (currently only "PHP" supported).

    Returns:
        DispensePlan with items, total, and exactness flag.

    Raises:
        InsufficientInventoryError: If exact change cannot be made.
    """
    if amount <= 0:
        return DispensePlan(items=[], total_amount=0, is_exact=True)

    if currency != "PHP":
        raise ValueError(f"Unsupported currency for change: {currency}")

    remaining = amount
    items: List[DispensePlanItem] = []

    # Build working copies of available inventory
    bills_avail = dict(available_bills)
    coins_avail = dict(available_coins)

    # Determine denomination ordering based on user preferences
    bill_order = _get_bill_order(preferred_denoms)
    coin_order = _get_coin_order(preferred_denoms)

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
            items.append(
                DispensePlanItem(
                    denom=denom_key,
                    denom_type="bill",
                    count=count,
                    value=value,
                )
            )
            remaining -= count * value
            bills_avail[denom_key] = avail - count

    # Phase 2: Dispense coins (largest first)
    for denom, value in coin_order:
        if remaining <= 0:
            break
        denom_key = f"PHP_{value}"
        avail = coins_avail.get(denom_key, 0)
        if avail <= 0 or value > remaining:
            continue
        count = min(remaining // value, avail)
        if count > 0:
            items.append(
                DispensePlanItem(
                    denom=denom_key,
                    denom_type="coin",
                    count=count,
                    value=value,
                )
            )
            remaining -= count * value
            coins_avail[denom_key] = avail - count

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
) -> List[tuple]:
    """Get bill denominations in dispensing order.

    If preferred_denoms is provided, those denominations come first
    (in descending order), followed by remaining denominations.
    """
    if not preferred_denoms:
        return list(_PHP_BILL_DENOMS)

    preferred_set = set(preferred_denoms)
    preferred = []
    others = []

    for denom, value in _PHP_BILL_DENOMS:
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
