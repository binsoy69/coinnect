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
            php_equivalent = amount * php_per_foreign
            fee_amount = round(php_equivalent * (fee_pct / 100))
            total_php_due = round(php_equivalent) + fee_amount

            return ForexQuote(
                from_currency=from_currency.value,
                to_currency=to_currency.value,
                rate=round(1 / php_per_foreign, 6),
                input_amount=total_php_due,
                converted_amount=round(php_equivalent),
                fee_percentage=fee_pct,
                fee_amount=fee_amount,
                output_amount=amount,
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
                input_amount=amount,
                converted_amount=round(php_equivalent),
                fee_percentage=fee_pct,
                fee_amount=fee_amount,
                output_amount=output_php,
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
