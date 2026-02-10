import pytest
from unittest.mock import AsyncMock

from app.core.errors import HardwareError
from app.drivers.coin_security_controller import CoinSecurityController


@pytest.fixture
def mock_serial_manager():
    return AsyncMock()


@pytest.fixture
def controller(mock_serial_manager):
    return CoinSecurityController(mock_serial_manager)


class TestCoinDispense:
    async def test_coin_dispense_success(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK", "dispensed": 3
        }
        resp = await controller.coin_dispense(denom=5, count=3)
        assert resp.dispensed == 3

    async def test_coin_dispense_error(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "ERROR", "code": "INVALID_DENOM"
        }
        with pytest.raises(HardwareError) as exc_info:
            await controller.coin_dispense(denom=7, count=1)
        assert exc_info.value.code == "INVALID_DENOM"


class TestCoinChange:
    async def test_coin_change(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK",
            "breakdown": {"20": 2, "5": 1, "1": 2},
        }
        resp = await controller.coin_change(47)
        assert resp.breakdown["20"] == 2
        total = sum(int(k) * v for k, v in resp.breakdown.items())
        assert total == 47


class TestCoinReset:
    async def test_coin_reset(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK", "previous_total": 150
        }
        resp = await controller.coin_reset()
        assert resp.previous_total == 150


class TestSecurityLock:
    async def test_lock(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK", "locked": True
        }
        resp = await controller.security_lock()
        assert resp.locked is True

    async def test_unlock(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK", "locked": False
        }
        resp = await controller.security_unlock()
        assert resp.locked is False


class TestSecurityStatus:
    async def test_status(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK", "locked": True, "tamper_a": False
        }
        resp = await controller.security_status()
        assert resp.locked is True
        assert resp.tamper_a is False


class TestSystem:
    async def test_ping(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK", "message": "PONG"
        }
        resp = await controller.ping()
        assert resp.message == "PONG"

    async def test_version(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK", "version": "2.0.0", "controller": "COIN_SECURITY"
        }
        resp = await controller.version()
        assert resp.controller == "COIN_SECURITY"
