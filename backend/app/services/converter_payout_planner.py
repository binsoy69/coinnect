"""Bounded dynamic programming payout planner for money converter transactions.

Adheres to Section 2.A specifications:
- Candidate ordering:
  1. Minimize the value of requested units that cannot be preserved.
  2. Minimize the number of requested units that cannot be preserved.
  3. Minimize total payout pieces.
  4. Prefer larger denominations to break ties deterministically.
- Actual quantity > requested is allowed for filling unallocated remainder (not a substitution).
- Actual quantity < requested is a substitution.
- Command limits: 20 bills or 50 coins per denomination.
"""

from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel

from app.models.converter import PayoutItem


# Supported denominations and per-unit values
PHP_BILL_DENOMINATIONS = [
    ("PHP_1000", 1000),
    ("PHP_500", 500),
    ("PHP_200", 200),
    ("PHP_100", 100),
    ("PHP_50", 50),
    ("PHP_20", 20),
]

PHP_COIN_DENOMINATIONS = [
    ("PHP_20", 20),
    ("PHP_10", 10),
    ("PHP_5", 5),
    ("PHP_1", 1),
]

MAX_BILL_PER_DENOM = 20
MAX_COIN_PER_DENOM = 50


class PlannerResult(BaseModel):
    """Result of exact payout planning."""
    success: bool
    items: List[PayoutItem] = []
    total_payout: int = 0
    requested_counts: Dict[str, int] = {}
    is_substitution: bool = False
    substitution_notice: Optional[str] = None
    reason_code: Optional[str] = None
    reason: Optional[str] = None

    @property
    def payout_amount(self) -> int:
        return self.total_payout


def normalize_requested_counts(
    raw_counts: Optional[Dict[str | int, int]],
    permitted_denoms: List[Tuple[str, int]],
) -> Dict[str, int]:
    """Normalize user requested counts to denomination string keys (e.g. 'PHP_50')."""
    if not raw_counts:
        return {}

    val_to_denom = {val: denom for denom, val in permitted_denoms}
    denom_to_val = {denom: val for denom, val in permitted_denoms}

    normalized: Dict[str, int] = {}
    for k, count in raw_counts.items():
        if count is None:
            continue
        try:
            int_count = int(count)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid count for denomination {k}: {count}")

        if int_count < 0:
            raise ValueError(f"Requested count cannot be negative for denomination {k}")

        denom_str = None
        if isinstance(k, int) or (isinstance(k, str) and k.isdigit()):
            int_val = int(k)
            if int_val in val_to_denom:
                denom_str = val_to_denom[int_val]
        elif isinstance(k, str) and k in denom_to_val:
            denom_str = k

        if not denom_str:
            raise ValueError(f"Unsupported denomination: {k}")

        normalized[denom_str] = normalized.get(denom_str, 0) + int_count

    return normalized


