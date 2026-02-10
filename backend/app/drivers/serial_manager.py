"""Serial communication manager with threaded readers and asyncio bridge.

Each serial port gets a dedicated reader thread that pushes parsed JSON into
an asyncio.Queue. Commands are sent via thread-safe locked writes, with
responses routed back through asyncio.Future objects.
"""

import asyncio
import json
import logging
import threading
import time
from typing import Optional

from app.core.config import Settings
from app.core.constants import ControllerType
from app.core.errors import HardwareError, SerialError
from app.core.errors import TimeoutError as HWTimeoutError

logger = logging.getLogger(__name__)


class SerialConnection:
    """Manages a single serial port: threaded reader + asyncio queue bridge."""

    def __init__(
        self,
        port: str,
        baud_rate: int,
        controller_type: ControllerType,
        event_queue: asyncio.Queue,
        timeout: float = 5.0,
        use_mock: bool = False,
        mock_delay: float = 0.0,
    ):
        self._port_path = port
        self._baud_rate = baud_rate
        self._controller_type = controller_type
        self._event_queue = event_queue
        self._timeout = timeout
        self._use_mock = use_mock
        self._mock_delay = mock_delay

        self._serial = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._send_lock = threading.Lock()
        self._pending_response: Optional[asyncio.Future] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self) -> None:
        self._loop = asyncio.get_running_loop()

        if self._use_mock:
            from app.drivers.mock_serial import MockSerial
            self._serial = MockSerial(
                port=self._port_path,
                baudrate=self._baud_rate,
                timeout=self._timeout,
                mock_delay=self._mock_delay,
            )
            logger.info(
                f"MockSerial connected: {self._port_path} "
                f"(controller={self._controller_type.value})"
            )
        else:
            try:
                import serial
                self._serial = serial.Serial(
                    port=self._port_path,
                    baudrate=self._baud_rate,
                    timeout=self._timeout,
                )
                logger.info(
                    f"Serial connected: {self._port_path} "
                    f"(controller={self._controller_type.value})"
                )
            except Exception as e:
                raise SerialError(
                    f"Failed to open {self._port_path}: {e}",
                    port=self._port_path,
                )

        self._running = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name=f"serial-reader-{self._controller_type.value}",
            daemon=True,
        )
        self._reader_thread.start()

    async def disconnect(self) -> None:
        self._running = False
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=3.0)
        if self._serial and self._serial.is_open:
            self._serial.close()
        logger.info(f"Serial disconnected: {self._port_path}")

    async def send_command(
        self, command: dict, timeout: Optional[float] = None
    ) -> dict:
        if not self._serial or not self._serial.is_open:
            raise SerialError("Serial port not open", port=self._port_path)

        timeout = timeout or self._timeout
        future = self._loop.create_future()

        # Set pending response future (reader thread will resolve it)
        self._pending_response = future

        # Send command (thread-safe)
        cmd_line = json.dumps(command) + "\n"
        with self._send_lock:
            try:
                self._serial.write(cmd_line.encode("utf-8"))
                logger.debug(
                    f"[{self._controller_type.value}] TX: {json.dumps(command)}"
                )
            except Exception as e:
                self._pending_response = None
                raise SerialError(
                    f"Write failed on {self._port_path}: {e}",
                    port=self._port_path,
                )

        # Wait for response
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending_response = None
            raise HWTimeoutError(
                command=command.get("cmd", "UNKNOWN"),
                timeout=timeout,
            )

    def _reader_loop(self) -> None:
        """Background thread: reads lines from serial, routes to response or event queue."""
        while self._running:
            try:
                if not self._serial or not self._serial.is_open:
                    time.sleep(0.1)
                    continue

                # Check if data is available
                if hasattr(self._serial, "in_waiting") and self._serial.in_waiting == 0:
                    time.sleep(0.01)
                    continue

                line = self._serial.readline()
                if not line:
                    continue

                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)
                except json.JSONDecodeError:
                    logger.warning(
                        f"[{self._controller_type.value}] "
                        f"Invalid JSON received: {line_str}"
                    )
                    continue

                logger.debug(
                    f"[{self._controller_type.value}] RX: {line_str}"
                )

                # Route: responses have "status", events have "event"
                if "status" in data:
                    self._resolve_response(data)
                elif "event" in data:
                    self._push_event(data)
                else:
                    logger.warning(
                        f"[{self._controller_type.value}] "
                        f"Unclassified message: {line_str}"
                    )

            except Exception as e:
                if self._running:
                    logger.error(
                        f"[{self._controller_type.value}] "
                        f"Reader error: {e}"
                    )
                    time.sleep(0.1)

    def _resolve_response(self, data: dict) -> None:
        """Resolve the pending response future from the reader thread."""
        future = self._pending_response
        if future and not future.done():
            self._pending_response = None
            self._loop.call_soon_threadsafe(future.set_result, data)

    def _push_event(self, data: dict) -> None:
        """Push an unsolicited event to the shared asyncio queue."""
        data["_controller"] = self._controller_type.value
        self._loop.call_soon_threadsafe(
            self._event_queue.put_nowait, data
        )

    @property
    def is_connected(self) -> bool:
        return (
            self._serial is not None
            and self._serial.is_open
            and self._running
        )

    @property
    def mock_serial(self):
        """Access the underlying MockSerial instance (for testing only)."""
        return self._serial


class SerialManager:
    """Manages both serial connections with a shared event queue."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.bill_connection: Optional[SerialConnection] = None
        self.coin_connection: Optional[SerialConnection] = None

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

        await self.bill_connection.connect()
        await self.coin_connection.connect()
        logger.info("SerialManager started (both connections active)")

    async def shutdown(self) -> None:
        if self.bill_connection:
            await self.bill_connection.disconnect()
        if self.coin_connection:
            await self.coin_connection.disconnect()
        logger.info("SerialManager shutdown complete")

    async def send_bill_command(
        self, command: dict, timeout: Optional[float] = None
    ) -> dict:
        if not self.bill_connection:
            raise SerialError("Bill connection not initialized")
        return await self.bill_connection.send_command(command, timeout)

    async def send_coin_command(
        self, command: dict, timeout: Optional[float] = None
    ) -> dict:
        if not self.coin_connection:
            raise SerialError("Coin connection not initialized")
        return await self.coin_connection.send_command(command, timeout)
