import pytest
from unittest.mock import AsyncMock

from app.core.config import Settings
from app.core.constants import BillDenom
from app.core.constants import ControllerType
from app.core.errors import SerialError
from app.core.errors import TimeoutError as HardwareTimeoutError
from app.ml.bill_authenticator import BillAuthResult
from app.services.machine_status import MachineStatus
import healthcheck_api.hardware as hardware_module
from healthcheck_api.hardware import HardwareContext, PartialSerialManager
from healthcheck_api.runner import DiagnosticsRunner


class FailingGPIO:
    def __init__(self):
        self.stopped = False

    async def motor_forward(self, speed: int):
        raise RuntimeError("forward failed")

    async def motor_stop(self):
        self.stopped = True

    async def motor_brake(self) -> None:
        pass


class FakeCoinController:
    def __init__(self):
        self.enabled_calls = []

    async def set_coin_acceptor_enabled(self, enabled: bool):
        self.enabled_calls.append(enabled)
        return {"status": "OK", "enabled": enabled}


class FakeGPIO:
    def __init__(self):
        self.entry_detected = True
        self.call_log = []

    async def is_bill_at_entry(self):
        self.call_log.append("is_bill_at_entry")
        return self.entry_detected

    async def is_bill_at_position(self):
        self.call_log.append("is_bill_at_position")
        return True

    async def motor_forward(self, speed: int):
        self.call_log.append(f"motor_forward({speed})")

    async def motor_reverse(self, speed: int):
        self.call_log.append(f"motor_reverse({speed})")

    async def motor_stop(self):
        self.call_log.append("motor_stop")

    async def motor_brake(self) -> None:
        self.call_log.append("motor_brake")

    async def uv_led_on(self):
        self.call_log.append("uv_led_on")

    async def uv_led_off(self):
        self.call_log.append("uv_led_off")

    async def white_led_on(self):
        self.call_log.append("white_led_on")

    async def white_led_off(self):
        self.call_log.append("white_led_off")


class FakeCamera:
    def __init__(self):
        self.capture_count = 0
        self.error = None

    async def capture_frame(self):
        import numpy as np

        if self.error:
            raise self.error
        self.capture_count += 1
        return np.zeros((12, 16, 3), dtype=np.uint8)


class FakeAuthenticator:
    def __init__(self):
        self.currency_calls = []
        self.auth_result = BillAuthResult(
            is_genuine=True,
            confidence=0.91,
            raw_label="genuine",
        )
        self.denom_result = BillAuthResult(
            is_genuine=True,
            confidence=0.87,
            denomination=BillDenom.PHP_100,
            raw_label="PHP_100",
        )

    def set_currency(self, currency: str):
        self.currency_calls.append(currency)

    async def authenticate(self, _image):
        return self.auth_result

    async def identify_denomination(self, _image):
        return self.denom_result


class BootResetSerialConnection:
    port_path = "COM_TEST"
    uses_mock = False
    is_connected = True

    def __init__(self):
        self.ready = False

    async def connect(self):
        return None

    async def disconnect(self):
        return None

    async def send_command(self, command: dict, timeout=None):
        if not self.ready:
            raise HardwareTimeoutError(command=command["cmd"], timeout=timeout or 5)
        return {
            "status": "OK",
            "version": "2.1.0",
            "controller": "COIN_SECURITY",
        }


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


async def test_real_serial_identity_probe_waits_for_arduino_boot(monkeypatch):
    settings = Settings(use_mock_serial=False, _env_file=None)
    serial = PartialSerialManager(settings)
    connection = BootResetSerialConnection()

    async def fake_sleep(seconds: float):
        assert seconds >= 2.0
        connection.ready = True

    monkeypatch.setattr(hardware_module.asyncio, "sleep", fake_sleep)

    await serial._connect_one(
        "coin", connection, ControllerType.COIN_SECURITY
    )

    assert serial.snapshot()["coin"]["error"] is None
    assert serial.snapshot()["coin"]["controller"] == "COIN_SECURITY"


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


