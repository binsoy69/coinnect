from enum import Enum
from typing import Dict


class BillDenom(str, Enum):
    PHP_20 = "PHP_20"
    PHP_50 = "PHP_50"
    PHP_100 = "PHP_100"
    PHP_200 = "PHP_200"
    PHP_500 = "PHP_500"
    PHP_1000 = "PHP_1000"
    USD_10 = "USD_10"
    USD_50 = "USD_50"
    EUR_5 = "EUR_5"
    EUR_10 = "EUR_10"


class CoinDenom(int, Enum):
    PHP_1 = 1
    PHP_5 = 5
    PHP_10 = 10
    PHP_20 = 20


class SortSlot(int, Enum):
    SLOT_1 = 1  # PHP_20
    SLOT_2 = 2  # PHP_50
    SLOT_3 = 3  # PHP_100
    SLOT_4 = 4  # PHP_200
    SLOT_5 = 5  # PHP_500
    SLOT_6 = 6  # PHP_1000
    SLOT_7 = 7  # USD (all)
    SLOT_8 = 8  # EUR (all)


class ErrorCode(str, Enum):
    PARSE_ERROR = "PARSE_ERROR"
    UNKNOWN_CMD = "UNKNOWN_CMD"
    INVALID_PARAM = "INVALID_PARAM"
    INVALID_DENOM = "INVALID_DENOM"
    INVALID_COUNT = "INVALID_COUNT"
    NOT_HOMED = "NOT_HOMED"
    JAM = "JAM"
    EMPTY = "EMPTY"
    TIMEOUT = "TIMEOUT"
    MOTOR_FAULT = "MOTOR_FAULT"
    LOCKED_OUT = "LOCKED_OUT"


class ControllerType(str, Enum):
    BILL = "BILL"
    COIN_SECURITY = "COIN_SECURITY"


# Denomination -> sorting slot mapping
DENOM_TO_SLOT: Dict[BillDenom, SortSlot] = {
    BillDenom.PHP_20: SortSlot.SLOT_1,
    BillDenom.PHP_50: SortSlot.SLOT_2,
    BillDenom.PHP_100: SortSlot.SLOT_3,
    BillDenom.PHP_200: SortSlot.SLOT_4,
    BillDenom.PHP_500: SortSlot.SLOT_5,
    BillDenom.PHP_1000: SortSlot.SLOT_6,
    BillDenom.USD_10: SortSlot.SLOT_7,
    BillDenom.USD_50: SortSlot.SLOT_7,
    BillDenom.EUR_5: SortSlot.SLOT_8,
    BillDenom.EUR_10: SortSlot.SLOT_8,
}

# Slot -> stepper position (calibrated coordinates from Arduino)
SLOT_POSITIONS: Dict[SortSlot, int] = {
    SortSlot.SLOT_1: 0,
    SortSlot.SLOT_2: 30000,
    SortSlot.SLOT_3: 60000,
    SortSlot.SLOT_4: 90000,
    SortSlot.SLOT_5: 122500,
    SortSlot.SLOT_6: 153500,
    SortSlot.SLOT_7: 187500,
    SortSlot.SLOT_8: 219500,
}


def update_slot_positions(settings) -> None:
    SLOT_POSITIONS[SortSlot.SLOT_1] = settings.slot_1_position
    SLOT_POSITIONS[SortSlot.SLOT_2] = settings.slot_2_position
    SLOT_POSITIONS[SortSlot.SLOT_3] = settings.slot_3_position
    SLOT_POSITIONS[SortSlot.SLOT_4] = settings.slot_4_position
    SLOT_POSITIONS[SortSlot.SLOT_5] = settings.slot_5_position
    SLOT_POSITIONS[SortSlot.SLOT_6] = settings.slot_6_position
    SLOT_POSITIONS[SortSlot.SLOT_7] = settings.slot_7_position
    SLOT_POSITIONS[SortSlot.SLOT_8] = settings.slot_8_position

# Bill denomination -> integer PHP value
BILL_DENOM_VALUES: Dict[BillDenom, int] = {
    BillDenom.PHP_20: 20,
    BillDenom.PHP_50: 50,
    BillDenom.PHP_100: 100,
    BillDenom.PHP_200: 200,
    BillDenom.PHP_500: 500,
    BillDenom.PHP_1000: 1000,
    BillDenom.USD_10: 10,
    BillDenom.USD_50: 50,
    BillDenom.EUR_5: 5,
    BillDenom.EUR_10: 10,
}

# Coin denomination -> integer PHP value
COIN_DENOM_VALUES: Dict[CoinDenom, int] = {
    CoinDenom.PHP_1: 1,
    CoinDenom.PHP_5: 5,
    CoinDenom.PHP_10: 10,
    CoinDenom.PHP_20: 20,
}

# Bill dispenser unit mapping (unit index -> denomination)
DISPENSER_UNITS: Dict[int, BillDenom] = {
    1: BillDenom.PHP_20,
    2: BillDenom.PHP_50,
    3: BillDenom.PHP_100,
    4: BillDenom.PHP_200,
    5: BillDenom.PHP_500,
    6: BillDenom.PHP_1000,
    7: BillDenom.USD_10,
    8: BillDenom.USD_50,
    9: BillDenom.EUR_5,
    10: BillDenom.EUR_10,
}


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
    Currency.USD: [BillDenom.USD_10, BillDenom.USD_50],
    Currency.EUR: [BillDenom.EUR_5, BillDenom.EUR_10],
}

# Bill denomination -> currency
BILL_DENOM_CURRENCY: Dict[BillDenom, Currency] = {}
for _curr, _denoms in CURRENCY_BILL_DENOMS.items():
    for _d in _denoms:
        BILL_DENOM_CURRENCY[_d] = _curr
