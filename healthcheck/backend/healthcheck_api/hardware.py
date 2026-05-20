"""Healthcheck-specific hardware lifecycle wrappers."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import Settings
from app.core.constants import ControllerType
from app.core.errors import SerialError
from app.drivers.bill_controller import BillController
from app.drivers.coin_security_controller import CoinSecurityController
from app.drivers.serial_manager import SerialConnection
from app.services.machine_status import MachineStatus
from healthcheck_api.paperang import paperang_snapshot

logger = logging.getLogger(__name__)


class PartialSerialManager:
    """Serial manager that keeps diagnostics alive if one controller is missing."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.bill_connection: Optional[SerialConnection] = None
        self.coin_connection: Optional[SerialConnection] = None
        self._errors: dict[str, str] = {}

    async def startup(self) -> None:
        self.bill_connection = SerialConnection(
            port=self._settings.serial_port_bill,
            baud_rate=self._settings.baud_rate,
            controller_type=ControllerType.BILL,
            event_queue=self.event_queue,
            timeout=self._settings.serial_timeout,
            use_mock=self._settings.use_mock_serial,
            mock_delay=self._settings.mock_delay,
        )
        self.coin_connection = SerialConnection(
            port=self._settings.serial_port_coin,
            baud_rate=self._settings.baud_rate,
            controller_type=ControllerType.COIN_SECURITY,
            event_queue=self.event_queue,
            timeout=self._settings.serial_timeout,
            use_mock=self._settings.use_mock_serial,
            mock_delay=self._settings.mock_delay,
        )

        await self._connect_one("bill", self.bill_connection)
        await self._connect_one("coin", self.coin_connection)

    async def shutdown(self) -> None:
        for connection in (self.bill_connection, self.coin_connection):
            if connection and connection.is_connected:
                await connection.disconnect()

    async def send_bill_command(
        self, command: dict, timeout: Optional[float] = None
    ) -> dict:
        if not self.bill_connection or not self.bill_connection.is_connected:
            raise SerialError(self._unavailable_message("bill"))
        return await self.bill_connection.send_command(command, timeout)

    async def send_coin_command(
        self, command: dict, timeout: Optional[float] = None
    ) -> dict:
        if not self.coin_connection or not self.coin_connection.is_connected:
            raise SerialError(self._unavailable_message("coin"))
        return await self.coin_connection.send_command(command, timeout)

    def snapshot(self) -> dict:
        return {
            "bill": self._connection_snapshot(
                self.bill_connection,
                self._settings.serial_port_bill,
                self._errors.get("bill"),
            ),
            "coin": self._connection_snapshot(
                self.coin_connection,
                self._settings.serial_port_coin,
                self._errors.get("coin"),
            ),
        }

    async def _connect_one(self, name: str, connection: SerialConnection) -> None:
        try:
            await connection.connect()
            self._errors.pop(name, None)
        except Exception as exc:
            self._errors[name] = str(exc)
            logger.warning("Healthcheck %s serial unavailable: %s", name, exc)

    def _unavailable_message(self, name: str) -> str:
        detail = self._errors.get(name, "not connected")
        return f"{name} controller unavailable: {detail}"

    @staticmethod
    def _connection_snapshot(
        connection: Optional[SerialConnection],
        port: str,
        error: Optional[str],
    ) -> dict:
        return {
            "port": port,
            "connected": bool(connection and connection.is_connected),
            "error": error,
        }


@dataclass
class HardwareContext:
    settings: Settings
    serial_manager: PartialSerialManager
    bill_controller: BillController
    coin_controller: CoinSecurityController
    machine_status: MachineStatus
    gpio: object | None = None
    camera: object | None = None
    gpio_error: str | None = None
    camera_error: str | None = None
    _cleanup_callbacks: list = field(default_factory=list)

    @property
    def serial_snapshot(self) -> dict:
        return self.serial_manager.snapshot()

    @property
    def gpio_snapshot(self) -> dict:
        return {
            "available": self.gpio is not None and self.gpio_error is None,
            "mock": self.settings.use_mock_hardware,
            "error": self.gpio_error,
        }

    @property
    def camera_snapshot(self) -> dict:
        return {
            "available": self.camera is not None and self.camera_error is None,
            "mock": self.settings.use_mock_hardware,
            "device": self.settings.camera_device,
            "error": self.camera_error,
        }

    @property
    def printer_snapshot(self) -> dict:
        return paperang_snapshot(self.settings)

    async def shutdown(self) -> None:
        if self.camera is not None:
            try:
                await self.camera.release()
            except Exception as exc:
                logger.warning("Camera cleanup failed: %s", exc)
        if self.gpio is not None:
            try:
                await self.gpio.cleanup()
            except Exception as exc:
                logger.warning("GPIO cleanup failed: %s", exc)
        await self.serial_manager.shutdown()


async def create_hardware_context(settings: Settings) -> HardwareContext:
    serial_manager = PartialSerialManager(settings)
    await serial_manager.startup()

    machine_status = MachineStatus(settings)
    bill_controller = BillController(serial_manager)  # type: ignore[arg-type]
    coin_controller = CoinSecurityController(serial_manager)  # type: ignore[arg-type]

    context = HardwareContext(
        settings=settings,
        serial_manager=serial_manager,
        bill_controller=bill_controller,
        coin_controller=coin_controller,
        machine_status=machine_status,
    )

    if settings.use_mock_hardware:
        from app.drivers.mock_camera_controller import MockCameraController
        from app.drivers.mock_gpio_controller import MockGPIOController

        context.gpio = MockGPIOController()
        context.camera = MockCameraController()
    else:
        from app.drivers.camera_controller import USBCameraController
        from app.drivers.gpio_controller import RPiGPIOController

        context.gpio = RPiGPIOController()
        context.camera = USBCameraController(settings.camera_device)

    try:
        await context.gpio.setup()
    except Exception as exc:
        context.gpio_error = str(exc)
        logger.warning("Healthcheck GPIO unavailable: %s", exc)

    try:
        await context.camera.initialize()
    except Exception as exc:
        context.camera_error = str(exc)
        logger.warning("Healthcheck camera unavailable: %s", exc)

    return context
