import pytest
from unittest.mock import AsyncMock

from app.core.constants import BillDenom
from app.core.errors import HardwareError
from app.drivers.bill_controller import BillController


@pytest.fixture
def mock_serial_manager():
    manager = AsyncMock()
    return manager


@pytest.fixture
def controller(mock_serial_manager):
    return BillController(mock_serial_manager)


class TestBillControllerSort:
    async def test_sort_success(self, controller, mock_serial_manager):
        mock_serial_manager.send_bill_command.return_value = {
            "status": "READY", "slot": 3
        }
        resp = await controller.sort(BillDenom.PHP_100)
        assert resp.slot == 3
        mock_serial_manager.send_bill_command.assert_called_once_with(
            {"cmd": "SORT", "denom": "PHP_100"}, timeout=8.0
        )

    async def test_sort_error_raises(self, controller, mock_serial_manager):
        mock_serial_manager.send_bill_command.return_value = {
            "status": "ERROR", "code": "NOT_HOMED"
        }
        with pytest.raises(HardwareError) as exc_info:
            await controller.sort(BillDenom.PHP_100)
        assert exc_info.value.code == "NOT_HOMED"


class TestBillControllerHome:
    async def test_home_success(self, controller, mock_serial_manager):
        mock_serial_manager.send_bill_command.return_value = {
            "status": "OK", "position": 0
        }
        resp = await controller.home()
        assert resp.position == 0

    async def test_home_uses_12s_timeout(self, controller, mock_serial_manager):
        mock_serial_manager.send_bill_command.return_value = {
            "status": "OK", "position": 0
        }
        await controller.home()
        _, kwargs = mock_serial_manager.send_bill_command.call_args
        assert kwargs["timeout"] == 12.0


class TestBillControllerDispense:
    async def test_dispense_success(self, controller, mock_serial_manager):
        mock_serial_manager.send_bill_command.return_value = {
            "status": "OK", "dispensed": 5
        }
        resp = await controller.dispense(BillDenom.PHP_500, 5)
        assert resp.dispensed == 5

    async def test_dispense_timeout_scales_with_count(self, controller, mock_serial_manager):
        mock_serial_manager.send_bill_command.return_value = {
            "status": "OK", "dispensed": 10
        }
        await controller.dispense(BillDenom.PHP_100, 10)
        _, kwargs = mock_serial_manager.send_bill_command.call_args
        assert kwargs["timeout"] == 10 * 2.0 + 5.0

    async def test_dispense_jam_error(self, controller, mock_serial_manager):
        mock_serial_manager.send_bill_command.return_value = {
            "status": "ERROR", "code": "JAM", "dispensed": 2
        }
        with pytest.raises(HardwareError) as exc_info:
            await controller.dispense(BillDenom.PHP_100, 5)
        assert exc_info.value.code == "JAM"
        assert exc_info.value.dispensed == 2


class TestBillControllerStatus:
    async def test_sort_status(self, controller, mock_serial_manager):
        mock_serial_manager.send_bill_command.return_value = {
            "status": "OK", "position": 14600, "slot": 3, "homed": True
        }
        resp = await controller.sort_status()
        assert resp.homed is True
        assert resp.slot == 3

    async def test_dispense_status(self, controller, mock_serial_manager):
        mock_serial_manager.send_bill_command.return_value = {
            "status": "OK", "ready": True
        }
        resp = await controller.dispense_status(BillDenom.PHP_100)
        assert resp.ready is True


class TestBillControllerSystem:
    async def test_ping(self, controller, mock_serial_manager):
        mock_serial_manager.send_bill_command.return_value = {
            "status": "OK", "message": "PONG"
        }
        resp = await controller.ping()
        assert resp.message == "PONG"

    async def test_version(self, controller, mock_serial_manager):
        mock_serial_manager.send_bill_command.return_value = {
            "status": "OK", "version": "2.0.0", "controller": "BILL"
        }
        resp = await controller.version()
        assert resp.controller == "BILL"
