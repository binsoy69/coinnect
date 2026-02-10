import pytest
from pydantic import ValidationError

from app.models.serial_messages import (
    CoinChangeResponse,
    CoinDispenseCommand,
    CoinInEvent,
    DispenseCommand,
    DoorStateEvent,
    ErrorResponse,
    HomeResponse,
    PingResponse,
    ReadyEvent,
    SortCommand,
    SortResponse,
    SortStatusResponse,
    TamperEvent,
    VersionResponse,
)


class TestCommands:
    def test_sort_command_serialization(self):
        cmd = SortCommand(denom="PHP_100")
        d = cmd.model_dump()
        assert d == {"cmd": "SORT", "denom": "PHP_100"}

    def test_sort_command_invalid_denom(self):
        with pytest.raises(ValidationError):
            SortCommand(denom="INVALID")

    def test_dispense_command_valid(self):
        cmd = DispenseCommand(denom="PHP_500", count=3)
        assert cmd.count == 3
        assert cmd.denom == "PHP_500"

    def test_dispense_command_count_too_high(self):
        with pytest.raises(ValidationError):
            DispenseCommand(denom="PHP_100", count=21)

    def test_dispense_command_count_too_low(self):
        with pytest.raises(ValidationError):
            DispenseCommand(denom="PHP_100", count=0)

    def test_coin_dispense_command(self):
        cmd = CoinDispenseCommand(denom=5, count=3)
        d = cmd.model_dump()
        assert d == {"cmd": "COIN_DISPENSE", "denom": 5, "count": 3}


class TestResponses:
    def test_sort_response(self):
        resp = SortResponse(status="READY", slot=3)
        assert resp.slot == 3

    def test_home_response(self):
        resp = HomeResponse(status="OK")
        assert resp.position == 0

    def test_sort_status_response(self):
        resp = SortStatusResponse(
            status="OK", position=14600, slot=3, homed=True
        )
        assert resp.homed is True
        assert resp.position == 14600

    def test_coin_change_response(self):
        resp = CoinChangeResponse(
            status="OK",
            breakdown={"20": 2, "5": 1, "1": 2},
        )
        assert resp.breakdown["20"] == 2
        assert sum(
            int(k) * v for k, v in resp.breakdown.items()
        ) == 47

    def test_error_response(self):
        resp = ErrorResponse(status="ERROR", code="JAM")
        assert resp.code == "JAM"
        assert resp.dispensed is None

    def test_error_response_with_dispensed(self):
        resp = ErrorResponse(status="ERROR", code="JAM", dispensed=1)
        assert resp.dispensed == 1

    def test_ping_response(self):
        resp = PingResponse(status="OK")
        assert resp.message == "PONG"

    def test_version_response(self):
        resp = VersionResponse(
            status="OK", version="2.0.0", controller="BILL"
        )
        assert resp.controller == "BILL"


class TestEvents:
    def test_coin_in_event(self):
        evt = CoinInEvent(event="COIN_IN", denom=5, total=150)
        assert evt.denom == 5
        assert evt.total == 150

    def test_tamper_event(self):
        evt = TamperEvent(event="TAMPER", sensor="A")
        assert evt.sensor == "A"

    def test_door_state_event(self):
        evt = DoorStateEvent(event="DOOR_STATE", locked=True)
        assert evt.locked is True

    def test_ready_event(self):
        evt = ReadyEvent(
            event="READY", version="2.0.0", controller="COIN_SECURITY"
        )
        assert evt.controller == "COIN_SECURITY"

    def test_coin_in_from_dict(self):
        data = {"event": "COIN_IN", "denom": 10, "total": 60}
        evt = CoinInEvent(**data)
        assert evt.denom == 10
