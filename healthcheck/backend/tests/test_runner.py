import pytest

from app.core.config import Settings
from healthcheck_api.hardware import HardwareContext, PartialSerialManager
from healthcheck_api.runner import DiagnosticsRunner


class FailingGPIO:
    def __init__(self):
        self.stopped = False

    async def motor_forward(self, speed: int):
        raise RuntimeError("forward failed")

    async def motor_stop(self):
        self.stopped = True


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
