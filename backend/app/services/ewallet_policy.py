"""Pure cash-in feasibility and shared e-wallet business rules."""
from functools import wraps
import asyncio

from app.services.change_calculator import calculate_change

POLICY_VERSION = "ewallet-2026-09-v1"
TERMINAL = {"COMPLETE", "CANCELLED", "FAILED", "RESOLVED", "ABANDONED_RETAINED"}
INTAKE = {"ACCEPTING_CASH", "CASH_ACCEPTED"}
BILLS = (20, 50, 100, 200, 500, 1000)
COINS = (1, 5, 10, 20)
TRANSITIONS = {
    "CREATED": {"WAITING_FOR_PAYMENT", "CANCELLATION_PENDING", "CLAIM_REQUIRED"},
    "ACCEPTING_CASH": {"CASH_ACCEPTED", "CANCELLED", "ABANDONED_RETAINED", "CLAIM_REQUIRED"},
    "CASH_ACCEPTED": {"SUBMISSION_UNKNOWN", "CLAIM_REQUIRED"},
    "SUBMISSION_UNKNOWN": {"DISBURSEMENT_PENDING", "CLAIM_REQUIRED"},
    "DISBURSEMENT_PENDING": {"CHANGE_PENDING", "COMPLETE", "CLAIM_REQUIRED"},
    "CHANGE_PENDING": {"DISPENSING", "COMPLETE", "CLAIM_REQUIRED"},
    "WAITING_FOR_PAYMENT": {"PAYMENT_CONFIRMED", "CANCELLATION_PENDING", "CLAIM_REQUIRED"},
    "PAYMENT_CONFIRMED": {"DISPENSING", "CANCELLATION_PENDING", "CLAIM_REQUIRED"},
    "DISPENSING": {"PAYMENT_CONFIRMED", "CHANGE_PENDING", "COMPLETE", "CANCELLATION_PENDING", "CLAIM_REQUIRED"},
    "CANCELLATION_PENDING": {"WAITING_FOR_PAYMENT", "CANCELLED", "CLAIM_REQUIRED"},
    "CANCELLED": {"CLAIM_REQUIRED"},
    "CLAIM_REQUIRED": {"RESOLVED"},
}


def serialized(method):
    """Serialize kiosk money mutations, allowing same-task nested operations."""
    @wraps(method)
    async def wrapped(self, *args, **kwargs):
        task = asyncio.current_task()
        if self._mutation_owner is task:
            return await method(self, *args, **kwargs)
        async with self._mutation_lock:
            self._mutation_owner = task
            try:
                return await method(self, *args, **kwargs)
            finally:
                self._mutation_owner = None
    return wrapped


def intake_options(remaining, coins, bills, allow_coins=True):
    """Reachability under controllable bills and uncontrollable coin values.

    Coin intake is safe only if ALL possible next coins have a safe continuation.
    Larger positive balances depend only on smaller balances, avoiding recursion.
    """
    change = {}
    for amount in range(21):
        try:
            change[amount] = calculate_change(amount, {}, coins)
        except Exception:
            pass
    if isinstance(bills, dict):
        # With finite storage, a bill path must fit the remaining slots. Coin
        # paths are deliberately conservative: every possible excess 0..19
        # must be supported, so no later coin value can strand the customer.
        coin_safe = allow_coins and all(amount in change for amount in range(20))
        def can_finish(balance, slots):
            if balance <= 0:
                return -balance in change
            if coin_safe:
                return True
            reachable_bits = 1
            mask = (1 << (balance + 21)) - 1
            for value, stock in slots.items():
                left, chunk = min(stock, (balance + 20) // value), 1
                while left > 0:
                    count = min(chunk, left)
                    reachable_bits |= reachable_bits << (count * value)
                    reachable_bits &= mask
                    left -= count
                    chunk *= 2
            return any((reachable_bits >> (balance + excess)) & 1 for excess in change)
        allowed = []
        for value, stock in bills.items():
            if stock > 0 and remaining > 0:
                slots = {**bills, value: stock - 1}
                if can_finish(remaining - value, slots):
                    allowed.append(value)
        return {"bills": allowed, "coins_enabled": remaining > 0 and coin_safe}, change
    reachable = {r: -r in change for r in range(-20, 1)}
    choices = {}
    for r in range(1, max(0, remaining) + 1):
        allowed = [v for v in bills if reachable.get(r - v, False)]
        coin_safe = allow_coins and all(reachable.get(r - v, False) for v in COINS)
        reachable[r] = bool(allowed) or coin_safe
        choices[r] = {"bills": allowed, "coins_enabled": coin_safe}
    return choices.get(remaining, {"bills": [], "coins_enabled": False}), change