def plan_payout(
    service_type: str,
    payout_amount: int,
    available_bills: Dict[str, int],
    available_coins: Dict[str, int],
    requested_counts: Optional[Dict[str | int, int]] = None,
) -> PlannerResult:
    """Compute exact payout plan using bounded dynamic programming.

    Args:
        service_type: "bill-to-bill", "bill-to-coin", or "coin-to-bill"
        payout_amount: Payout amount in integer pesos.
        available_bills: Dict of available bill counts (e.g. {"PHP_100": 5}).
        available_coins: Dict of available coin counts (e.g. {"PHP_5": 20}).
        requested_counts: Optional partial/complete breakdown requests.

    Returns:
        PlannerResult with typed items, substitution flag, or machine-readable failure.
    """
    if payout_amount <= 0:
        return PlannerResult(
            success=False,
            total_payout=payout_amount,
            reason_code="INVALID_PAYOUT_AMOUNT",
            reason=f"Payout amount must be positive, got {payout_amount}",
        )

    # Determine permitted denominations and capacities based on service type
    if service_type in {"bill-to-bill", "coin-to-bill"}:
        permitted = PHP_BILL_DENOMINATIONS
        denom_type = "bill"
        stock = available_bills
        command_limit = MAX_BILL_PER_DENOM
    elif service_type == "bill-to-coin":
        permitted = PHP_COIN_DENOMINATIONS
        denom_type = "coin"
        stock = available_coins
        command_limit = MAX_COIN_PER_DENOM
    else:
        return PlannerResult(
            success=False,
            reason_code="UNSUPPORTED_SERVICE_TYPE",
            reason=f"Unknown service type: {service_type}",
        )

    # Validate and normalize requested counts
    try:
        norm_requested = normalize_requested_counts(requested_counts, permitted)
    except ValueError as e:
        return PlannerResult(
            success=False,
            reason_code="INVALID_PARAM",
            reason=str(e),
        )

    # Check command limits on requested counts
    for denom, count in norm_requested.items():
        if count > command_limit:
            return PlannerResult(
                success=False,
                reason_code="EXCEEDS_COMMAND_LIMIT",
                reason=f"Requested count {count} for {denom} exceeds limit of {command_limit}",
            )

    # Check requested total does not exceed payout amount
    requested_total = sum(
        count * next(v for d, v in permitted if d == denom)
        for denom, count in norm_requested.items()
    )
    if requested_total > payout_amount:
        return PlannerResult(
            success=False,
            reason_code="REQUESTED_EXCEEDS_PAYOUT",
            reason=f"Requested breakdown total ₱{requested_total} exceeds payout amount ₱{payout_amount}",
        )

    # Build bounds for each denomination
    # Bound is min(stock, command_limit)
    bounds = []
    for denom, val in permitted:
        avail = max(
            0,
            stock.get(
                denom,
                stock.get(denom.replace("PHP_", ""), stock.get(str(val), 0)),
            ),
        )
        limit = min(avail, command_limit)
        req = norm_requested.get(denom, 0)
        bounds.append((denom, val, limit, req))

    # Total theoretical capacity check
    max_possible_val = sum(limit * val for _, val, limit, _ in bounds)
    if max_possible_val < payout_amount:
        return PlannerResult(
            success=False,
            total_payout=payout_amount,
            reason_code="INSUFFICIENT_INVENTORY",
            reason=f"Insufficient machine stock to dispense ₱{payout_amount}",
        )

    # Bounded DP search to find exact breakdown minimizing candidate ordering tuple:
    # (unpreserved_value, unpreserved_units, total_pieces, -c_1, -c_2, ..., -c_k)
    k = len(bounds)
    memo: Dict[Tuple[int, int], Optional[Tuple[Tuple, Dict[str, int]]]] = {}

    def dp(idx: int, rem_amount: int) -> Optional[Tuple[Tuple, Dict[str, int]]]:
        if rem_amount == 0:
            # Remaining denoms have count 0
            unpres_val = 0
            unpres_units = 0
            tie_breakers = []
            chosen = {}
            for j in range(idx, k):
                _, val_j, _, req_j = bounds[j]
                unpres_val += val_j * req_j
                unpres_units += req_j
                tie_breakers.append(0)
            return (unpres_val, unpres_units, 0, tuple(tie_breakers)), chosen

        if idx >= k:
            return None

        state_key = (idx, rem_amount)
        if state_key in memo:
            return memo[state_key]

        denom, val, limit, req = bounds[idx]
        max_c = min(limit, rem_amount // val)
        best_solution = None

        for c in range(max_c, -1, -1):
            sub = dp(idx + 1, rem_amount - c * val)
            if sub is not None:
                sub_score, sub_counts = sub
                # Loss from this denomination
                loss_units = max(0, req - c)
                loss_val = val * loss_units

                score = (
                    sub_score[0] + loss_val,
                    sub_score[1] + loss_units,
                    sub_score[2] + c,
                    (-c,) + sub_score[3],
                )

                if best_solution is None or score < best_solution[0]:
                    merged_counts = dict(sub_counts)
                    if c > 0:
                        merged_counts[denom] = c
                    best_solution = (score, merged_counts)

        memo[state_key] = best_solution
        return best_solution

    result = dp(0, payout_amount)

    if result is None:
        # Check if the failure is due to command limit or no exact combination
        return PlannerResult(
            success=False,
            total_payout=payout_amount,
            reason_code="NO_EXACT_COMBINATION",
            reason=f"No exact combination of available denominations can dispense ₱{payout_amount}",
        )

    _, chosen_counts = result

    # Check whether substitution occurred:
    # A quantity below the request is a substitution.
    # An actual quantity greater than requested when filling remainder is NOT a substitution.
    is_substitution = False
    for denom, req_count in norm_requested.items():
        actual_count = chosen_counts.get(denom, 0)
        if actual_count < req_count:
            is_substitution = True
            break

    substitution_notice = None
    if is_substitution:
        substitution_notice = (
            "Due to current stock availability, your selected breakdown has been revised to an exact equivalent."
        )

    # Build PayoutItem list in order of permitted denominations
    items = []
    for denom, val in permitted:
        count = chosen_counts.get(denom, 0)
        if count > 0:
            items.append(
                PayoutItem(
                    denom=denom,
                    denom_type=denom_type,
                    count=count,
                    value=val,
                )
            )

    return PlannerResult(
        success=True,
        items=items,
        total_payout=payout_amount,
        requested_counts=norm_requested,
        is_substitution=is_substitution,
        substitution_notice=substitution_notice,
    )
