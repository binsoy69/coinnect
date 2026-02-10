from typing import Dict

# Frontend uses integer denomination keys: { 100: 3, 50: 2 }
# Backend serial protocol uses string keys: "PHP_100", "PHP_50"

_PHP_INT_TO_BILL: Dict[int, str] = {
    20: "PHP_20", 50: "PHP_50", 100: "PHP_100",
    200: "PHP_200", 500: "PHP_500", 1000: "PHP_1000",
}

_USD_INT_TO_BILL: Dict[int, str] = {
    10: "USD_10", 50: "USD_50", 100: "USD_100",
}

_EUR_INT_TO_BILL: Dict[int, str] = {
    5: "EUR_5", 10: "EUR_10", 20: "EUR_20",
}

_COIN_INT_TO_DENOM: Dict[int, str] = {
    1: "PHP_1", 5: "PHP_5", 10: "PHP_10", 20: "PHP_20",
}

_CURRENCY_MAPS: Dict[str, Dict[int, str]] = {
    "PHP": _PHP_INT_TO_BILL,
    "USD": _USD_INT_TO_BILL,
    "EUR": _EUR_INT_TO_BILL,
}

# Reverse maps (protocol string -> integer value)
_BILL_TO_INT: Dict[str, int] = {}
for _map in _CURRENCY_MAPS.values():
    for _val, _key in _map.items():
        _BILL_TO_INT[_key] = _val
for _val, _key in _COIN_INT_TO_DENOM.items():
    _BILL_TO_INT[_key] = _val


def frontend_bills_to_protocol(
    counts: Dict[int, int], currency: str = "PHP"
) -> Dict[str, int]:
    """Convert frontend denomination counts to protocol format.

    Example: {100: 3, 50: 2} with currency="PHP" -> {"PHP_100": 3, "PHP_50": 2}
    """
    mapping = _CURRENCY_MAPS.get(currency, _PHP_INT_TO_BILL)
    result = {}
    for value, count in counts.items():
        protocol_key = mapping.get(value)
        if protocol_key is not None:
            result[protocol_key] = count
    return result


def frontend_coins_to_protocol(counts: Dict[int, int]) -> Dict[str, int]:
    """Convert frontend coin counts to protocol format.

    Example: {5: 3, 1: 2} -> {"PHP_5": 3, "PHP_1": 2}
    """
    result = {}
    for value, count in counts.items():
        protocol_key = _COIN_INT_TO_DENOM.get(value)
        if protocol_key is not None:
            result[protocol_key] = count
    return result


def protocol_to_frontend(counts: Dict[str, int]) -> Dict[int, int]:
    """Convert protocol denomination counts to frontend format.

    Example: {"PHP_100": 3, "PHP_50": 2} -> {100: 3, 50: 2}
    """
    result = {}
    for protocol_key, count in counts.items():
        value = _BILL_TO_INT.get(protocol_key)
        if value is not None:
            result[value] = count
    return result


def denom_string_to_value(denom: str) -> int:
    """Extract integer value from protocol denomination string.

    Example: "PHP_100" -> 100, "USD_50" -> 50
    """
    return _BILL_TO_INT.get(denom, 0)


def value_to_denom_string(value: int, currency: str = "PHP") -> str:
    """Convert integer value to protocol denomination string.

    Example: 100, "PHP" -> "PHP_100"
    """
    mapping = _CURRENCY_MAPS.get(currency, _PHP_INT_TO_BILL)
    return mapping.get(value, f"{currency}_{value}")
