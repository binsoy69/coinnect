"""Forex conversion calculator.

Computes how much to dispense in the target currency given
an input amount, exchange rate, and fee.
"""

import logging
from typing import Dict, List, Optional

from app.core.constants import Currency
from app.models.forex import ForexQuote
from app.services.change_calculator import DispensePlan, calculate_change

logger = logging.getLogger(__name__)


def calculate_forex_dispense(
    quote: ForexQuote,
    bill_inventory: Dict[str, int],
    coin_inventory: Dict[str, int],
    preferred_denoms: Optional[List[int]] = None,
) -> DispensePlan:
    """Calculate a dispense plan for a forex transaction.

    This delegates to the existing calculate_change() function
    but filters inventory to only include denominations of the
    target currency.

    Args:
        quote: The locked forex quote with conversion details.
        bill_inventory: Current bill dispenser counts (e.g., {"PHP_100": 50}).
        coin_inventory: Current coin counts (e.g., {"PHP_5": 100}).
        preferred_denoms: User-selected denominations for dispensing.

    Returns:
        DispensePlan with items to dispense.

    Raises:
        InsufficientInventoryError: If the amount cannot be dispensed.
    """
    output_amount = int(quote.output_amount)
    to_currency = Currency(quote.to_currency)

    if to_currency == Currency.PHP:
        # Dispensing PHP: use PHP bills + PHP coins
        php_bills = {
            k: v for k, v in bill_inventory.items()
            if k.startswith("PHP_")
        }
        return calculate_change(
            output_amount,
            php_bills,
            coin_inventory,
            preferred_denoms=preferred_denoms,
            currency="PHP",
        )
    else:
        # Dispensing foreign currency: use only foreign bills, no coins
        prefix = f"{to_currency.value}_"
        foreign_bills = {
            k: v for k, v in bill_inventory.items()
            if k.startswith(prefix)
        }
        return calculate_change(
            output_amount,
            foreign_bills,
            {},  # No coins for foreign currencies
            preferred_denoms=preferred_denoms,
            currency=to_currency.value,
        )
