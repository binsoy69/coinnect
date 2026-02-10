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
    USD_100 = "USD_100"
    EUR_5 = "EUR_5"
    EUR_10 = "EUR_10"
    EUR_20 = "EUR_20"


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
    BillDenom.USD_100: SortSlot.SLOT_7,
    BillDenom.EUR_5: SortSlot.SLOT_8,
    BillDenom.EUR_10: SortSlot.SLOT_8,
    BillDenom.EUR_20: SortSlot.SLOT_8,
}

# Slot -> stepper position (1/16 microstepping, steps from home)
SLOT_POSITIONS: Dict[SortSlot, int] = {
    SortSlot.SLOT_1: 2920,
    SortSlot.SLOT_2: 8760,
    SortSlot.SLOT_3: 14600,
    SortSlot.SLOT_4: 20440,
    SortSlot.SLOT_5: 26280,
    SortSlot.SLOT_6: 32120,
    SortSlot.SLOT_7: 37960,
    SortSlot.SLOT_8: 43800,
}

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
    BillDenom.USD_100: 100,
    BillDenom.EUR_5: 5,
    BillDenom.EUR_10: 10,
    BillDenom.EUR_20: 20,
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
    9: BillDenom.USD_100,
    10: BillDenom.EUR_5,
    11: BillDenom.EUR_10,
    12: BillDenom.EUR_20,
}