async def test_live_bill_auth_turns_off_uv_led_and_returns_result():
    settings = Settings(use_mock_serial=True, use_mock_hardware=True, _env_file=None)
    serial = PartialSerialManager(settings)
    gpio = FakeGPIO()
    camera = FakeCamera()
    authenticator = FakeAuthenticator()
    hardware = HardwareContext(
        settings=settings,
        serial_manager=serial,
        bill_controller=object(),
        coin_controller=object(),
        machine_status=object(),
        gpio=gpio,
        camera=camera,
        authenticator=authenticator,
    )
    runner = DiagnosticsRunner(hardware)

    result = await runner.run("bill_image_auth_php")

    assert result.status == "passed"
    assert result.response["currency"] == "PHP"
    assert result.response["is_genuine"] is True
    assert result.response["confidence"] == pytest.approx(0.91)
    assert result.response["image_shape"] == [12, 16, 3]
    assert authenticator.currency_calls == ["PHP"]
    assert gpio.call_log[-1] == "uv_led_off"


async def test_live_bill_denom_turns_off_white_led_and_returns_result():
    settings = Settings(use_mock_serial=True, use_mock_hardware=True, _env_file=None)
    serial = PartialSerialManager(settings)
    gpio = FakeGPIO()
    camera = FakeCamera()
    authenticator = FakeAuthenticator()
    hardware = HardwareContext(
        settings=settings,
        serial_manager=serial,
        bill_controller=object(),
        coin_controller=object(),
        machine_status=object(),
        gpio=gpio,
        camera=camera,
        authenticator=authenticator,
    )
    runner = DiagnosticsRunner(hardware)

    result = await runner.run("bill_image_denom_php")

    assert result.status == "passed"
    assert result.response["currency"] == "PHP"
    assert result.response["denomination"] == "PHP_100"
    assert result.response["confidence"] == pytest.approx(0.87)
    assert result.response["raw_label"] == "PHP_100"
    assert gpio.call_log[-1] == "white_led_off"


async def test_live_bill_auth_turns_off_uv_led_after_camera_failure():
    settings = Settings(use_mock_serial=True, use_mock_hardware=True, _env_file=None)
    serial = PartialSerialManager(settings)
    gpio = FakeGPIO()
    camera = FakeCamera()
    camera.error = RuntimeError("capture failed")
    hardware = HardwareContext(
        settings=settings,
        serial_manager=serial,
        bill_controller=object(),
        coin_controller=object(),
        machine_status=object(),
        gpio=gpio,
        camera=camera,
        authenticator=FakeAuthenticator(),
    )
    runner = DiagnosticsRunner(hardware)

    result = await runner.run("bill_image_auth_php")

    assert result.status == "failed"
    assert "capture failed" in result.error
    assert gpio.call_log[-1] == "uv_led_off"


async def test_full_bill_acceptor_flow_waits_for_entry_then_stores_bill():
    settings = Settings(
        use_mock_serial=True,
        use_mock_hardware=True,
        led_stabilization_delay=0,
        bill_pull_duration=0,
        bill_store_duration=0,
        bill_eject_duration=0,
        _env_file=None,
    )
    serial = PartialSerialManager(settings)
    gpio = FakeGPIO()
    camera = FakeCamera()
    authenticator = FakeAuthenticator()
    bill_controller = AsyncMock()
    bill_controller.sort = AsyncMock()
    machine_status = MachineStatus(settings)
    hardware = HardwareContext(
        settings=settings,
        serial_manager=serial,
        bill_controller=bill_controller,
        coin_controller=object(),
        machine_status=machine_status,
        gpio=gpio,
        camera=camera,
        authenticator=authenticator,
    )
    runner = DiagnosticsRunner(hardware)

    result = await runner.run("bill_acceptor_flow_php")

    assert result.status == "passed"
    assert result.response["success"] is True
    assert result.response["denomination"] == "PHP_100"
    assert gpio.call_log[0] == "is_bill_at_entry"
    assert "motor_forward(60)" in gpio.call_log
    assert gpio.call_log.index("motor_stop") < gpio.call_log.index("uv_led_on")
    assert camera.capture_count == 2
    bill_controller.sort.assert_awaited_once_with(BillDenom.PHP_100)
    assert machine_status.snapshot().consumables.bill_storage_counts["PHP_100"] == 1


