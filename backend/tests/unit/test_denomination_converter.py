import pytest

from app.models.denominations import (
    denom_string_to_value,
    frontend_bills_to_protocol,
    frontend_coins_to_protocol,
    protocol_to_frontend,
    value_to_denom_string,
)


class TestFrontendToProtocol:
    def test_php_bills(self):
        result = frontend_bills_to_protocol({100: 3, 50: 2}, currency="PHP")
        assert result == {"PHP_100": 3, "PHP_50": 2}

    def test_usd_bills(self):
        result = frontend_bills_to_protocol({10: 1, 100: 2}, currency="USD")
        assert result == {"USD_10": 1, "USD_100": 2}

    def test_eur_bills(self):
        result = frontend_bills_to_protocol({5: 4, 20: 1}, currency="EUR")
        assert result == {"EUR_5": 4, "EUR_20": 1}

    def test_unknown_denomination_skipped(self):
        result = frontend_bills_to_protocol({999: 1}, currency="PHP")
        assert result == {}

    def test_empty_input(self):
        result = frontend_bills_to_protocol({})
        assert result == {}


class TestFrontendCoinsToProtocol:
    def test_coins(self):
        result = frontend_coins_to_protocol({5: 3, 1: 2})
        assert result == {"PHP_5": 3, "PHP_1": 2}

    def test_all_coin_denoms(self):
        result = frontend_coins_to_protocol({1: 1, 5: 2, 10: 3, 20: 4})
        assert result == {"PHP_1": 1, "PHP_5": 2, "PHP_10": 3, "PHP_20": 4}


class TestProtocolToFrontend:
    def test_php_bills(self):
        result = protocol_to_frontend({"PHP_100": 3, "PHP_50": 2})
        assert result == {100: 3, 50: 2}

    def test_mixed_currencies(self):
        result = protocol_to_frontend({"PHP_100": 1, "USD_50": 2})
        assert result == {100: 1, 50: 2}

    def test_coins(self):
        result = protocol_to_frontend({"PHP_5": 3, "PHP_1": 2})
        assert result == {5: 3, 1: 2}


class TestDenomStringToValue:
    def test_php(self):
        assert denom_string_to_value("PHP_100") == 100
        assert denom_string_to_value("PHP_1000") == 1000

    def test_usd(self):
        assert denom_string_to_value("USD_50") == 50

    def test_eur(self):
        assert denom_string_to_value("EUR_20") == 20

    def test_coin(self):
        assert denom_string_to_value("PHP_5") == 5

    def test_unknown(self):
        assert denom_string_to_value("UNKNOWN") == 0


class TestValueToDenomString:
    def test_php(self):
        assert value_to_denom_string(100, "PHP") == "PHP_100"

    def test_usd(self):
        assert value_to_denom_string(50, "USD") == "USD_50"

    def test_eur(self):
        assert value_to_denom_string(5, "EUR") == "EUR_5"


class TestRoundTrip:
    def test_php_roundtrip(self):
        original = {20: 5, 100: 3, 500: 1}
        protocol = frontend_bills_to_protocol(original, "PHP")
        restored = protocol_to_frontend(protocol)
        assert restored == original

    def test_coin_roundtrip(self):
        original = {1: 10, 5: 5, 10: 3, 20: 1}
        protocol = frontend_coins_to_protocol(original)
        restored = protocol_to_frontend(protocol)
        assert restored == original
