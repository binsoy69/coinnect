import pytest

from app.core.constants import (
    BILL_DENOM_VALUES,
    COIN_DENOM_VALUES,
    DENOM_TO_SLOT,
    DISPENSER_UNITS,
    SLOT_POSITIONS,
    BillDenom,
    CoinDenom,
    ErrorCode,
    SortSlot,
)


class TestBillDenom:
    def test_all_php_denominations(self):
        php_denoms = [d for d in BillDenom if d.value.startswith("PHP")]
        assert len(php_denoms) == 6

    def test_all_usd_denominations(self):
        usd_denoms = [d for d in BillDenom if d.value.startswith("USD")]
        assert len(usd_denoms) == 3

    def test_all_eur_denominations(self):
        eur_denoms = [d for d in BillDenom if d.value.startswith("EUR")]
        assert len(eur_denoms) == 3

    def test_string_format(self):
        assert BillDenom.PHP_100.value == "PHP_100"
        assert BillDenom.USD_50.value == "USD_50"
        assert BillDenom.EUR_20.value == "EUR_20"


class TestSlotMapping:
    def test_every_denom_has_slot(self):
        for denom in BillDenom:
            assert denom in DENOM_TO_SLOT, f"{denom} missing slot mapping"

    def test_php_slots_are_1_to_6(self):
        for denom in BillDenom:
            if denom.value.startswith("PHP"):
                slot = DENOM_TO_SLOT[denom]
                assert 1 <= slot.value <= 6

    def test_usd_uses_slot_7(self):
        for denom in BillDenom:
            if denom.value.startswith("USD"):
                assert DENOM_TO_SLOT[denom] == SortSlot.SLOT_7

    def test_eur_uses_slot_8(self):
        for denom in BillDenom:
            if denom.value.startswith("EUR"):
                assert DENOM_TO_SLOT[denom] == SortSlot.SLOT_8

    def test_every_slot_has_position(self):
        for slot in SortSlot:
            assert slot in SLOT_POSITIONS

    def test_positions_increase_monotonically(self):
        positions = [SLOT_POSITIONS[SortSlot(i)] for i in range(1, 9)]
        for i in range(1, len(positions)):
            assert positions[i] > positions[i - 1]


class TestDenomValues:
    def test_php_bill_values(self):
        assert BILL_DENOM_VALUES[BillDenom.PHP_20] == 20
        assert BILL_DENOM_VALUES[BillDenom.PHP_1000] == 1000

    def test_coin_values(self):
        assert COIN_DENOM_VALUES[CoinDenom.PHP_1] == 1
        assert COIN_DENOM_VALUES[CoinDenom.PHP_20] == 20

    def test_dispenser_units_cover_all_denoms(self):
        dispensed_denoms = set(DISPENSER_UNITS.values())
        assert dispensed_denoms == set(BillDenom)


class TestErrorCodes:
    def test_all_expected_codes_exist(self):
        expected = [
            "PARSE_ERROR", "UNKNOWN_CMD", "INVALID_DENOM", "INVALID_COUNT",
            "NOT_HOMED", "JAM", "EMPTY", "TIMEOUT", "MOTOR_FAULT", "LOCKED_OUT",
        ]
        for code in expected:
            assert ErrorCode(code)
