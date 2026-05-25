"""Diagnostics test execution."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Awaitable, Callable

from app.core.constants import BillDenom
from app.core.errors import HardwareError, SerialError
from app.core.errors import TimeoutError as HardwareTimeoutError

from healthcheck_api.hardware import HardwareContext
from healthcheck_api.models import ComponentGroup, TestDefinition, TestRunResult
from healthcheck_api.paperang import (
    PaperangDiagnosticError,
    PaperangHealthcheckPrinter,
)
from healthcheck_api.registry import build_component_groups, flatten_tests

TestHandler = Callable[[], Awaitable[dict]]


class DiagnosticsBusyError(Exception):
    """Raised when a test is already running."""


class DiagnosticsRunner:
    def __init__(self, hardware: HardwareContext):
        self._hardware = hardware
        self._groups = build_component_groups()
        self._tests = flatten_tests(self._groups)
        self._lock = asyncio.Lock()
        self._history: list[TestRunResult] = []
        self._handlers = self._build_handlers()

    @property
    def component_groups(self) -> list[ComponentGroup]:
        return self._groups

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    @property
    def recent_runs(self) -> list[TestRunResult]:
        return list(reversed(self._history))

    async def run(self, test_id: str) -> TestRunResult:
        definition = self._tests.get(test_id)
        if definition is None:
            raise KeyError(test_id)
        if self._lock.locked():
            raise DiagnosticsBusyError("A diagnostics test is already running")

        await self._lock.acquire()
        try:
            return await self._run_locked(definition)
        finally:
            self._lock.release()

    async def _run_locked(self, definition: TestDefinition) -> TestRunResult:
        started_at = datetime.now(UTC)
        response: dict = {}
        error = None
        error_code = None
        status = "passed"

        try:
            handler = self._handlers[definition.id]
            response = await handler()
        except Exception as exc:
            status = "failed"
            error = str(exc)
            error_code = self._error_code(exc)

        completed_at = datetime.now(UTC)
        result = TestRunResult(
            id=str(uuid.uuid4()),
            test_id=definition.id,
            label=definition.label,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=max(
                0, int((completed_at - started_at).total_seconds() * 1000)
            ),
            response=response,
            error=error,
            error_code=error_code,
        )
        self._history.append(result)
        if len(self._history) > 100:
            self._history = self._history[-100:]
        return result

    def _build_handlers(self) -> dict[str, TestHandler]:
        handlers: dict[str, TestHandler] = {
            "connectivity_bill_ping": self._bill_ping,
            "connectivity_bill_version": self._bill_version,
            "connectivity_coin_ping": self._coin_ping,
            "connectivity_coin_version": self._coin_version,
            "rpi_ir_entry": self._rpi_ir_entry,
            "rpi_ir_position": self._rpi_ir_position,
            "rpi_conveyor_forward": self._rpi_conveyor_forward,
            "rpi_conveyor_reverse": self._rpi_conveyor_reverse,
            "rpi_uv_led": self._rpi_uv_led,
            "rpi_white_led": self._rpi_white_led,
            "rpi_camera_capture": self._rpi_camera_capture,
            "paperang_sample_receipt": self._paperang_sample_receipt,
            "bill_home_sorter": self._bill_home_sorter,
            "bill_sort_status": self._bill_sort_status,
            "coin_security_status": self._coin_security_status,
            "coin_security_lock": self._coin_security_lock,
            "coin_security_unlock": self._coin_security_unlock,
            "coin_reset": self._coin_reset,
            "coin_acceptor_listen": self._coin_acceptor_listen,
            "coin_tamper_listen": self._coin_tamper_listen,
        }

        for definition in self._tests.values():
            if (
                definition.id.startswith("bill_sort_")
                and definition.id != "bill_sort_status"
            ):
                denom = BillDenom(definition.id.removeprefix("bill_sort_"))
                handlers[definition.id] = self._bill_sort_handler(denom)
            elif definition.id.startswith("bill_dispenser_status_"):
                denom = BillDenom(
                    definition.id.removeprefix("bill_dispenser_status_")
                )
                handlers[definition.id] = self._bill_dispenser_status_handler(denom)
            elif definition.id.startswith("bill_dispense_"):
                denom = BillDenom(definition.id.removeprefix("bill_dispense_"))
                handlers[definition.id] = self._bill_dispense_handler(denom)
            elif definition.id.startswith("coin_dispense_"):
                denom = int(definition.id.removeprefix("coin_dispense_"))
                handlers[definition.id] = self._coin_dispense_handler(denom)

        return handlers

    async def _bill_ping(self) -> dict:
        return (await self._hardware.bill_controller.ping()).model_dump()

    async def _bill_version(self) -> dict:
        return (await self._hardware.bill_controller.version()).model_dump()

    async def _coin_ping(self) -> dict:
        return (await self._hardware.coin_controller.ping()).model_dump()

    async def _coin_version(self) -> dict:
        return (await self._hardware.coin_controller.version()).model_dump()

    async def _rpi_ir_entry(self) -> dict:
        gpio = self._require_gpio()
        return {"detected": await gpio.is_bill_at_entry()}

    async def _rpi_ir_position(self) -> dict:
        gpio = self._require_gpio()
        return {"detected": await gpio.is_bill_in_position()}

    async def _rpi_conveyor_forward(self) -> dict:
        gpio = self._require_gpio()
        speed = self._hardware.settings.bill_pull_speed
        try:
            await gpio.motor_forward(speed)
            await asyncio.sleep(1.0)
            return {"direction": "forward", "speed": speed, "duration_seconds": 1}
        finally:
            await gpio.motor_stop()

    async def _rpi_conveyor_reverse(self) -> dict:
        gpio = self._require_gpio()
        speed = self._hardware.settings.bill_eject_speed
        try:
            await gpio.motor_reverse(speed)
            await asyncio.sleep(1.0)
            return {"direction": "reverse", "speed": speed, "duration_seconds": 1}
        finally:
            await gpio.motor_stop()

    async def _rpi_uv_led(self) -> dict:
        gpio = self._require_gpio()
        try:
            await gpio.uv_led_on()
            await asyncio.sleep(1.0)
            return {"uv_led": "on", "duration_seconds": 1}
        finally:
            await gpio.uv_led_off()

    async def _rpi_white_led(self) -> dict:
        gpio = self._require_gpio()
        try:
            await gpio.white_led_on()
            await asyncio.sleep(1.0)
            return {"white_led": "on", "duration_seconds": 1}
        finally:
            await gpio.white_led_off()

    async def _rpi_camera_capture(self) -> dict:
        camera = self._require_camera()
        frame = await camera.capture_frame()
        shape = getattr(frame, "shape", None)
        return {
            "captured": True,
            "shape": list(shape) if shape is not None else None,
        }

    async def _paperang_sample_receipt(self) -> dict:
        printer = PaperangHealthcheckPrinter(self._hardware.settings)
        return await printer.print_sample_receipt()

    async def _bill_home_sorter(self) -> dict:
        return (await self._hardware.bill_controller.home()).model_dump()

    async def _bill_sort_status(self) -> dict:
        return (await self._hardware.bill_controller.sort_status()).model_dump()

    def _bill_sort_handler(self, denom: BillDenom) -> TestHandler:
        async def handler() -> dict:
            return (await self._hardware.bill_controller.sort(denom)).model_dump()

        return handler

    def _bill_dispenser_status_handler(self, denom: BillDenom) -> TestHandler:
        async def handler() -> dict:
            return (
                await self._hardware.bill_controller.dispense_status(denom)
            ).model_dump()

        return handler

    def _bill_dispense_handler(self, denom: BillDenom) -> TestHandler:
        async def handler() -> dict:
            return (await self._hardware.bill_controller.dispense(denom, 1)).model_dump()

        return handler

    async def _coin_security_status(self) -> dict:
        return (await self._hardware.coin_controller.security_status()).model_dump()

    async def _coin_security_lock(self) -> dict:
        return (await self._hardware.coin_controller.security_lock()).model_dump()

    async def _coin_security_unlock(self) -> dict:
        return (await self._hardware.coin_controller.security_unlock()).model_dump()

    async def _coin_reset(self) -> dict:
        return (await self._hardware.coin_controller.coin_reset()).model_dump()

    def _coin_dispense_handler(self, denom: int) -> TestHandler:
        async def handler() -> dict:
            return (
                await self._hardware.coin_controller.coin_dispense(denom, 1)
            ).model_dump()

        return handler

    async def _coin_acceptor_listen(self) -> dict:
        self._hardware.serial_manager.require_coin_controller()
        return await self._wait_for_event("COIN_IN", timeout=10.0)

    async def _coin_tamper_listen(self) -> dict:
        self._hardware.serial_manager.require_coin_controller()
        return await self._wait_for_event("TAMPER", timeout=10.0)

    async def _wait_for_event(self, event_name: str, timeout: float) -> dict:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for {event_name}")
            data = await asyncio.wait_for(
                self._hardware.serial_manager.event_queue.get(),
                timeout=remaining,
            )
            if data.get("event") == event_name:
                return {"event": data}

    def _require_gpio(self):
        if self._hardware.gpio is None or self._hardware.gpio_error:
            detail = self._hardware.gpio_error or "GPIO not initialized"
            raise RuntimeError(f"GPIO unavailable: {detail}")
        return self._hardware.gpio

    def _require_camera(self):
        if self._hardware.camera is None or self._hardware.camera_error:
            detail = self._hardware.camera_error or "Camera not initialized"
            raise RuntimeError(f"Camera unavailable: {detail}")
        return self._hardware.camera

    @staticmethod
    def _error_code(exc: Exception) -> str | None:
        if isinstance(exc, HardwareError):
            return exc.code
        if isinstance(exc, SerialError):
            return "SERIAL_ERROR"
        if isinstance(exc, HardwareTimeoutError):
            return "TIMEOUT"
        if isinstance(exc, TimeoutError):
            return "TIMEOUT"
        if isinstance(exc, PaperangDiagnosticError):
            return "PRINTER_ERROR"
        return None
