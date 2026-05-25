import pytest

from app.core.config import Settings
from app.core.errors import SerialError
from healthcheck_api.hardware import HardwareContext, PartialSerialManager
from healthcheck_api.runner import DiagnosticsRunner


class FailingGPIO:
    def __init__(self):
        self.stopped = False

    async def motor_forward(self, speed: int):
        raise RuntimeError("forward failed")

    async def motor_stop(self):
        self.stopped = True


class FakeCoinController:
    def __init__(self):
        self.enabled_calls = []

    async def set_coin_acceptor_enabled(self, enabled: bool):
        self.enabled_calls.append(enabled)
        return {"status": "OK", "enabled": enabled}


@pytest.mark.parametrize(
    "env_value",
    ["true"],
)
async def test_gpio_motor_test_cleans_up_after_failure(monkeypatch, env_value):
    monkeypatch.setenv("USE_MOCK_SERIAL", env_value)
    monkeypatch.setenv("USE_MOCK_HARDWARE", env_value)

    settings = Settings(
        use_mock_serial=True,
        use_mock_hardware=True,
        _env_file=None,
    )
    serial = PartialSerialManager(settings)
    gpio = FailingGPIO()
    hardware = HardwareContext(
        settings=settings,
        serial_manager=serial,
        bill_controller=object(),
        coin_controller=object(),
        machine_status=object(),
        gpio=gpio,
        camera=object(),
    )
    runner = DiagnosticsRunner(hardware)

    result = await runner.run("rpi_conveyor_forward")

    assert result.status == "failed"
    assert gpio.stopped is True


async def test_swapped_serial_ports_are_reported_before_actuation():
    settings = Settings(
        use_mock_serial=True,
        serial_port_bill="MOCK_COIN",
        serial_port_coin="MOCK_BILL",
        mock_delay=0,
        _env_file=None,
    )
    serial = PartialSerialManager(settings)

    await serial.startup()
    try:
        snapshot = serial.snapshot()

        assert snapshot["bill"]["error"] is not None
        assert "expected BILL" in snapshot["bill"]["error"]
        assert "got COIN_SECURITY" in snapshot["bill"]["error"]
        assert snapshot["coin"]["error"] is not None
        assert "expected COIN_SECURITY" in snapshot["coin"]["error"]
        assert "got BILL" in snapshot["coin"]["error"]

        with pytest.raises(SerialError):
            await serial.send_coin_command(
                {"cmd": "COIN_DISPENSE", "denom": 1, "count": 1}
            )
    finally:
        await serial.shutdown()


async def test_coin_acceptor_listen_disables_acceptor_after_timeout(monkeypatch):
    monkeypatch.setenv("USE_MOCK_SERIAL", "true")
    monkeypatch.setenv("USE_MOCK_HARDWARE", "true")

    settings = Settings(
        use_mock_serial=True,
        use_mock_hardware=True,
        _env_file=None,
    )
    serial = PartialSerialManager(settings)

    await serial.startup()
    try:
        coin_controller = FakeCoinController()
        hardware = HardwareContext(
            settings=settings,
            serial_manager=serial,
            bill_controller=object(),
            coin_controller=coin_controller,
            machine_status=object(),
            gpio=object(),
            camera=object(),
        )
        runner = DiagnosticsRunner(hardware)

        async def fail_wait(event_name: str, timeout: float):
            raise TimeoutError(f"Timed out waiting for {event_name}")

        runner._wait_for_event = fail_wait
        result = await runner.run("coin_acceptor_listen")

        assert result.status == "failed"
        assert coin_controller.enabled_calls == [True, False]
    finally:
        await serial.shutdown()
