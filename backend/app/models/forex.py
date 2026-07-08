"""Pydantic models for forex data."""

from datetime import datetime, timezone
from typing import Dict, Optional

from pydantic import BaseModel


class ExchangeRate(BaseModel):
    """A single exchange rate entry."""

    base: str  # e.g., "USD"
    target: str  # e.g., "PHP"
    rate: float  # e.g., 58.7656
    fetched_at: datetime
    expires_at: datetime


class ExchangeRateCache(BaseModel):
    """Cached exchange rates."""

    rates: Dict[str, float] = {}  # e.g., {"USD": 58.7656, "EUR": 61.7246}
    fetched_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    @property
    def is_valid(self) -> bool:
        if not self.fetched_at or not self.expires_at:
            return False
        return datetime.now(timezone.utc).replace(tzinfo=None) < self.expires_at

    @property
    def is_expired(self) -> bool:
        return not self.is_valid


class ForexQuote(BaseModel):
    """A forex conversion quote with locked rate."""

    from_currency: str
    to_currency: str
    rate: float
    input_amount: float  # Amount in source currency
    converted_amount: float  # Amount in target currency (before fee)
    fee_percentage: float
    fee_amount: float  # Fee in target currency
    output_amount: float  # Final amount after fee (what user receives)
    locked_at: datetime


class ForexTransactionRequest(BaseModel):
    """Request to start a forex transaction."""

    service_type: str  # e.g., "usd-to-php"
    selected_amount: int  # Foreign currency amount selected by user
    selected_dispense_denoms: list = []


class ForexRateResponse(BaseModel):
    """Response with current exchange rates."""

    rates: Dict[str, float]  # {"USD": 58.7656, "EUR": 61.7246}
    fetched_at: Optional[str] = None
    valid: bool = False
    fees: Dict[str, float] = {}  # {"usd-to-php": 5.0, ...}
