"""Unit tests for ForexRateService."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import Settings
from app.core.errors import RateUnavailableError
from app.models.forex import ExchangeRateCache, ForexQuote
from app.services.forex_rate_service import ForexRateService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_settings():
    return Settings(
        use_mock_serial=True,
        use_mock_hardware=True,
        mock_delay=0.0,
        serial_port_bill="MOCK_BILL",
        serial_port_coin="MOCK_COIN",
        environment="test",
        db_url="sqlite+aiosqlite:///:memory:",
        forex_api_key="test_key",
        forex_fee_usd_to_php=5.0,
        forex_fee_php_to_usd=5.0,
        forex_fee_eur_to_php=4.0,
        forex_fee_php_to_eur=4.0,
    )


@pytest.fixture
def mock_ws():
    ws = AsyncMock()
    ws.broadcast = AsyncMock()
    return ws


@pytest.fixture
def service(test_settings, mock_ws):
    return ForexRateService(test_settings, mock_ws)


@pytest.fixture
def service_with_cache(service):
    """Service with pre-populated valid cache."""
    now = datetime.utcnow()
    service._cache = ExchangeRateCache(
        rates={"USD": 58.7656, "EUR": 61.7246},
        fetched_at=now,
        expires_at=now + timedelta(hours=24),
    )
    service._is_online = True
    return service


@pytest.fixture
def service_with_expired_cache(service):
    """Service with expired cache."""
    past = datetime.utcnow() - timedelta(hours=48)
    service._cache = ExchangeRateCache(
        rates={"USD": 58.0, "EUR": 61.0},
        fetched_at=past,
        expires_at=past + timedelta(hours=24),
    )
    service._is_online = False
    return service


# ---------------------------------------------------------------------------
# 1. Rate retrieval tests
# ---------------------------------------------------------------------------


class TestGetRate:
    def test_valid_cache_returns_rate(self, service_with_cache):
        rate = service_with_cache.get_rate("USD")
        assert rate == 58.7656

    def test_valid_cache_returns_eur_rate(self, service_with_cache):
        rate = service_with_cache.get_rate("EUR")
        assert rate == 61.7246

    def test_expired_cache_raises(self, service_with_expired_cache):
        with pytest.raises(RateUnavailableError):
            service_with_expired_cache.get_rate("USD")

    def test_no_cache_raises(self, service):
        with pytest.raises(RateUnavailableError):
            service.get_rate("USD")

    def test_unknown_currency_raises(self, service_with_cache):
        with pytest.raises(RateUnavailableError, match="No rate available"):
            service_with_cache.get_rate("GBP")


# ---------------------------------------------------------------------------
# 2. Fee percentage tests
# ---------------------------------------------------------------------------


class TestGetFeePercentage:
    def test_usd_to_php_fee(self, service_with_cache):
        assert service_with_cache.get_fee_percentage("usd-to-php") == 5.0

    def test_php_to_usd_fee(self, service_with_cache):
        assert service_with_cache.get_fee_percentage("php-to-usd") == 5.0

    def test_eur_to_php_fee(self, service_with_cache):
        assert service_with_cache.get_fee_percentage("eur-to-php") == 4.0

    def test_php_to_eur_fee(self, service_with_cache):
        assert service_with_cache.get_fee_percentage("php-to-eur") == 4.0

    def test_unknown_service_returns_default(self, service_with_cache):
        assert service_with_cache.get_fee_percentage("gbp-to-php") == 5.0


# ---------------------------------------------------------------------------
# 3. Quote calculation tests
# ---------------------------------------------------------------------------


class TestGetQuote:
    def test_usd_to_php_quote(self, service_with_cache):
        """100 USD at 58.7656 rate, 5% fee."""
        quote = service_with_cache.get_quote("usd-to-php", 100)
        assert quote.from_currency == "USD"
        assert quote.to_currency == "PHP"
        assert quote.rate == 58.7656
        assert quote.input_amount == 100
        # converted: 100 * 58.7656 = 5876.56 -> 5877
        assert quote.converted_amount == 5877
        # fee: 5877 * 0.05 = 293.85 -> 294
        assert quote.fee_amount == 294
        # output: 5877 - 294 = 5583
        assert quote.output_amount == 5583

    def test_php_to_usd_quote(self, service_with_cache):
        """50 USD out, rate 58.7656, 5% fee."""
        quote = service_with_cache.get_quote("php-to-usd", 50)
        assert quote.from_currency == "PHP"
        assert quote.to_currency == "USD"
        # input_amount = PHP needed to insert
        # 50 * 58.7656 = 2938.28 -> 2938 + fee
        assert quote.output_amount == 50  # User receives 50 USD

    def test_eur_to_php_quote(self, service_with_cache):
        """20 EUR at 61.7246, 4% fee."""
        quote = service_with_cache.get_quote("eur-to-php", 20)
        assert quote.from_currency == "EUR"
        assert quote.to_currency == "PHP"
        assert quote.rate == 61.7246
        assert quote.input_amount == 20

    def test_php_to_eur_quote(self, service_with_cache):
        """10 EUR out, 4% fee."""
        quote = service_with_cache.get_quote("php-to-eur", 10)
        assert quote.from_currency == "PHP"
        assert quote.to_currency == "EUR"
        assert quote.output_amount == 10

    def test_quote_no_cache_raises(self, service):
        with pytest.raises(RateUnavailableError):
            service.get_quote("usd-to-php", 100)

    def test_quote_expired_cache_raises(self, service_with_expired_cache):
        with pytest.raises(RateUnavailableError):
            service_with_expired_cache.get_quote("usd-to-php", 100)

    def test_quote_has_locked_at(self, service_with_cache):
        quote = service_with_cache.get_quote("usd-to-php", 100)
        assert quote.locked_at is not None
        assert isinstance(quote.locked_at, datetime)


# ---------------------------------------------------------------------------
# 4. Properties tests
# ---------------------------------------------------------------------------


class TestProperties:
    def test_is_online_default_false(self, service):
        assert service.is_online is False

    def test_rates_valid_default_false(self, service):
        assert service.rates_valid is False

    def test_current_rates_empty(self, service):
        assert service.current_rates == {}

    def test_current_rates_populated(self, service_with_cache):
        rates = service_with_cache.current_rates
        assert "USD" in rates
        assert "EUR" in rates
        assert rates["USD"] == 58.7656

    def test_is_online_with_cache(self, service_with_cache):
        assert service_with_cache.is_online is True

    def test_rates_valid_with_cache(self, service_with_cache):
        assert service_with_cache.rates_valid is True
