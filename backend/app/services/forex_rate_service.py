"""Forex rate service using Frankfurter API with local caching.

Responsibilities:
- Fetch live rates from Frankfurter API
- Cache rates locally (24h TTL)
- Provide rate locking for transactions
- Check internet connectivity
- Broadcast rate updates via WebSocket
"""

import asyncio
import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP
from app.models.db_models import ForexQuoteRecord, ForexSetting
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx

from app.api.ws import ConnectionManager
from app.core.config import Settings
from app.core.constants import Currency, ForexServiceType, FOREX_PAIRS
from app.core.errors import RateUnavailableError
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

    def __init__(
        self,
        settings: Settings,
        ws_manager: ConnectionManager,
        machine_status: Optional[Any] = None,
        db_session_factory=None,
    ):
        self._settings = settings
        self._db_factory = db_session_factory
        self._ws = ws_manager
        self._machine_status = machine_status
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

    @property
    def enabled(self):
        return self._settings.environment.lower() != "production" or self._settings.forex_enabled

    async def start(self) -> None:
        """Start the rate service: initial fetch + periodic refresh."""
        await self.initialize_fees()
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
        return self._is_online and self.rates_valid and self.enabled

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
        """Get the configured fee percentage for a forex service type."""
        fee_map = {
            ForexServiceType.USD_TO_PHP: self._settings.forex_fee_usd_to_php,
            ForexServiceType.PHP_TO_USD: self._settings.forex_fee_php_to_usd,
            ForexServiceType.EUR_TO_PHP: self._settings.forex_fee_eur_to_php,
            ForexServiceType.PHP_TO_EUR: self._settings.forex_fee_php_to_eur,
        }
        try:
            return fee_map[ForexServiceType(service_type)]
        except (ValueError, KeyError):
            return 5.0

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
        allowed = {"usd-to-php": [10, 50], "php-to-usd": [10, 50],
                   "eur-to-php": [5, 10], "php-to-eur": [5, 10]}
        if type(amount) is not int or amount not in allowed.get(service_type, []):
            raise ValueError("Unsupported forex service or amount")
        from_currency, to_currency = FOREX_PAIRS[ForexServiceType(service_type)]
        foreign = to_currency if from_currency == Currency.PHP else from_currency
        rate = Decimal(str(self.get_rate(foreign.value)))
        fee_pct = self.validate_fee(self.get_fee_percentage(service_type))
        exact = Decimal(amount) * rate
        principal = int(exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        fee = int((exact * fee_pct / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        buying = from_currency == Currency.PHP
        output = amount if buying else principal - fee
        if output <= 0:
            raise ValueError("Quote must have a positive payout")
        return ForexQuote(
            from_currency=from_currency.value, to_currency=to_currency.value,
            rate=float(1 / rate if buying else rate), php_rate=str(rate),
            input_amount=principal + fee if buying else amount,
            converted_amount=principal, fee_percentage=float(fee_pct), fee_amount=fee,
            output_amount=output, locked_at=datetime.now(timezone.utc).replace(tzinfo=None),
            service_type=service_type, selected_amount=amount,
        )

    @staticmethod
    def validate_fee(value):
        fee = Decimal(str(value))
        if not fee.is_finite() or not 0 <= fee < 100 or fee != fee.quantize(Decimal("0.01")):
            raise ValueError("Forex fee must be from 0 to less than 100 with at most two decimal places")
        return fee

    async def initialize_fees(self):
        if self._db_factory is None:
            return
        async with self._db_factory() as session:
            for service in ForexServiceType:
                key = service.value
                row = await session.get(ForexSetting, key)
                if row is None:
                    row = ForexSetting(key=key, value=str(self.validate_fee(self.get_fee_percentage(key))))
                    session.add(row)
                setattr(self._settings, "forex_fee_" + key.replace("-", "_"), float(self.validate_fee(row.value)))
            await session.commit()

    async def update_fees(self, fees):
        if set(fees) - {s.value for s in ForexServiceType}:
            raise ValueError("Unknown forex fee service")
        validated = {k: self.validate_fee(v) for k, v in fees.items()}
        async with self._db_factory() as session:
            for key, value in validated.items():
                row = await session.get(ForexSetting, key)
                if row is None:
                    session.add(ForexSetting(key=key, value=str(value)))
                else:
                    row.value = str(value)
            await session.commit()
        for key, value in validated.items():
            setattr(self._settings, "forex_fee_" + key.replace("-", "_"), float(value))

    async def create_quote(self, service_type, amount):
        if not await self.check_forex_available():
            raise RateUnavailableError("Online connectivity and valid rates are required")
        quote = self.get_quote(service_type, amount)
        quote.quote_id = str(uuid.uuid4())
        quote.expires_at = quote.locked_at + timedelta(seconds=60)
        async with self._db_factory() as session:
            session.add(ForexQuoteRecord(id=quote.quote_id, data=quote.model_dump(mode="json"), expires_at=quote.expires_at))
            await session.commit()
        return quote

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

        if self._machine_status:
            self._machine_status.update_connectivity(internet_connected=self._is_online)

        if was_online != self._is_online:
            logger.info(
                f"Forex connectivity: {'online' if self._is_online else 'offline'}"
            )
            event = WSEvent(
                type=WSEventType.FOREX_CONNECTIVITY_CHANGED,
                payload={"online": self._is_online},
            )
            await self._ws.broadcast(event)


    async def _fetch_rates(self) -> None:
        """Fetch live rates from Frankfurter API.

        Frankfurter API endpoint:
          GET https://api.frankfurter.dev/v1/latest?base=PHP&symbols=USD,EUR

        We request PHP as base, so we get PHP->USD and PHP->EUR.
        We store the inverse (USD->PHP, EUR->PHP) for convenience.
        """
        try:
            resp = await self._http_client.get(
                self._settings.forex_api_url,
                params={
                    "base": "PHP",
                    "symbols": "USD,EUR",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # Frankfurter API returns: {"amount": 1.0, "base": "PHP", "date": "...", "rates": {"USD": 0.017, "EUR": 0.016}}
            exchange_rates = data.get("rates", {})

            # Store as foreign->PHP rates (inverse of what API gives us)
            rates = {}
            for currency_code, php_to_foreign in exchange_rates.items():
                if php_to_foreign > 0:
                    rates[currency_code] = round(1 / php_to_foreign, 4)

            if not all(k in rates and Decimal(str(rates[k])).is_finite() and rates[k] > 0 for k in ("USD", "EUR")):
                raise ValueError("Incomplete or invalid forex rates")
            now = datetime.now(timezone.utc).replace(tzinfo=None)
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
            interval = (
                self._settings.forex_rate_refresh_interval
                if (self._is_online and self._cache.is_valid)
                else 30  # Fast retry when offline/invalid
            )
            await asyncio.sleep(interval)
            try:
                await self._check_connectivity()
                if self._is_online:
                    await self._fetch_rates()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Rate refresh error: {e}")

