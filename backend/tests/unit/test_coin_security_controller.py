import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.errors import HardwareError
from app.drivers.coin_security_controller import CoinSecurityController


@pytest.fixture
def mock_serial_manager():
    manager = AsyncMock()
    manager._settings = MagicMock()
    manager._settings.coin_dispense_timeout_factor = 0.8
    manager._settings.coin_dispense_timeout_base = 5.0
    manager._settings.tamper_sustain_ms = 3000
    manager._settings.tamper_max_gap_ms = 750
    return manager


@pytest.fixture
def controller(mock_serial_manager):
    return CoinSecurityController(mock_serial_manager)


class TestCoinDispense:
    operation_id = "123e4567-e89b-12d3-a456-426614174000"

    async def test_coin_dispense_success(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK", "dispensed": 3
        }
        resp = await controller.coin_dispense(denom=5, count=3, operation_id=self.operation_id)
        assert resp.dispensed == 3

    async def test_coin_dispense_error(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "ERROR", "code": "INVALID_DENOM"
        }
        with pytest.raises(HardwareError) as exc_info:
            await controller.coin_dispense(denom=7, count=1, operation_id=self.operation_id)
        assert exc_info.value.code == "INVALID_DENOM"

    async def test_operation_acknowledgement_error_is_not_ignored(
        self, controller, mock_serial_manager
    ):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "ERROR", "code": "PARSE_ERROR"
        }

        with pytest.raises(HardwareError) as exc_info:
            await controller.acknowledge_operation(self.operation_id)

        assert exc_info.value.code == "PARSE_ERROR"


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


class TestCoinAcceptorEnable:
    async def test_enable_coin_acceptor(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK", "enabled": True
        }

        resp = await controller.set_coin_acceptor_enabled(True)

        assert resp.enabled is True
        mock_serial_manager.send_coin_command.assert_awaited_once_with(
            {"cmd": "COIN_ACCEPTOR_ENABLE", "enabled": True}
        )

    async def test_disable_coin_acceptor(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK", "enabled": False
        }

        resp = await controller.set_coin_acceptor_enabled(False)

        assert resp.enabled is False
        mock_serial_manager.send_coin_command.assert_awaited_once_with(
            {"cmd": "COIN_ACCEPTOR_ENABLE", "enabled": False}
        )


class TestCoinSorterPosition:
    async def test_set_sorter_position(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK",
            "sorter_position": "LEFT",
            "sorter_angle": 45,
        }

        resp = await controller.set_coin_sorter_position("LEFT")

        assert resp.sorter_position == "LEFT"
        assert resp.sorter_angle == 45
        mock_serial_manager.send_coin_command.assert_awaited_once_with(
            {"cmd": "COIN_SORTER_POSITION", "position": "LEFT"}
        )

    async def test_coin_status(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.return_value = {
            "status": "OK",
            "acceptor_enabled": False,
            "sorter_position": "CENTER",
            "sorter_angle": 81,
            "session_total": 0,
        }

        resp = await controller.coin_status()

        assert resp.acceptor_enabled is False
        assert resp.sorter_position == "CENTER"
        assert resp.sorter_angle == 81
        assert resp.session_total == 0


class TestSecurityLock:
    async def test_lock(self, controller, mock_serial_manager):
        mock_serial_manager.send_coin_command.side_effect = [
            {"status": "OK", "sustain_ms": 3000, "max_gap_ms": 750},
            {"status": "OK", "locked": True},
        ]
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
            "status": "OK", "version": "2.1.0", "controller": "COIN_SECURITY"
        }
        resp = await controller.version()
        assert resp.controller == "COIN_SECURITY"


@pytest.mark.parametrize("response", [
    {"status": "ERROR", "code": "UNKNOWN_CMD"},
    {"status": "OK", "sustain_ms": 2000, "max_gap_ms": 750},
    {"status": "OK", "sustain_ms": "3000", "max_gap_ms": 750},
    {"status": "OK"},
])
@pytest.mark.parametrize("action", ["security_lock", "reset"])
async def test_configuration_failure_prevents_arming(controller, mock_serial_manager, response, action):
    mock_serial_manager.send_coin_command.return_value = response
    with pytest.raises(HardwareError):
        await getattr(controller, action)()
    mock_serial_manager.send_coin_command.assert_awaited_once_with(
        {"cmd": "SECURITY_CONFIG", "sustain_ms": 3000, "max_gap_ms": 750}
    )


async def test_reset_configures_before_arming(controller, mock_serial_manager):
    mock_serial_manager.send_coin_command.side_effect = [
        {"status": "OK", "sustain_ms": 3000, "max_gap_ms": 750}, {"status": "OK"}
    ]
    await controller.reset()
    assert [c.args[0]["cmd"] for c in mock_serial_manager.send_coin_command.await_args_list] == [
        "SECURITY_CONFIG", "RESET"
    ]


@pytest.mark.parametrize("sustain,gap", [(250, 250), (3000, 3000), (3000, 249), (60001, 750), (3000.0, 750), (True, 750)])
def test_invalid_tamper_settings(sustain, gap):
    from app.core.config import Settings
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(_env_file=None, tamper_sustain_ms=sustain, tamper_max_gap_ms=gap)


async def test_custom_security_thresholds(controller, mock_serial_manager):
    mock_serial_manager._settings.tamper_sustain_ms = 5000
    mock_serial_manager._settings.tamper_max_gap_ms = 1000
    mock_serial_manager.send_coin_command.return_value = {
        "status": "OK", "sustain_ms": 5000, "max_gap_ms": 1000
    }
    await controller.configure_security()
    mock_serial_manager.send_coin_command.assert_awaited_once_with(
        {"cmd": "SECURITY_CONFIG", "sustain_ms": 5000, "max_gap_ms": 1000}
    )


def test_tamper_settings_from_environment(monkeypatch):
    from app.core.config import Settings
    monkeypatch.setenv("TAMPER_SUSTAIN_MS", "4000")
    monkeypatch.setenv("TAMPER_MAX_GAP_MS", "1000")
    settings = Settings(_env_file=None)
    assert (settings.tamper_sustain_ms, settings.tamper_max_gap_ms) == (4000, 1000)
