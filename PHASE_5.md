# Phase 5: Foreign Exchange - Implementation Plan

> **Goal**: Accept USD/EUR bills and dispense PHP (and vice versa) using live exchange rates from Abstract API.
> **Prerequisite**: Phase 3 (Money Changer) complete. Phase 2 infrastructure (serial, WS, REST) in place.
> **Online Requirement**: Forex is **strictly online-only**. If the kiosk has no internet, forex is blocked entirely.

---

## Table of Contents

1. [Architecture Decisions](#1-architecture-decisions)
2. [Implementation Steps Overview](#2-implementation-steps-overview)
3. [Step 1: Backend Configuration & Models ✅](#step-1-backend-configuration--models)
4. [Step 2: Forex Rate Service ✅](#step-2-forex-rate-service)
5. [Step 3: Forex Change Calculator ✅](#step-3-forex-change-calculator)
6. [Step 4: Multi-Currency Bill Authentication ✅](#step-4-multi-currency-bill-authentication)
7. [Step 5: Forex Transaction Orchestrator ✅](#step-5-forex-transaction-orchestrator)
8. [Step 6: REST API Endpoints ✅](#step-6-rest-api-endpoints)
9. [Step 7: WebSocket Events ✅](#step-7-websocket-events)
10. [Step 8: Frontend Backend Integration ✅](#step-8-frontend-backend-integration)
11. [Step 9: Tests ✅](#step-9-tests)
12. [File Change Summary](#file-change-summary)
13. [Dependency Graph](#dependency-graph)

---

## 1. Architecture Decisions

These decisions were confirmed with the project owner:

| Decision | Choice | Rationale |
|---|---|---|
| Rate API provider | **Abstract API** | Free plan available, simple JSON response |
| Orchestrator pattern | **Separate `ForexTransactionOrchestrator`** | Forex has different flow (rate locking, currency conversion, online requirement) |
| ML model strategy | **Separate models per currency** | Different `.pt` files per currency (PHP, USD, EUR). More modular. |
| Online requirement | **Strict online only** | Require active internet. Block forex entirely when offline. |
| Fee configuration | **Configurable per currency pair** | Store fee % per pair in backend config/env. Admin-adjustable. |
| Persistence | **Extend existing `TransactionRecord`** | Add forex-specific fields. Reuse WAL for crash recovery. |

---

## 2. Implementation Steps Overview

```
Step 1: Backend Configuration & Models ........... (foundation)
Step 2: Forex Rate Service ....................... (external API)
Step 3: Forex Change Calculator .................. (conversion math)
Step 4: Multi-Currency Bill Authentication ....... (ML updates)
Step 5: Forex Transaction Orchestrator ........... (core logic)
Step 6: REST API Endpoints ....................... (HTTP layer)
Step 7: WebSocket Events ......................... (real-time)
Step 8: Frontend Backend Integration ............. (hook up UI)
Step 9: Tests .................................... (verification)
```

Steps 1-3 can be developed in parallel. Steps 4-5 depend on 1-3. Steps 6-7 depend on 5. Step 8 depends on 6-7.

---

## Step 1: Backend Configuration & Models ✅ DONE

### 1.1 Update `backend/app/core/config.py`

Add these fields to the `Settings` class:

```python
# --- ADD AFTER existing settings (line ~66, before model_config) ---

# Forex
forex_api_key: str = ""  # Abstract API key
forex_api_url: str = "https://exchange-rates.abstractapi.com/v1/live/"
forex_cache_ttl_seconds: int = 86400  # 24 hours
forex_rate_refresh_interval: int = 3600  # Auto-refresh every 1 hour

# Forex fees (percentage per currency pair)
forex_fee_usd_to_php: float = 5.0
forex_fee_php_to_usd: float = 5.0
forex_fee_eur_to_php: float = 5.0
forex_fee_php_to_eur: float = 5.0

# Forex connectivity
forex_connectivity_check_url: str = "https://exchange-rates.abstractapi.com"
forex_connectivity_timeout: int = 5  # seconds

# ML models per currency
yolo_auth_model_path_usd: str = "models/auth_usd.pt"
yolo_denom_model_path_usd: str = "models/denom_usd.pt"
yolo_auth_model_path_eur: str = "models/auth_eur.pt"
yolo_denom_model_path_eur: str = "models/denom_eur.pt"
```

### 1.2 Add forex constants to `backend/app/core/constants.py`

Add after the existing enums (after line ~122):

```python
class Currency(str, Enum):
    PHP = "PHP"
    USD = "USD"
    EUR = "EUR"


class ForexServiceType(str, Enum):
    USD_TO_PHP = "usd-to-php"
    PHP_TO_USD = "php-to-usd"
    EUR_TO_PHP = "eur-to-php"
    PHP_TO_EUR = "php-to-eur"


# Currency pair -> (from_currency, to_currency)
FOREX_PAIRS: Dict[ForexServiceType, tuple] = {
    ForexServiceType.USD_TO_PHP: (Currency.USD, Currency.PHP),
    ForexServiceType.PHP_TO_USD: (Currency.PHP, Currency.USD),
    ForexServiceType.EUR_TO_PHP: (Currency.EUR, Currency.PHP),
    ForexServiceType.PHP_TO_EUR: (Currency.PHP, Currency.EUR),
}

# Which BillDenom values belong to each currency
CURRENCY_BILL_DENOMS: Dict[Currency, list] = {
    Currency.PHP: [BillDenom.PHP_20, BillDenom.PHP_50, BillDenom.PHP_100,
                   BillDenom.PHP_200, BillDenom.PHP_500, BillDenom.PHP_1000],
    Currency.USD: [BillDenom.USD_10, BillDenom.USD_50, BillDenom.USD_100],
    Currency.EUR: [BillDenom.EUR_5, BillDenom.EUR_10, BillDenom.EUR_20],
}

# Bill denomination -> currency
BILL_DENOM_CURRENCY: Dict[BillDenom, Currency] = {}
for _curr, _denoms in CURRENCY_BILL_DENOMS.items():
    for _d in _denoms:
        BILL_DENOM_CURRENCY[_d] = _curr
```

### 1.3 Update `backend/app/models/db_models.py`

Add a new `TransactionType` enum value and new columns to `TransactionRecord`.

Add to `TransactionType` enum:

```python
class TransactionType(str, enum.Enum):
    BILL_TO_BILL = "bill-to-bill"
    BILL_TO_COIN = "bill-to-coin"
    COIN_TO_BILL = "coin-to-bill"
    # --- ADD ---
    FOREX_USD_TO_PHP = "forex-usd-to-php"
    FOREX_PHP_TO_USD = "forex-php-to-usd"
    FOREX_EUR_TO_PHP = "forex-eur-to-php"
    FOREX_PHP_TO_EUR = "forex-php-to-eur"
```

Add new WAL action:

```python
class WALAction(str, enum.Enum):
    # ... existing ...
    FOREX_RATE_LOCKED = "FOREX_RATE_LOCKED"
    FOREX_CONVERSION_START = "FOREX_CONVERSION_START"
```

Add new columns to `TransactionRecord` (after `selected_dispense_denoms`):

```python
    # Forex-specific fields (nullable for non-forex transactions)
    from_currency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    to_currency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    exchange_rate: Mapped[Optional[float]] = mapped_column(nullable=True)
    rate_locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    forex_fee_percentage: Mapped[Optional[float]] = mapped_column(nullable=True)
    converted_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Amount in target currency before fee
```

### 1.4 Update `backend/app/models/events.py`

Add new forex-specific WebSocket event types to `WSEventType`:

```python
    # --- ADD: Phase 5 forex events ---
    FOREX_RATE_UPDATE = "FOREX_RATE_UPDATE"
    FOREX_RATE_LOCKED = "FOREX_RATE_LOCKED"
    FOREX_CONNECTIVITY_CHANGED = "FOREX_CONNECTIVITY_CHANGED"
    FOREX_CONVERSION_COMPLETE = "FOREX_CONVERSION_COMPLETE"
```

### 1.5 Create `backend/app/models/forex.py` (NEW FILE)

Pydantic models for forex-specific data:

```python
"""Pydantic models for forex data."""

from datetime import datetime
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
    rates: Dict[str, float] = {}  # e.g., {"USD": 58.7656, "EUR": 61.7246} (all relative to PHP)
    fetched_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    @property
    def is_valid(self) -> bool:
        if not self.fetched_at or not self.expires_at:
            return False
        return datetime.utcnow() < self.expires_at

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
    selected_dispense_denoms: list = []  # Denominations for dispensing


class ForexRateResponse(BaseModel):
    """Response with current exchange rates."""
    rates: Dict[str, float]  # {"USD": 58.7656, "EUR": 61.7246}
    fetched_at: Optional[str] = None
    valid: bool = False
    fees: Dict[str, float] = {}  # {"usd-to-php": 5.0, "php-to-usd": 5.0, ...}
```

### 1.6 Add forex error types to `backend/app/core/errors.py`

```python
class ForexError(CoinnectError):
    """Forex-specific error."""
    def __init__(self, message: str, code: str = "FOREX_ERROR"):
        self.code = code
        super().__init__(message)


class ConnectivityError(CoinnectError):
    """No internet connectivity."""
    def __init__(self, message: str = "No internet connectivity"):
        super().__init__(message)


class RateExpiredError(ForexError):
    """Exchange rate has expired."""
    def __init__(self):
        super().__init__("Exchange rate has expired", "RATE_EXPIRED")


class RateUnavailableError(ForexError):
    """Cannot fetch exchange rates."""
    def __init__(self, message: str = "Exchange rates unavailable"):
        super().__init__(message, "RATE_UNAVAILABLE")
```

---

## Step 2: Forex Rate Service ✅ DONE

### 2.1 Create `backend/app/services/forex_rate_service.py` (NEW FILE)

This service fetches rates from Abstract API, caches them locally, and provides rate-locking for transactions.

```python
"""Forex rate service using Abstract API with local caching.

Responsibilities:
- Fetch live rates from Abstract API
- Cache rates locally (24h TTL)
- Provide rate locking for transactions
- Check internet connectivity
- Broadcast rate updates via WebSocket
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import httpx

from app.api.ws import ConnectionManager
from app.core.config import Settings
from app.core.constants import Currency, ForexServiceType, FOREX_PAIRS
from app.core.errors import ConnectivityError, RateExpiredError, RateUnavailableError
from app.models.events import WSEvent, WSEventType
from app.models.forex import ExchangeRateCache, ForexQuote

logger = logging.getLogger(__name__)


class ForexRateService:
    """Manages exchange rates with caching and connectivity checks.

    Usage:
        service = ForexRateService(settings, ws_manager)
        await service.start()  # Begin periodic refresh
        rate = service.get_rate("USD")  # Get USD->PHP rate
        quote = service.get_quote("usd-to-php", 100)  # Get conversion quote
        await service.stop()
    """

    def __init__(self, settings: Settings, ws_manager: ConnectionManager):
        self._settings = settings
        self._ws = ws_manager
        self._cache = ExchangeRateCache()
        self._is_online: bool = False
        self._refresh_task: Optional[asyncio.Task] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def is_online(self) -> bool:
        return self._is_online

    @property
    def rates_valid(self) -> bool:
        return self._cache.is_valid

    @property
    def current_rates(self) -> Dict[str, float]:
        return dict(self._cache.rates)

    async def start(self) -> None:
        """Start the rate service: initial fetch + periodic refresh."""
        self._http_client = httpx.AsyncClient(timeout=10.0)
        await self._check_connectivity()
        if self._is_online:
            await self._fetch_rates()
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info("ForexRateService started")

    async def stop(self) -> None:
        """Stop the rate service."""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        if self._http_client:
            await self._http_client.aclose()
        logger.info("ForexRateService stopped")

    async def check_forex_available(self) -> bool:
        """Check if forex transactions are currently possible.

        Returns True only if online AND rates are valid.
        """
        await self._check_connectivity()
        return self._is_online

    def get_rate(self, currency: str) -> float:
        """Get the current exchange rate for currency -> PHP.

        Args:
            currency: "USD" or "EUR"

        Returns:
            Rate as float (e.g., 58.7656 means 1 USD = 58.7656 PHP)

        Raises:
            RateUnavailableError: If no valid cached rate exists.
        """
        if not self._cache.is_valid:
            raise RateUnavailableError()
        rate = self._cache.rates.get(currency)
        if rate is None:
            raise RateUnavailableError(f"No rate available for {currency}")
        return rate

    def get_fee_percentage(self, service_type: str) -> float:
        """Get the configured fee percentage for a forex service type.

        Args:
            service_type: e.g., "usd-to-php"

        Returns:
            Fee percentage (e.g., 5.0)
        """
        fee_map = {
            ForexServiceType.USD_TO_PHP: self._settings.forex_fee_usd_to_php,
            ForexServiceType.PHP_TO_USD: self._settings.forex_fee_php_to_usd,
            ForexServiceType.EUR_TO_PHP: self._settings.forex_fee_eur_to_php,
            ForexServiceType.PHP_TO_EUR: self._settings.forex_fee_php_to_eur,
        }
        try:
            return fee_map[ForexServiceType(service_type)]
        except (ValueError, KeyError):
            return 5.0  # Default

    def get_quote(self, service_type: str, amount: int) -> ForexQuote:
        """Calculate a forex conversion quote.

        Args:
            service_type: e.g., "usd-to-php" or "php-to-usd"
            amount: The selected amount (in the foreign currency for both directions)

        Returns:
            ForexQuote with all conversion details.

        Raises:
            RateUnavailableError: If rates are not available.
        """
        if not self._cache.is_valid:
            raise RateUnavailableError()

        pair = FOREX_PAIRS.get(ForexServiceType(service_type))
        if not pair:
            raise RateUnavailableError(f"Unknown service type: {service_type}")

        from_currency, to_currency = pair
        fee_pct = self.get_fee_percentage(service_type)

        if from_currency == Currency.PHP:
            # PHP -> Foreign: user selects foreign amount to receive
            foreign_currency = to_currency.value
            php_per_foreign = self.get_rate(foreign_currency)
            # How much PHP does the user need to insert?
            php_equivalent = amount * php_per_foreign
            fee_amount = round(php_equivalent * (fee_pct / 100))
            total_php_due = round(php_equivalent) + fee_amount

            return ForexQuote(
                from_currency=from_currency.value,
                to_currency=to_currency.value,
                rate=round(1 / php_per_foreign, 6),  # PHP->Foreign rate
                input_amount=total_php_due,  # PHP user must insert
                converted_amount=round(php_equivalent),
                fee_percentage=fee_pct,
                fee_amount=fee_amount,
                output_amount=amount,  # Foreign amount to dispense
                locked_at=datetime.utcnow(),
            )
        else:
            # Foreign -> PHP: user selects foreign amount to insert
            foreign_currency = from_currency.value
            php_per_foreign = self.get_rate(foreign_currency)
            php_equivalent = amount * php_per_foreign
            fee_amount = round(php_equivalent * (fee_pct / 100))
            output_php = round(php_equivalent) - fee_amount

            return ForexQuote(
                from_currency=from_currency.value,
                to_currency=to_currency.value,
                rate=php_per_foreign,
                input_amount=amount,  # Foreign amount user inserts
                converted_amount=round(php_equivalent),
                fee_percentage=fee_pct,
                fee_amount=fee_amount,
                output_amount=output_php,  # PHP to dispense
                locked_at=datetime.utcnow(),
            )

    async def _check_connectivity(self) -> None:
        """Check internet connectivity by pinging the API host."""
        was_online = self._is_online
        try:
            resp = await self._http_client.head(
                self._settings.forex_connectivity_check_url,
                timeout=self._settings.forex_connectivity_timeout,
            )
            self._is_online = resp.status_code < 500
        except Exception:
            self._is_online = False

        if was_online != self._is_online:
            logger.info(f"Forex connectivity: {'online' if self._is_online else 'offline'}")
            event = WSEvent(
                type=WSEventType.FOREX_CONNECTIVITY_CHANGED,
                payload={"online": self._is_online},
            )
            await self._ws.broadcast(event)

    async def _fetch_rates(self) -> None:
        """Fetch live rates from Abstract API.

        Abstract API endpoint:
          GET https://exchange-rates.abstractapi.com/v1/live/
              ?api_key=YOUR_KEY&base=PHP&target=USD,EUR

        We request PHP as base, so we get PHP->USD and PHP->EUR.
        We store the inverse (USD->PHP, EUR->PHP) for convenience.
        """
        try:
            resp = await self._http_client.get(
                self._settings.forex_api_url,
                params={
                    "api_key": self._settings.forex_api_key,
                    "base": "PHP",
                    "target": "USD,EUR",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # Abstract API returns: {"base": "PHP", "exchange_rates": {"USD": 0.017, "EUR": 0.016}}
            exchange_rates = data.get("exchange_rates", {})

            # Store as foreign->PHP rates (inverse of what API gives us)
            rates = {}
            for currency_code, php_to_foreign in exchange_rates.items():
                if php_to_foreign > 0:
                    rates[currency_code] = round(1 / php_to_foreign, 4)

            now = datetime.utcnow()
            self._cache = ExchangeRateCache(
                rates=rates,
                fetched_at=now,
                expires_at=now + timedelta(seconds=self._settings.forex_cache_ttl_seconds),
            )

            logger.info(f"Forex rates updated: {rates}")

            # Broadcast rate update
            event = WSEvent(
                type=WSEventType.FOREX_RATE_UPDATE,
                payload={
                    "rates": rates,
                    "fetched_at": now.isoformat(),
                    "valid": True,
                },
            )
            await self._ws.broadcast(event)

        except Exception as e:
            logger.error(f"Failed to fetch forex rates: {e}")

    async def _refresh_loop(self) -> None:
        """Periodically refresh rates and check connectivity."""
        while True:
            await asyncio.sleep(self._settings.forex_rate_refresh_interval)
            try:
                await self._check_connectivity()
                if self._is_online:
                    await self._fetch_rates()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Rate refresh error: {e}")
```

### 2.2 Add `httpx` dependency

Add to `backend/requirements.txt`:

```
httpx>=0.27.0
```

---

## Step 3: Forex Change Calculator ✅ DONE

### 3.1 Create `backend/app/services/forex_change_calculator.py` (NEW FILE)

Handles the conversion math and dispense plan calculation for forex transactions.

```python
"""Forex conversion calculator.

Computes how much to dispense in the target currency given
an input amount, exchange rate, and fee.
"""

import logging
from typing import Dict, List, Optional

from app.core.constants import (
    BILL_DENOM_VALUES,
    BillDenom,
    Currency,
    CURRENCY_BILL_DENOMS,
    ForexServiceType,
    FOREX_PAIRS,
)
from app.models.forex import ForexQuote
from app.services.change_calculator import DispensePlan, DispenseItem, calculate_change

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
        bill_inventory: Current bill dispenser counts (protocol keys, e.g., {"PHP_100": 50}).
        coin_inventory: Current coin counts (e.g., {"PHP_5": 100}).
        preferred_denoms: User-selected denominations for dispensing.

    Returns:
        DispensePlan with items to dispense.

    Raises:
        ValueError: If the amount cannot be dispensed.
    """
    output_amount = int(quote.output_amount)
    to_currency = Currency(quote.to_currency)

    if to_currency == Currency.PHP:
        # Dispensing PHP: use PHP bills + PHP coins
        # Filter bill inventory to PHP only
        php_bills = {
            k: v for k, v in bill_inventory.items()
            if k.startswith("PHP_")
        }
        return calculate_change(
            output_amount,
            php_bills,
            coin_inventory,
            preferred_denoms=preferred_denoms,
        )
    else:
        # Dispensing foreign currency: use only foreign bills, no coins
        prefix = f"{to_currency.value}_"
        foreign_bills = {
            k: v for k, v in bill_inventory.items()
            if k.startswith(prefix)
        }
        # No coin dispensing for foreign currencies
        return calculate_change(
            output_amount,
            foreign_bills,
            {},  # No coins for foreign currencies
            preferred_denoms=preferred_denoms,
        )
```

---

## Step 4: Multi-Currency Bill Authentication ✅ DONE

### 4.1 Update `backend/app/ml/bill_authenticator.py`

The existing `BillAuthenticatorBase` abstract class and `YOLOBillAuthenticator` need to support currency-specific models.

**Current interface** (in `bill_authenticator.py`):

```python
class BillAuthenticatorBase(ABC):
    @abstractmethod
    async def authenticate(self, image) -> AuthResult: ...
    @abstractmethod
    async def identify_denomination(self, image) -> DenomResult: ...
```

**Changes needed**:

1. Add a `set_currency(currency: str)` method to switch between models.
2. `YOLOBillAuthenticator` loads all models on init but switches the active model pair based on expected currency.

**Updated `YOLOBillAuthenticator.__init__`**:

```python
def __init__(self, settings: Settings):
    self._confidence_threshold = settings.yolo_confidence_threshold
    # PHP models (default)
    self._models = {
        "PHP": {
            "auth": self._load_model(settings.yolo_auth_model_path),
            "denom": self._load_model(settings.yolo_denom_model_path),
        },
        "USD": {
            "auth": self._load_model(settings.yolo_auth_model_path_usd),
            "denom": self._load_model(settings.yolo_denom_model_path_usd),
        },
        "EUR": {
            "auth": self._load_model(settings.yolo_auth_model_path_eur),
            "denom": self._load_model(settings.yolo_denom_model_path_eur),
        },
    }
    self._active_currency = "PHP"

def set_currency(self, currency: str) -> None:
    """Switch to models for the given currency."""
    if currency not in self._models:
        raise ValueError(f"No models available for currency: {currency}")
    self._active_currency = currency

def _get_active_models(self):
    return self._models[self._active_currency]
```

The `authenticate()` and `identify_denomination()` methods use `self._get_active_models()` to get the correct model pair.

### 4.2 Update `backend/app/ml/mock_authenticator.py`

Add `set_currency()` method to `MockBillAuthenticator`:

```python
def set_currency(self, currency: str) -> None:
    """Set the expected currency for mock auth."""
    self._currency = currency

# Update set_next_denomination to validate currency matches
```

### 4.3 Update `backend/app/services/bill_acceptor.py`

Add a method to set the expected currency before starting a forex acceptance cycle:

```python
def set_expected_currency(self, currency: str) -> None:
    """Configure the bill acceptor to expect a specific currency.

    Switches the ML model to the appropriate currency-specific model.

    Args:
        currency: "PHP", "USD", or "EUR"
    """
    if hasattr(self._auth, "set_currency"):
        self._auth.set_currency(currency)
    self._expected_currency = currency
```

Also update `accept_bill()` to validate the detected denomination matches the expected currency:

```python
# After denomination identification, validate currency matches
detected_currency = BILL_DENOM_CURRENCY.get(denom_result.denomination)
if self._expected_currency and detected_currency != Currency(self._expected_currency):
    # Wrong currency inserted - reject
    await self._eject_bill()
    return BillAcceptResult(
        success=False,
        error=f"Expected {self._expected_currency} bill, got {detected_currency.value}",
    )
```

---

## Step 5: Forex Transaction Orchestrator ✅ DONE

### 5.1 Create `backend/app/services/forex_transaction_orchestrator.py` (NEW FILE)

This is the core of Phase 5. It mirrors the pattern of `TransactionOrchestrator` but handles the forex-specific flow.

**Transaction Flow**:

```
1. User selects forex service (e.g., USD→PHP)
2. Backend checks connectivity → fetches/validates rates
3. Backend creates ForexQuote (locks rate)
4. Backend pre-checks dispense capability
5. Transaction created (DB record + state machine)
6. State: WAITING_FOR_BILL
   - Bill acceptor configured for expected currency (USD/EUR/PHP)
   - User inserts bills
   - Each bill: authenticate → sort → update inserted amount
7. When enough inserted → State: WAITING_FOR_CONFIRMATION
8. User confirms → State: DISPENSING
   - Calculate dispense plan for target currency
   - Execute dispense (bills + coins for PHP, bills only for foreign)
9. State: COMPLETE or ERROR (with claim ticket if partial)
```

```python
"""Forex transaction orchestrator.

Coordinates forex-specific transaction lifecycle:
rate fetching, rate locking, multi-currency bill acceptance,
conversion calculation, and dispensing in the target currency.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.ws import ConnectionManager
from app.core.constants import (
    BillDenom,
    Currency,
    ForexServiceType,
    FOREX_PAIRS,
    BILL_DENOM_CURRENCY,
    BILL_DENOM_VALUES,
)
from app.core.errors import ConnectivityError, ForexError, TransactionError
from app.models.db_models import TransactionRecord, TransactionState, WALEntry, WALStatus, WALAction
from app.models.events import WSEvent, WSEventType
from app.models.forex import ForexQuote
from app.services.bill_acceptor import BillAcceptor
from app.services.dispense_orchestrator import DispenseOrchestrator
from app.services.forex_change_calculator import calculate_forex_dispense
from app.services.forex_rate_service import ForexRateService
from app.services.machine_status import MachineStatus
from app.services.transaction_state_machine import TransactionStateMachine

logger = logging.getLogger(__name__)


class ForexTransactionOrchestrator:
    """Manages forex transaction lifecycles.

    Key differences from TransactionOrchestrator:
    - Requires online connectivity check before starting
    - Locks exchange rate at transaction start
    - Configures bill acceptor for the expected input currency
    - Uses forex-specific dispense calculation
    - Records forex metadata (rate, currency pair, fee %)
    """

    def __init__(
        self,
        bill_acceptor: BillAcceptor,
        dispense_orchestrator: DispenseOrchestrator,
        machine_status: MachineStatus,
        ws_manager: ConnectionManager,
        forex_rate_service: ForexRateService,
        db_session_factory: async_sessionmaker,
    ):
        self._bill_acceptor = bill_acceptor
        self._dispenser = dispense_orchestrator
        self._status = machine_status
        self._ws = ws_manager
        self._forex = forex_rate_service
        self._db_factory = db_session_factory
        self._active_tx: Optional[TransactionStateMachine] = None
        self._active_session: Optional[AsyncSession] = None
        self._active_quote: Optional[ForexQuote] = None

    @property
    def has_active_transaction(self) -> bool:
        return self._active_tx is not None

    @property
    def active_transaction_id(self) -> Optional[str]:
        return self._active_tx.transaction_id if self._active_tx else None

    async def start_transaction(
        self,
        service_type: str,
        selected_amount: int,
        selected_dispense_denoms: list = None,
    ) -> dict:
        """Start a forex transaction.

        Args:
            service_type: e.g., "usd-to-php"
            selected_amount: Foreign currency amount (for both directions)
            selected_dispense_denoms: User-selected output denominations

        Returns:
            Transaction state dict.

        Raises:
            ConnectivityError: If kiosk is offline.
            ForexError: If rates unavailable or dispense not possible.
            TransactionError: If another transaction is active.
        """
        if self._active_tx is not None:
            raise TransactionError(
                self._active_tx.transaction_id,
                "A transaction is already in progress",
            )

        # --- 1. Connectivity check ---
        if not await self._forex.check_forex_available():
            raise ConnectivityError("Forex requires internet connectivity")

        # --- 2. Validate machine state ---
        snapshot = self._status.snapshot()
        if snapshot.security.tamper_active:
            raise TransactionError("", "Machine is in lockdown mode")

        # --- 3. Get quote (locks rate) ---
        try:
            self._active_quote = self._forex.get_quote(service_type, selected_amount)
        except Exception as e:
            raise ForexError(f"Cannot calculate conversion: {e}")

        quote = self._active_quote
        pair = FOREX_PAIRS[ForexServiceType(service_type)]
        from_currency, to_currency = pair

        # --- 4. Determine amounts ---
        # For foreign->PHP: user inserts foreign, we dispense PHP
        # For PHP->foreign: user inserts PHP, we dispense foreign
        total_due = int(quote.input_amount)
        target_amount = int(quote.output_amount)
        fee = int(quote.fee_amount)

        # --- 5. Pre-check dispense capability ---
        try:
            calculate_forex_dispense(
                quote,
                snapshot.consumables.bill_dispenser_counts,
                snapshot.consumables.coin_counts,
                preferred_denoms=selected_dispense_denoms or [],
            )
        except Exception as e:
            raise ForexError(f"Cannot dispense target amount: {e}")

        # --- 6. Configure bill acceptor for expected currency ---
        self._bill_acceptor.set_expected_currency(from_currency.value)

        # --- 7. Create DB record ---
        tx_type = f"forex-{service_type}"
        tx_id = str(uuid.uuid4())
        session = self._db_factory()
        self._active_session = session

        record = TransactionRecord(
            id=tx_id,
            type=tx_type,
            state=TransactionState.IDLE.value,
            target_amount=target_amount,
            fee=fee,
            total_due=total_due,
            selected_dispense_denoms=selected_dispense_denoms or [],
            # Forex-specific fields
            from_currency=from_currency.value,
            to_currency=to_currency.value,
            exchange_rate=quote.rate,
            rate_locked_at=quote.locked_at,
            forex_fee_percentage=quote.fee_percentage,
            converted_amount=int(quote.converted_amount),
        )
        session.add(record)

        # WAL: rate locked
        wal_entry = WALEntry(
            transaction_id=tx_id,
            action=WALAction.FOREX_RATE_LOCKED.value,
            data={
                "rate": quote.rate,
                "from": from_currency.value,
                "to": to_currency.value,
                "amount": selected_amount,
            },
        )
        session.add(wal_entry)
        await session.commit()

        # --- 8. Create state machine ---
        self._active_tx = TransactionStateMachine(
            transaction_id=tx_id,
            transaction_type=tx_type,
            ws_manager=self._ws,
            db_session=session,
        )

        await self._active_tx.transition_to(TransactionState.WAITING_FOR_BILL)

        # Broadcast rate locked event
        await self._ws.broadcast(WSEvent(
            type=WSEventType.FOREX_RATE_LOCKED,
            payload={
                "transaction_id": tx_id,
                "rate": quote.rate,
                "from_currency": from_currency.value,
                "to_currency": to_currency.value,
                "fee_percentage": quote.fee_percentage,
            },
        ))

        logger.info(
            f"Forex transaction started: {tx_id} type={service_type} "
            f"rate={quote.rate} amount={selected_amount} fee={fee}"
        )

        return await self.get_transaction_state(tx_id)

    async def handle_bill_inserted(self) -> dict:
        """Handle a bill acceptance cycle during a forex transaction.

        Same flow as money changer but uses currency-specific ML model.
        """
        tx = self._require_active()

        if not tx.is_in_state(TransactionState.WAITING_FOR_BILL):
            raise TransactionError(
                tx.transaction_id,
                f"Cannot accept bill in state {tx.state.value}",
            )

        await tx.transition_to(TransactionState.AUTHENTICATING)

        result = await self._bill_acceptor.accept_bill()

        if not result.success:
            await tx.transition_to(
                TransactionState.WAITING_FOR_BILL,
                {"last_rejection": result.error},
            )
            tx.reset_timeout()
            return await self.get_transaction_state(tx.transaction_id)

        # Bill accepted
        await tx.transition_to(
            TransactionState.SORTING,
            {"denomination": result.denomination.value, "value": result.value},
        )

        # Update DB
        session = self._active_session
        db_record = await self._get_db_record(session, tx.transaction_id)
        if db_record:
            db_record.inserted_amount += result.value
            inserted = dict(db_record.inserted_denominations or {})
            denom_key = str(result.value)
            inserted[denom_key] = inserted.get(denom_key, 0) + 1
            db_record.inserted_denominations = inserted
            await session.commit()

        await tx.transition_to(TransactionState.WAITING_FOR_BILL)

        # Check if enough money inserted
        if db_record and db_record.inserted_amount >= db_record.total_due:
            await tx.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)
        else:
            tx.reset_timeout()

        return await self.get_transaction_state(tx.transaction_id)

    async def confirm_transaction(self) -> dict:
        """Confirm the forex transaction and trigger dispensing."""
        tx = self._require_active()

        if not tx.is_in_state(TransactionState.WAITING_FOR_CONFIRMATION):
            raise TransactionError(
                tx.transaction_id,
                f"Cannot confirm in state {tx.state.value}",
            )

        session = self._active_session
        db_record = await self._get_db_record(session, tx.transaction_id)
        if not db_record:
            raise TransactionError(tx.transaction_id, "Transaction record not found")

        # Calculate dispense plan using locked quote
        snapshot = self._status.snapshot()
        plan = calculate_forex_dispense(
            self._active_quote,
            snapshot.consumables.bill_dispenser_counts,
            snapshot.consumables.coin_counts,
            preferred_denoms=db_record.selected_dispense_denoms,
        )

        db_record.dispense_plan = {
            "items": [item.model_dump() for item in plan.items],
            "total_amount": plan.total_amount,
        }
        await session.commit()

        await tx.transition_to(TransactionState.DISPENSING)

        result = await self._dispenser.execute_dispense(plan)

        db_record.dispensed_amount = result.total_dispensed
        db_record.dispense_result = result.model_dump()
        await session.commit()

        if result.success:
            await tx.transition_to(
                TransactionState.COMPLETE,
                {"dispensed_amount": result.total_dispensed},
            )
        else:
            await tx.transition_to(
                TransactionState.ERROR,
                {
                    "error_code": "PARTIAL_DISPENSE",
                    "error_message": result.error,
                    "dispensed_amount": result.total_dispensed,
                    "shortfall": result.shortfall,
                    "claim_ticket_code": result.claim_ticket_code,
                },
            )

        state = await self.get_transaction_state(tx.transaction_id)
        await self._cleanup()
        return state

    async def cancel_transaction(self) -> dict:
        """Cancel the active forex transaction."""
        tx = self._require_active()
        await tx.cancel()
        state = await self.get_transaction_state(tx.transaction_id)
        await self._cleanup()
        return state

    async def get_transaction_state(self, transaction_id: str) -> dict:
        """Get full state including forex-specific fields."""
        session = self._active_session or self._db_factory()
        db_record = await self._get_db_record(session, transaction_id)
        if not db_record:
            raise TransactionError(transaction_id, "Transaction not found")

        result = {
            "transaction_id": db_record.id,
            "type": db_record.type,
            "state": db_record.state,
            "target_amount": db_record.target_amount,
            "fee": db_record.fee,
            "total_due": db_record.total_due,
            "inserted_amount": db_record.inserted_amount,
            "dispensed_amount": db_record.dispensed_amount,
            "inserted_denominations": db_record.inserted_denominations or {},
            "dispense_plan": db_record.dispense_plan,
            "dispense_result": db_record.dispense_result,
            "selected_dispense_denoms": db_record.selected_dispense_denoms or [],
            "error_code": db_record.error_code,
            "error_message": db_record.error_message,
            "created_at": db_record.created_at.isoformat() if db_record.created_at else None,
            "updated_at": db_record.updated_at.isoformat() if db_record.updated_at else None,
            "completed_at": db_record.completed_at.isoformat() if db_record.completed_at else None,
            # Forex-specific
            "from_currency": db_record.from_currency,
            "to_currency": db_record.to_currency,
            "exchange_rate": db_record.exchange_rate,
            "rate_locked_at": db_record.rate_locked_at.isoformat() if db_record.rate_locked_at else None,
            "forex_fee_percentage": db_record.forex_fee_percentage,
            "converted_amount": db_record.converted_amount,
        }

        if session != self._active_session:
            await session.close()

        return result

    def _require_active(self) -> TransactionStateMachine:
        if self._active_tx is None:
            raise TransactionError("", "No active forex transaction")
        return self._active_tx

    async def _get_db_record(
        self, session: AsyncSession, transaction_id: str
    ) -> Optional[TransactionRecord]:
        result = await session.execute(
            select(TransactionRecord).where(TransactionRecord.id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def _cleanup(self) -> None:
        if self._active_session:
            await self._active_session.close()
            self._active_session = None
        self._active_tx = None
        self._active_quote = None
        # Reset bill acceptor to PHP
        self._bill_acceptor.set_expected_currency("PHP")
```

---

## Step 6: REST API Endpoints ✅ DONE

### 6.1 Create `backend/app/api/forex.py` (NEW FILE)

```python
"""Forex REST API endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forex", tags=["forex"])


# --- Request/Response Models ---


class ForexStartRequest(BaseModel):
    service_type: str  # "usd-to-php", "php-to-usd", "eur-to-php", "php-to-eur"
    selected_amount: int  # Foreign currency amount
    selected_dispense_denoms: List[int] = []


class ForexRatesResponse(BaseModel):
    rates: dict  # {"USD": 58.7656, "EUR": 61.7246}
    fetched_at: Optional[str] = None
    valid: bool = False
    online: bool = False
    fees: dict = {}  # {"usd-to-php": 5.0, ...}


class ForexQuoteResponse(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    input_amount: float
    converted_amount: float
    fee_percentage: float
    fee_amount: float
    output_amount: float


class ForexTransactionResponse(BaseModel):
    transaction_id: str
    type: str
    state: str
    target_amount: int
    fee: int
    total_due: int
    inserted_amount: int
    dispensed_amount: int
    inserted_denominations: dict = {}
    dispense_plan: Optional[dict] = None
    dispense_result: Optional[dict] = None
    selected_dispense_denoms: list = []
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    # Forex fields
    from_currency: Optional[str] = None
    to_currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    rate_locked_at: Optional[str] = None
    forex_fee_percentage: Optional[float] = None
    converted_amount_forex: Optional[int] = None  # renamed to avoid conflict


# --- Endpoints ---


@router.get("/rates", response_model=ForexRatesResponse)
async def get_forex_rates(request: Request):
    """Get current exchange rates and availability status."""
    forex_service = request.app.state.forex_rate_service
    return ForexRatesResponse(
        rates=forex_service.current_rates,
        fetched_at=(
            forex_service._cache.fetched_at.isoformat()
            if forex_service._cache.fetched_at
            else None
        ),
        valid=forex_service.rates_valid,
        online=forex_service.is_online,
        fees={
            "usd-to-php": forex_service.get_fee_percentage("usd-to-php"),
            "php-to-usd": forex_service.get_fee_percentage("php-to-usd"),
            "eur-to-php": forex_service.get_fee_percentage("eur-to-php"),
            "php-to-eur": forex_service.get_fee_percentage("php-to-eur"),
        },
    )


@router.get("/quote/{service_type}")
async def get_forex_quote(
    service_type: str, amount: int, request: Request
):
    """Get a conversion quote without starting a transaction.

    Query params:
        amount: Foreign currency amount

    Example: GET /api/v1/forex/quote/usd-to-php?amount=100
    """
    forex_service = request.app.state.forex_rate_service
    try:
        quote = forex_service.get_quote(service_type, amount)
        return ForexQuoteResponse(
            from_currency=quote.from_currency,
            to_currency=quote.to_currency,
            rate=quote.rate,
            input_amount=quote.input_amount,
            converted_amount=quote.converted_amount,
            fee_percentage=quote.fee_percentage,
            fee_amount=quote.fee_amount,
            output_amount=quote.output_amount,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transaction", response_model=ForexTransactionResponse)
async def start_forex_transaction(req: ForexStartRequest, request: Request):
    """Start a new forex transaction with rate locking."""
    orchestrator = request.app.state.forex_transaction_orchestrator
    try:
        state = await orchestrator.start_transaction(
            service_type=req.service_type,
            selected_amount=req.selected_amount,
            selected_dispense_denoms=req.selected_dispense_denoms,
        )
        return ForexTransactionResponse(**_map_state(state))
    except Exception as e:
        status = 409 if "already in progress" in str(e) else 400
        raise HTTPException(status_code=status, detail=str(e))


@router.get("/transaction/{transaction_id}", response_model=ForexTransactionResponse)
async def get_forex_transaction(transaction_id: str, request: Request):
    """Get forex transaction state."""
    orchestrator = request.app.state.forex_transaction_orchestrator
    try:
        state = await orchestrator.get_transaction_state(transaction_id)
        return ForexTransactionResponse(**_map_state(state))
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/transaction/{transaction_id}", response_model=ForexTransactionResponse)
async def cancel_forex_transaction(transaction_id: str, request: Request):
    """Cancel an active forex transaction."""
    orchestrator = request.app.state.forex_transaction_orchestrator
    try:
        if orchestrator.active_transaction_id != transaction_id:
            raise HTTPException(status_code=404, detail="Transaction not active")
        state = await orchestrator.cancel_transaction()
        return ForexTransactionResponse(**_map_state(state))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transaction/{transaction_id}/confirm", response_model=ForexTransactionResponse)
async def confirm_forex_transaction(transaction_id: str, request: Request):
    """Confirm forex transaction and trigger dispensing."""
    orchestrator = request.app.state.forex_transaction_orchestrator
    try:
        if orchestrator.active_transaction_id != transaction_id:
            raise HTTPException(status_code=404, detail="Transaction not active")
        state = await orchestrator.confirm_transaction()
        return ForexTransactionResponse(**_map_state(state))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transaction/{transaction_id}/simulate-insert")
async def simulate_forex_insert(
    transaction_id: str, request: Request
):
    """Simulate bill insertion for forex (dev mode only).

    Body: {"denom": 100, "currency": "USD"}
    """
    orchestrator = request.app.state.forex_transaction_orchestrator
    settings = request.app.state.settings
    body = await request.json()
    denom = body.get("denom", 0)
    currency = body.get("currency", "PHP")

    try:
        if orchestrator.active_transaction_id != transaction_id:
            raise HTTPException(status_code=404, detail="Transaction not active")

        if settings.use_mock_hardware:
            bill_acceptor = request.app.state.bill_acceptor
            from app.core.constants import BillDenom
            from app.models.denominations import value_to_denom_string

            denom_str = value_to_denom_string(denom, currency)
            try:
                bill_denom = BillDenom(denom_str)
                auth = bill_acceptor._auth
                if hasattr(auth, "set_next_denomination"):
                    auth.set_next_denomination(bill_denom)
                if hasattr(auth, "set_accept_next"):
                    auth.set_accept_next()
                gpio = bill_acceptor._gpio
                if hasattr(gpio, "set_bill_at_entry"):
                    gpio.set_bill_at_entry(True)
                if hasattr(gpio, "set_bill_in_position"):
                    gpio.set_bill_in_position(True)
            except (ValueError, KeyError):
                raise HTTPException(status_code=400, detail=f"Invalid denomination: {denom}")

        state = await orchestrator.handle_bill_inserted()
        return state
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connectivity")
async def check_connectivity(request: Request):
    """Check if forex is currently available (online + valid rates)."""
    forex_service = request.app.state.forex_rate_service
    available = await forex_service.check_forex_available()
    return {
        "online": forex_service.is_online,
        "rates_valid": forex_service.rates_valid,
        "forex_available": available,
    }


def _map_state(state: dict) -> dict:
    """Map internal state dict to response fields."""
    mapped = dict(state)
    # Handle field name conflict: converted_amount -> converted_amount_forex
    if "converted_amount" in mapped:
        mapped["converted_amount_forex"] = mapped.pop("converted_amount")
    return mapped
```

### 6.2 Register forex router in `backend/app/api/router.py`

Add after the existing router imports (line ~9):

```python
from app.api.forex import router as forex_router
```

Add after the existing `include_router` calls (line ~16):

```python
api_router.include_router(forex_router)
```

### 6.3 Add forex WS action handling in `backend/app/api/router.py`

Add to the `_handle_ws_action` function (after the existing `SIMULATE_COIN_INSERT` block):

```python
    elif action == "SIMULATE_FOREX_BILL_INSERT" and settings.use_mock_hardware:
        denom = data.get("denom")
        currency = data.get("currency", "PHP")
        forex_orchestrator = websocket.app.state.forex_transaction_orchestrator
        if denom and forex_orchestrator.has_active_transaction:
            try:
                bill_acceptor = websocket.app.state.bill_acceptor
                from app.core.constants import BillDenom
                from app.models.denominations import value_to_denom_string

                denom_str = value_to_denom_string(denom, currency)
                bill_denom = BillDenom(denom_str)
                auth = bill_acceptor._auth
                if hasattr(auth, "set_next_denomination"):
                    auth.set_next_denomination(bill_denom)
                if hasattr(auth, "set_accept_next"):
                    auth.set_accept_next()
                gpio = bill_acceptor._gpio
                if hasattr(gpio, "set_bill_at_entry"):
                    gpio.set_bill_at_entry(True)
                if hasattr(gpio, "set_bill_in_position"):
                    gpio.set_bill_in_position(True)
                await forex_orchestrator.handle_bill_inserted()
            except Exception as e:
                logger.error(f"WS SIMULATE_FOREX_BILL_INSERT error: {e}")
```

---

## Step 7: WebSocket Events ✅ DONE

### 7.1 New event types (already defined in Step 1.4)

| Event Type | Payload | When |
|---|---|---|
| `FOREX_RATE_UPDATE` | `{rates, fetched_at, valid}` | Rates refreshed |
| `FOREX_RATE_LOCKED` | `{transaction_id, rate, from_currency, to_currency, fee_percentage}` | Transaction started |
| `FOREX_CONNECTIVITY_CHANGED` | `{online}` | Connectivity status changes |
| `FOREX_CONVERSION_COMPLETE` | `{transaction_id, output_amount, to_currency}` | Dispense complete |

All existing transaction events (`TRANSACTION_STATE_CHANGED`, `BILL_STORED`, `DISPENSE_PROGRESS`, etc.) are also emitted by `ForexTransactionOrchestrator` since it uses the same `TransactionStateMachine`.

---

## Step 8: Frontend Backend Integration ✅ DONE

### 8.1 Create `frontend/src/hooks/useForexTransaction.js` (NEW FILE)

This hook connects the existing forex UI screens to the backend API, similar to `useBackendTransaction.js`.

```javascript
/**
 * Hook bridging ForexContext with the backend forex API.
 *
 * Provides:
 * - startForexBackendTransaction(serviceType, amount, dispenseDenoms)
 * - confirmForexTransaction()
 * - cancelForexTransaction()
 * - simulateForexInsert(denom, currency)
 * - forexRates (live rates from backend)
 * - connectivity status
 *
 * Subscribes to WS events:
 * - FOREX_RATE_UPDATE -> update rates
 * - FOREX_RATE_LOCKED -> lock rate in ForexContext
 * - FOREX_CONNECTIVITY_CHANGED -> update online status
 * - BILL_STORED -> update inserted amount in ForexContext
 * - TRANSACTION_STATE_CHANGED -> update state
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { API_BASE } from "../constants/api";
import { useWebSocket } from "../context/WebSocketContext";
import { useForex } from "../context/ForexContext";

export function useForexTransaction() {
  const { subscribe, unsubscribe } = useWebSocket();
  const { addInsertedMoney, lockRate } = useForex();
  const [transactionId, setTransactionId] = useState(null);
  const [backendState, setBackendState] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [forexRates, setForexRates] = useState({});
  const [isOnline, setIsOnline] = useState(false);
  const [dispenseProgress, setDispenseProgress] = useState(null);
  const txIdRef = useRef(null);

  useEffect(() => {
    txIdRef.current = transactionId;
  }, [transactionId]);

  // Fetch initial rates
  useEffect(() => {
    const fetchRates = async () => {
      try {
        const resp = await fetch(`${API_BASE}/forex/rates`);
        if (resp.ok) {
          const data = await resp.json();
          setForexRates(data.rates || {});
          setIsOnline(data.online);
        }
      } catch {
        setIsOnline(false);
      }
    };
    fetchRates();
  }, []);

  // Subscribe to WS events
  useEffect(() => {
    const handleRateUpdate = (event) => {
      setForexRates(event.payload?.rates || {});
    };

    const handleConnectivity = (event) => {
      setIsOnline(event.payload?.online ?? false);
    };

    const handleStateChange = (event) => {
      if (event.payload?.transaction_id === txIdRef.current) {
        setBackendState(event.payload);
      }
    };

    const handleBillStored = (event) => {
      if (event.payload?.value) {
        addInsertedMoney(event.payload.value);
      }
    };

    const handleRateLocked = (event) => {
      if (event.payload?.transaction_id === txIdRef.current) {
        lockRate();
      }
    };

    const handleDispenseProgress = (event) => {
      setDispenseProgress(event.payload);
    };

    const handleError = (event) => {
      if (event.payload?.transaction_id === txIdRef.current) {
        setError(event.payload?.error_message || "Forex transaction error");
      }
    };

    subscribe("FOREX_RATE_UPDATE", handleRateUpdate);
    subscribe("FOREX_CONNECTIVITY_CHANGED", handleConnectivity);
    subscribe("FOREX_RATE_LOCKED", handleRateLocked);
    subscribe("TRANSACTION_STATE_CHANGED", handleStateChange);
    subscribe("TRANSACTION_COMPLETE", handleStateChange);
    subscribe("TRANSACTION_CANCELLED", handleStateChange);
    subscribe("TRANSACTION_ERROR", handleError);
    subscribe("BILL_STORED", handleBillStored);
    subscribe("DISPENSE_PROGRESS", handleDispenseProgress);

    return () => {
      unsubscribe("FOREX_RATE_UPDATE", handleRateUpdate);
      unsubscribe("FOREX_CONNECTIVITY_CHANGED", handleConnectivity);
      unsubscribe("FOREX_RATE_LOCKED", handleRateLocked);
      unsubscribe("TRANSACTION_STATE_CHANGED", handleStateChange);
      unsubscribe("TRANSACTION_COMPLETE", handleStateChange);
      unsubscribe("TRANSACTION_CANCELLED", handleStateChange);
      unsubscribe("TRANSACTION_ERROR", handleError);
      unsubscribe("BILL_STORED", handleBillStored);
      unsubscribe("DISPENSE_PROGRESS", handleDispenseProgress);
    };
  }, [subscribe, unsubscribe, addInsertedMoney, lockRate]);

  const startForexBackendTransaction = useCallback(
    async (serviceType, amount, dispenseDenoms = []) => {
      setIsLoading(true);
      setError(null);
      try {
        const resp = await fetch(`${API_BASE}/forex/transaction`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            service_type: serviceType,
            selected_amount: amount,
            selected_dispense_denoms: dispenseDenoms,
          }),
        });
        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.detail || `HTTP ${resp.status}`);
        }
        const data = await resp.json();
        setTransactionId(data.transaction_id);
        setBackendState(data);
        return data;
      } catch (err) {
        setError(err.message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const confirmForexTransaction = useCallback(async () => {
    if (!txIdRef.current) return null;
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${API_BASE}/forex/transaction/${txIdRef.current}/confirm`,
        { method: "POST" }
      );
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setBackendState(data);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const cancelForexTransaction = useCallback(async () => {
    if (!txIdRef.current) return null;
    setIsLoading(true);
    try {
      const resp = await fetch(
        `${API_BASE}/forex/transaction/${txIdRef.current}`,
        { method: "DELETE" }
      );
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setBackendState(data);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
      setTransactionId(null);
    }
  }, []);

  const simulateForexInsert = useCallback(
    async (denom, currency = "USD") => {
      if (!txIdRef.current) return null;
      try {
        const resp = await fetch(
          `${API_BASE}/forex/transaction/${txIdRef.current}/simulate-insert`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ denom, currency }),
          }
        );
        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.detail || `HTTP ${resp.status}`);
        }
        return await resp.json();
      } catch (err) {
        console.error("Simulate forex insert error:", err);
        return null;
      }
    },
    []
  );

  const resetForexTransaction = useCallback(() => {
    setTransactionId(null);
    setBackendState(null);
    setError(null);
    setDispenseProgress(null);
  }, []);

  // Check connectivity
  const checkConnectivity = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/forex/connectivity`);
      if (resp.ok) {
        const data = await resp.json();
        setIsOnline(data.online);
        return data;
      }
    } catch {
      setIsOnline(false);
    }
    return { online: false, forex_available: false };
  }, []);

  return {
    transactionId,
    backendState,
    isLoading,
    error,
    forexRates,
    isOnline,
    dispenseProgress,
    startForexBackendTransaction,
    confirmForexTransaction,
    cancelForexTransaction,
    simulateForexInsert,
    resetForexTransaction,
    checkConnectivity,
  };
}
```

### 8.2 Update `frontend/src/context/ForexContext.jsx`

Key changes to make:
1. Replace `MOCK_EXCHANGE_RATES` usage with rates from backend (passed via hook)
2. Add method to set rates from backend: `setBackendRates(rates)`
3. Keep the existing UI state management (it still manages UI flow state)

Add to `ForexProvider`:

```javascript
// Add to state
const [backendRates, setBackendRates] = useState(null);

// Add method to update rates from backend
const updateRatesFromBackend = useCallback((rates) => {
  setBackendRates(rates);
  // Recalculate if amount is selected
  // ... (same as refreshRate but using backend rates)
}, []);
```

Add to `value` object:

```javascript
updateRatesFromBackend,
backendRates,
```

### 8.3 Update `frontend/src/constants/forexData.js`

Add helper to get live rates from backend (for use when backend is available):

```javascript
/**
 * Get exchange rate from backend rates (live) or mock rates (fallback).
 * @param {string} fromCurrency
 * @param {string} toCurrency
 * @param {Object} backendRates - Optional backend rates {USD: 58.76, EUR: 61.72}
 * @returns {number}
 */
export const getExchangeRateLive = (fromCurrency, toCurrency, backendRates = null) => {
  const rates = backendRates || MOCK_EXCHANGE_RATES;
  if (fromCurrency === CURRENCIES.PHP) {
    return 1 / rates[toCurrency];
  }
  return rates[fromCurrency];
};
```

### 8.4 Update forex screens to use backend integration

Each forex screen needs minor updates to call backend endpoints instead of using mock data. The key screens to update:

**`ForexConfirmationScreen.jsx`**: On confirm, call `startForexBackendTransaction()` to create the backend transaction and lock the rate.

**`ForexInsertMoneyScreen.jsx`**: Replace keyboard simulation with `simulateForexInsert()`. Listen for WS events for real bill insertions.

**`ForexConversionScreen.jsx`**: On confirm, call `confirmForexTransaction()` to trigger dispensing.

**`ForexProcessingScreen.jsx`**: Listen for `DISPENSE_PROGRESS` and `TRANSACTION_COMPLETE` WS events.

**`ForexSuccessScreen.jsx`**: Call `resetForexTransaction()` on exit.

**`ForexWarningScreen.jsx`**: Call `cancelForexTransaction()` on cancel.

**`ForexServiceSelectionScreen.jsx`**: Check connectivity via `checkConnectivity()` and show "Offline" badge on forex cards if not available.

**`ExchangeRateScreen.jsx` (ForexRateScreen)**: Fetch live rates from `GET /api/v1/forex/rates` and display them instead of mock data.

### 8.5 Update `frontend/src/constants/api.js`

Verify that `API_BASE` is set correctly. It should already be:

```javascript
export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api/v1";
```

No changes needed if this already exists.

---

## Step 9: Tests ✅ DONE

### 9.1 Unit Tests

#### `backend/tests/unit/test_forex_rate_service.py` (NEW FILE)

```python
"""Tests for ForexRateService."""

# Test cases:
# 1. test_get_rate_valid_cache - Returns rate when cache is valid
# 2. test_get_rate_expired_cache - Raises RateUnavailableError when cache expired
# 3. test_get_rate_no_cache - Raises RateUnavailableError when no cache
# 4. test_get_quote_usd_to_php - Correct conversion for USD->PHP
# 5. test_get_quote_php_to_usd - Correct conversion for PHP->USD
# 6. test_get_quote_eur_to_php - Correct conversion for EUR->PHP
# 7. test_get_quote_php_to_eur - Correct conversion for PHP->EUR
# 8. test_get_fee_percentage_configured - Returns configured fee per pair
# 9. test_get_fee_percentage_default - Returns 5.0 for unknown pair
# 10. test_check_connectivity_online - Returns True when API reachable
# 11. test_check_connectivity_offline - Returns False when API unreachable
# 12. test_fetch_rates_success - Parses Abstract API response correctly
# 13. test_fetch_rates_api_error - Handles API error gracefully
# 14. test_rate_cache_ttl - Cache expires after configured TTL
# 15. test_ws_broadcast_on_rate_update - Broadcasts FOREX_RATE_UPDATE event
# 16. test_ws_broadcast_on_connectivity_change - Broadcasts FOREX_CONNECTIVITY_CHANGED
```

#### `backend/tests/unit/test_forex_change_calculator.py` (NEW FILE)

```python
"""Tests for forex change calculator."""

# Test cases:
# 1. test_dispense_php_from_usd - Calculates PHP dispense from USD input
# 2. test_dispense_php_from_eur - Calculates PHP dispense from EUR input
# 3. test_dispense_usd_from_php - Calculates USD bill dispense (no coins)
# 4. test_dispense_eur_from_php - Calculates EUR bill dispense (no coins)
# 5. test_dispense_php_with_coins - Uses PHP coins for remainder
# 6. test_dispense_foreign_no_coins - No coin dispensing for foreign currency
# 7. test_insufficient_inventory - Raises ValueError when not enough bills
# 8. test_preferred_denoms - Respects preferred denomination selection
```

#### `backend/tests/unit/test_forex_transaction_orchestrator.py` (NEW FILE)

```python
"""Tests for ForexTransactionOrchestrator."""

# Test cases:
# 1. test_start_transaction_success - Creates transaction with locked rate
# 2. test_start_transaction_offline - Raises ConnectivityError
# 3. test_start_transaction_tamper - Raises TransactionError when tampered
# 4. test_start_transaction_already_active - Raises TransactionError
# 5. test_start_transaction_rate_unavailable - Raises ForexError
# 6. test_start_transaction_cannot_dispense - Raises ForexError
# 7. test_handle_bill_inserted_correct_currency - Accepts bill
# 8. test_handle_bill_inserted_wrong_currency - Rejects bill
# 9. test_handle_bill_auto_confirm - Transitions to WAITING_FOR_CONFIRMATION when enough inserted
# 10. test_confirm_transaction_success - Full dispense cycle
# 11. test_confirm_transaction_partial_dispense - Generates claim ticket
# 12. test_cancel_transaction - Cancels and cleans up
# 13. test_db_record_has_forex_fields - Persists forex metadata
# 14. test_rate_locked_in_transaction - Rate doesn't change during transaction
# 15. test_bill_acceptor_currency_reset - Resets to PHP after transaction
```

### 9.2 Integration Tests

#### `backend/tests/integration/test_forex_api.py` (NEW FILE)

```python
"""Integration tests for forex API endpoints."""

# Test cases (using TestClient + mock hardware):
# 1. test_get_rates_online - GET /forex/rates returns rates when online
# 2. test_get_rates_offline - GET /forex/rates returns valid=False when offline
# 3. test_get_quote - GET /forex/quote/usd-to-php?amount=100 returns correct quote
# 4. test_start_transaction - POST /forex/transaction starts correctly
# 5. test_start_transaction_offline - POST /forex/transaction returns 400 when offline
# 6. test_simulate_insert - POST /forex/transaction/{id}/simulate-insert works
# 7. test_confirm_transaction - POST /forex/transaction/{id}/confirm triggers dispense
# 8. test_cancel_transaction - DELETE /forex/transaction/{id} cancels correctly
# 9. test_full_forex_flow_usd_to_php - End-to-end: start -> insert -> confirm -> complete
# 10. test_full_forex_flow_php_to_usd - End-to-end reverse direction
# 11. test_connectivity_check - GET /forex/connectivity returns status
# 12. test_ws_forex_events - WebSocket receives forex events
```

### 9.3 Test Fixtures

Add to `backend/tests/conftest.py`:

```python
@pytest.fixture
def mock_forex_rate_service(mock_ws_manager, test_settings):
    """ForexRateService with mocked HTTP client."""
    from app.services.forex_rate_service import ForexRateService
    service = ForexRateService(test_settings, mock_ws_manager)
    # Pre-populate cache with test rates
    from datetime import datetime, timedelta
    from app.models.forex import ExchangeRateCache
    service._cache = ExchangeRateCache(
        rates={"USD": 58.7656, "EUR": 61.7246},
        fetched_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    service._is_online = True
    return service


@pytest.fixture
def mock_forex_orchestrator(
    mock_bill_acceptor, mock_dispense_orchestrator,
    mock_machine_status, mock_ws_manager,
    mock_forex_rate_service, db_session_factory,
):
    """ForexTransactionOrchestrator with all mocked dependencies."""
    from app.services.forex_transaction_orchestrator import ForexTransactionOrchestrator
    return ForexTransactionOrchestrator(
        bill_acceptor=mock_bill_acceptor,
        dispense_orchestrator=mock_dispense_orchestrator,
        machine_status=mock_machine_status,
        ws_manager=mock_ws_manager,
        forex_rate_service=mock_forex_rate_service,
        db_session_factory=db_session_factory,
    )
```

---

## Step 10: Wire Everything Up in `main.py` ✅ DONE

### 10.1 Update `backend/app/main.py`

Add imports:

```python
from app.services.forex_rate_service import ForexRateService
from app.services.forex_transaction_orchestrator import ForexTransactionOrchestrator
```

In the `lifespan` function, after the existing service layer setup (after line ~100):

```python
    # --- Phase 5: Forex services ---
    forex_rate_service = ForexRateService(settings, ws_manager)
    forex_transaction_orchestrator = ForexTransactionOrchestrator(
        bill_acceptor=bill_acceptor,
        dispense_orchestrator=dispense_orchestrator,
        machine_status=machine_status,
        ws_manager=ws_manager,
        forex_rate_service=forex_rate_service,
        db_session_factory=get_session_factory(),
    )

    app.state.forex_rate_service = forex_rate_service
    app.state.forex_transaction_orchestrator = forex_transaction_orchestrator
```

In the startup section (after `await transaction_orchestrator.recover_pending_transactions()`):

```python
    # Start forex rate service (fetches initial rates + starts periodic refresh)
    await forex_rate_service.start()
```

In the shutdown section (before `await event_dispatcher.stop()`):

```python
    await forex_rate_service.stop()
```

### 10.2 Database Migration

Since we're adding new columns to `TransactionRecord`, run a database migration. With SQLite and SQLAlchemy, the simplest approach:

1. Delete the existing `coinnect.db` during development (it's recreated on startup by `init_db()`).
2. For production, use Alembic migrations (out of scope for this phase).

Ensure `init_db()` in `backend/app/core/database.py` calls `Base.metadata.create_all()` which will create the new columns.

---

## File Change Summary

### New Files (8)

| File | Purpose |
|---|---|
| `backend/app/models/forex.py` | Pydantic models for forex data (ExchangeRateCache, ForexQuote, etc.) |
| `backend/app/services/forex_rate_service.py` | Abstract API client with caching, connectivity check, rate locking |
| `backend/app/services/forex_change_calculator.py` | Forex-specific dispense plan calculation |
| `backend/app/services/forex_transaction_orchestrator.py` | Forex transaction lifecycle coordinator |
| `backend/app/api/forex.py` | REST API endpoints for forex |
| `frontend/src/hooks/useForexTransaction.js` | React hook bridging ForexContext with backend API |
| `backend/tests/unit/test_forex_rate_service.py` | Unit tests for rate service |
| `backend/tests/unit/test_forex_change_calculator.py` | Unit tests for forex calculator |
| `backend/tests/unit/test_forex_transaction_orchestrator.py` | Unit tests for forex orchestrator |
| `backend/tests/integration/test_forex_api.py` | Integration tests for forex API |

### Modified Files (10)

| File | Changes |
|---|---|
| `backend/app/core/config.py` | Add forex config fields (API key, fees, ML model paths) |
| `backend/app/core/constants.py` | Add `Currency`, `ForexServiceType` enums, currency mappings |
| `backend/app/core/errors.py` | Add `ForexError`, `ConnectivityError`, `RateExpiredError` |
| `backend/app/models/db_models.py` | Add forex `TransactionType` variants, forex columns to `TransactionRecord` |
| `backend/app/models/events.py` | Add forex `WSEventType` variants |
| `backend/app/ml/bill_authenticator.py` | Add `set_currency()` for model switching |
| `backend/app/ml/mock_authenticator.py` | Add `set_currency()` for mock |
| `backend/app/services/bill_acceptor.py` | Add `set_expected_currency()`, wrong-currency rejection |
| `backend/app/api/router.py` | Register forex router, add `SIMULATE_FOREX_BILL_INSERT` WS handler |
| `backend/app/main.py` | Wire up `ForexRateService` and `ForexTransactionOrchestrator` |
| `backend/requirements.txt` | Add `httpx>=0.27.0` |
| `backend/tests/conftest.py` | Add forex test fixtures |
| `frontend/src/context/ForexContext.jsx` | Add `updateRatesFromBackend()`, `backendRates` |
| `frontend/src/constants/forexData.js` | Add `getExchangeRateLive()` helper |
| `frontend/src/pages/forex/ForexConfirmationScreen.jsx` | Call `startForexBackendTransaction()` on confirm |
| `frontend/src/pages/forex/ForexInsertMoneyScreen.jsx` | Use `simulateForexInsert()`, listen for WS events |
| `frontend/src/pages/forex/ForexConversionScreen.jsx` | Call `confirmForexTransaction()` |
| `frontend/src/pages/forex/ForexProcessingScreen.jsx` | Listen for dispense WS events |
| `frontend/src/pages/forex/ForexSuccessScreen.jsx` | Call `resetForexTransaction()` |
| `frontend/src/pages/forex/ForexWarningScreen.jsx` | Call `cancelForexTransaction()` |
| `frontend/src/pages/forex/ForexServiceSelectionScreen.jsx` | Check connectivity, show offline badge |

---

## Dependency Graph

```
Step 1: Config & Models ─────────────────────────┐
                                                  │
Step 2: Forex Rate Service ──────────────────┐    │
    depends on: Step 1 (config, models)      │    │
                                             │    │
Step 3: Forex Change Calculator ────────┐    │    │
    depends on: Step 1 (constants)      │    │    │
                                        │    │    │
Step 4: Multi-Currency ML ──────────┐   │    │    │
    depends on: Step 1 (config)     │   │    │    │
                                    ▼   ▼    ▼    ▼
                              Step 5: Forex Orchestrator
                                    depends on: 1, 2, 3, 4
                                         │
                                    ┌────┴────┐
                                    ▼         ▼
                              Step 6: API  Step 7: WS Events
                              depends on 5  depends on 5
                                    │         │
                                    └────┬────┘
                                         ▼
                              Step 8: Frontend Integration
                              depends on: 6, 7
                                         │
                                         ▼
                              Step 9: Tests
                              depends on: all steps
```

**Recommended implementation order**:
1. Steps 1, 2, 3, 4 in parallel (independent foundation work)
2. Step 5 (depends on 1-4)
3. Steps 6, 7 in parallel (depend on 5)
4. Step 8 (depends on 6, 7)
5. Step 9 (tests throughout, but formal test suite last)

---

## Environment Variables (`.env`)

Add these to `backend/.env`:

```env
# Forex - Abstract API
FOREX_API_KEY=your_abstract_api_key_here
FOREX_CACHE_TTL_SECONDS=86400
FOREX_RATE_REFRESH_INTERVAL=3600

# Forex fees (percentage per pair)
FOREX_FEE_USD_TO_PHP=5.0
FOREX_FEE_PHP_TO_USD=5.0
FOREX_FEE_EUR_TO_PHP=5.0
FOREX_FEE_PHP_TO_EUR=5.0

# ML models per currency
YOLO_AUTH_MODEL_PATH_USD=models/auth_usd.pt
YOLO_DENOM_MODEL_PATH_USD=models/denom_usd.pt
YOLO_AUTH_MODEL_PATH_EUR=models/auth_eur.pt
YOLO_DENOM_MODEL_PATH_EUR=models/denom_eur.pt
```

---

## Verification Checklist

After implementation, verify:

- [ ] `pytest tests/unit/test_forex_rate_service.py -v` - All pass
- [ ] `pytest tests/unit/test_forex_change_calculator.py -v` - All pass
- [ ] `pytest tests/unit/test_forex_transaction_orchestrator.py -v` - All pass
- [ ] `pytest tests/integration/test_forex_api.py -v` - All pass
- [ ] `pytest --cov=app tests/` - No regressions in existing tests
- [ ] Manual smoke test: `USE_MOCK_SERIAL=true USE_MOCK_HARDWARE=true uvicorn app.main:app --reload`
  - [ ] `GET /api/v1/forex/rates` returns rates
  - [ ] `GET /api/v1/forex/connectivity` returns `{"online": true}`
  - [ ] `GET /api/v1/forex/quote/usd-to-php?amount=100` returns correct quote
  - [ ] Full flow: start → simulate-insert → confirm → dispense
- [ ] Frontend: Navigate forex flow with backend connected
  - [ ] Rates load from backend (not mock)
  - [ ] Insert money triggers backend bill acceptance
  - [ ] Confirm triggers backend dispense
  - [ ] Success/error screens reflect backend state