async def test_full_bill_acceptor_flow_rejects_fake_bill_without_sorting():
    settings = Settings(
        use_mock_serial=True,
        use_mock_hardware=True,
        led_stabilization_delay=0,
        bill_pull_duration=0,
        bill_store_duration=0,
        bill_eject_duration=0,
        _env_file=None,
    )
    serial = PartialSerialManager(settings)
    gpio = FakeGPIO()
    camera = FakeCamera()
    authenticator = FakeAuthenticator()
    authenticator.auth_result = BillAuthResult(
        is_genuine=False,
        confidence=0.33,
        raw_label="fake",
    )
    bill_controller = AsyncMock()
    bill_controller.sort = AsyncMock()
    hardware = HardwareContext(
        settings=settings,
        serial_manager=serial,
        bill_controller=bill_controller,
        coin_controller=object(),
        machine_status=MachineStatus(settings),
        gpio=gpio,
        camera=camera,
        authenticator=authenticator,
    )
    runner = DiagnosticsRunner(hardware)

    result = await runner.run("bill_acceptor_flow_php")

    assert result.status == "passed"
    assert result.response["success"] is False
    assert result.response["error"] == "NOT_GENUINE"
    assert "motor_reverse(80)" in gpio.call_log
    bill_controller.sort.assert_not_awaited()


async def test_full_bill_acceptor_flow_camera_error_stops_motor_and_leds():
    settings = Settings(
        use_mock_serial=True,
        use_mock_hardware=True,
        led_stabilization_delay=0,
        bill_pull_duration=0,
        bill_store_duration=0,
        bill_eject_duration=0,
        _env_file=None,
    )
    serial = PartialSerialManager(settings)
    gpio = FakeGPIO()
    camera = FakeCamera()
    camera.error = RuntimeError("camera fault")
    bill_controller = AsyncMock()
    bill_controller.sort = AsyncMock()
    hardware = HardwareContext(
        settings=settings,
        serial_manager=serial,
        bill_controller=bill_controller,
        coin_controller=object(),
        machine_status=MachineStatus(settings),
        gpio=gpio,
        camera=camera,
        authenticator=FakeAuthenticator(),
    )
    runner = DiagnosticsRunner(hardware)

    result = await runner.run("bill_acceptor_flow_php")

    assert result.status == "passed"
    assert "camera fault" in result.response["error"]
    assert "motor_stop" in gpio.call_log
    assert "uv_led_off" in gpio.call_log
    assert "white_led_off" in gpio.call_log
    bill_controller.sort.assert_not_awaited()


async def test_coin_rfid_listen_success():
    settings = Settings(use_mock_serial=True, use_mock_hardware=True, _env_file=None)
    serial = PartialSerialManager(settings)
    await serial.startup()
    try:
        hardware = HardwareContext(
            settings=settings,
            serial_manager=serial,
            bill_controller=object(),
            coin_controller=object(),
            machine_status=object(),
            gpio=object(),
            camera=object(),
        )
        runner = DiagnosticsRunner(hardware)

        # Inject mock RFID scan event into the queue
        event_data = {"event": "RFID", "uid": "A1B2C3D4"}
        serial.event_queue.put_nowait(event_data)

        result = await runner.run("coin_rfid_listen")
        assert result.status == "passed"
        assert result.response == {"event": event_data}
    finally:
        await serial.shutdown()


async def test_coin_rfid_listen_timeout():
    settings = Settings(use_mock_serial=True, use_mock_hardware=True, _env_file=None)
    serial = PartialSerialManager(settings)
    await serial.startup()
    try:
        hardware = HardwareContext(
            settings=settings,
            serial_manager=serial,
            bill_controller=object(),
            coin_controller=object(),
            machine_status=object(),
            gpio=object(),
            camera=object(),
        )
        runner = DiagnosticsRunner(hardware)

        async def mock_wait_for_event(event_name: str, timeout: float):
            raise TimeoutError(f"Timed out waiting for {event_name}")

        runner._wait_for_event = mock_wait_for_event
        result = await runner.run("coin_rfid_listen")
        assert result.status == "failed"
        assert "Timed out waiting for RFID" in result.error
    finally:
        await serial.shutdown()


async def test_all_registered_tests_have_handlers():
    settings = Settings(use_mock_serial=True, use_mock_hardware=True, _env_file=None)
    hardware = HardwareContext(
        settings=settings,
        serial_manager=object(),
        bill_controller=object(),
        coin_controller=object(),
        machine_status=object(),
        gpio=object(),
        camera=object(),
    )
    runner = DiagnosticsRunner(hardware)
    for test_id in runner._tests.keys():
        assert test_id in runner._handlers, f"Missing handler for test ID: {test_id}"


