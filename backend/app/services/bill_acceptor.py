"""Bill acceptance service orchestrating the full bill intake flow.

Coordinates GPIO (motor, sensors, LEDs), camera, ML authentication,
and Arduino sort commands for the bill acceptor system.
"""

import asyncio
import logging
from typing import Optional

from pydantic import BaseModel

from app.api.ws import ConnectionManager
from app.core.config import Settings
from app.core.constants import BillDenom, BILL_DENOM_VALUES
from app.core.errors import StorageFullError
from app.drivers.bill_controller import BillController
from app.drivers.camera_controller import CameraControllerBase
from app.drivers.gpio_controller import GPIOControllerBase
from app.ml.bill_authenticator import BillAuthenticatorBase
from app.models.events import WSEvent, WSEventType
from app.services.machine_status import MachineStatus

logger = logging.getLogger(__name__)


class BillAcceptResult(BaseModel):
    """Result of a bill acceptance attempt."""

    success: bool = False
    denomination: Optional[BillDenom] = None
    value: Optional[int] = None
    auth_confidence: Optional[float] = None
    denom_confidence: Optional[float] = None
    error: Optional[str] = None


class BillAcceptor:
    """Orchestrates the full bill acceptance sequence.

    Flow:
    1. Wait for bill at entry sensor
    2. Pull bill to camera position
    3. UV capture + authenticate
    4. White capture + identify denomination
    5. Check storage capacity
    6. Sort command to Arduino
    7. Store bill in slot
    8. Update inventory
    """

    def __init__(
        self,
        gpio: GPIOControllerBase,
        camera: CameraControllerBase,
        authenticator: BillAuthenticatorBase,
        bill_controller: BillController,
        machine_status: MachineStatus,
        ws_manager: ConnectionManager,
        settings: Settings,
    ):
        self._gpio = gpio
        self._camera = camera
        self._auth = authenticator
        self._bill = bill_controller
        self._status = machine_status
        self._ws = ws_manager
        self._settings = settings

    async def wait_for_bill(self, timeout: Optional[float] = None) -> bool:
        """Poll entry sensor until a bill is detected.

        Args:
            timeout: Max seconds to wait. None = use config default.

        Returns:
            True if bill detected, False on timeout.
        """
        if timeout is None:
            timeout = self._settings.bill_acceptance_timeout

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            if await self._gpio.is_bill_at_entry():
                return True
            await asyncio.sleep(0.05)  # 50ms poll interval
        return False

    async def accept_bill(self) -> BillAcceptResult:
        """Execute full bill acceptance sequence.

        Returns:
            BillAcceptResult with success status and denomination.
        """
        try:
            # Step 1: Pull bill to camera position
            await self._broadcast(WSEventType.BILL_ACCEPTING, {"step": "positioning"})
            positioned = await self._position_bill()
            if not positioned:
                await self._eject_bill()
                return BillAcceptResult(error="TIMEOUT_POSITION")

            # Step 2: UV authentication
            await self._broadcast(WSEventType.BILL_ACCEPTING, {"step": "authenticating"})
            await self._gpio.motor_stop()
            await self._gpio.uv_led_on()
            await asyncio.sleep(self._settings.led_stabilization_delay)

            uv_image = await self._camera.capture_frame()
            auth_result = await self._auth.authenticate(uv_image)

            await self._gpio.uv_led_off()

            if not auth_result.is_genuine:
                logger.warning(
                    f"Bill rejected: not genuine "
                    f"(confidence={auth_result.confidence:.2f})"
                )
                await self._eject_bill()
                await self._broadcast(
                    WSEventType.BILL_REJECTED,
                    {"reason": "NOT_GENUINE", "confidence": auth_result.confidence},
                )
                return BillAcceptResult(
                    error="NOT_GENUINE",
                    auth_confidence=auth_result.confidence,
                )

            # Step 3: Denomination identification
            await self._gpio.white_led_on()
            await asyncio.sleep(self._settings.led_stabilization_delay)

            visible_image = await self._camera.capture_frame()
            denom_result = await self._auth.identify_denomination(visible_image)

            await self._gpio.white_led_off()

            if denom_result.denomination is None:
                logger.warning("Bill rejected: unknown denomination")
                await self._eject_bill()
                await self._broadcast(
                    WSEventType.BILL_REJECTED,
                    {"reason": "UNKNOWN_DENOMINATION"},
                )
                return BillAcceptResult(
                    error="UNKNOWN_DENOMINATION",
                    auth_confidence=auth_result.confidence,
                    denom_confidence=denom_result.confidence,
                )

            denomination = denom_result.denomination

            # Step 4: Check storage capacity
            if self._status.is_storage_full(denomination.value):
                logger.warning(f"Storage full for {denomination.value}")
                await self._eject_bill()
                await self._broadcast(
                    WSEventType.BILL_REJECTED,
                    {"reason": "STORAGE_FULL", "denomination": denomination.value},
                )
                return BillAcceptResult(
                    error="STORAGE_FULL",
                    denomination=denomination,
                    auth_confidence=auth_result.confidence,
                    denom_confidence=denom_result.confidence,
                )

            # Step 5: Sort to correct slot
            await self._broadcast(
                WSEventType.BILL_SORTING,
                {"denomination": denomination.value},
            )
            await self._bill.sort(denomination)

            # Step 6: Store bill
            await self._store_bill()

            # Step 7: Update inventory
            self._status.increment_bill_storage(denomination.value)
            bill_value = BILL_DENOM_VALUES.get(denomination, 0)

            await self._broadcast(
                WSEventType.BILL_STORED,
                {
                    "denomination": denomination.value,
                    "value": bill_value,
                },
            )

            logger.info(
                f"Bill accepted: {denomination.value} "
                f"(auth={auth_result.confidence:.2f}, "
                f"denom={denom_result.confidence:.2f})"
            )

            return BillAcceptResult(
                success=True,
                denomination=denomination,
                value=bill_value,
                auth_confidence=auth_result.confidence,
                denom_confidence=denom_result.confidence,
            )

        except Exception as e:
            logger.error(f"Bill acceptance error: {e}", exc_info=True)
            # Ensure safe state: stop motor, turn off LEDs
            await self._safe_shutdown()
            await self._broadcast(
                WSEventType.ERROR,
                {"error": str(e), "context": "bill_acceptance"},
            )
            return BillAcceptResult(error=str(e))

    async def _position_bill(self) -> bool:
        """Pull bill from entry to camera position.

        Returns:
            True if bill reached camera position, False on timeout.
        """
        await self._gpio.motor_forward(self._settings.bill_pull_speed)

        deadline = (
            asyncio.get_event_loop().time()
            + self._settings.bill_position_timeout
        )
        while asyncio.get_event_loop().time() < deadline:
            if await self._gpio.is_bill_in_position():
                await self._gpio.motor_stop()
                return True
            await asyncio.sleep(0.05)

        await self._gpio.motor_stop()
        logger.warning("Bill position timeout")
        return False

    async def _store_bill(self) -> None:
        """Motor forward to push bill into storage slot."""
        await self._gpio.motor_forward(self._settings.bill_store_speed)
        await asyncio.sleep(self._settings.bill_store_duration)
        await self._gpio.motor_stop()

    async def _eject_bill(self) -> None:
        """Reverse motor to eject bill back to user."""
        await self._gpio.motor_reverse(self._settings.bill_eject_speed)
        await asyncio.sleep(self._settings.bill_eject_duration)
        await self._gpio.motor_stop()

    async def _safe_shutdown(self) -> None:
        """Ensure motor stopped and LEDs off."""
        try:
            await self._gpio.motor_stop()
            await self._gpio.uv_led_off()
            await self._gpio.white_led_off()
        except Exception:
            pass

    async def _broadcast(self, event_type: WSEventType, payload: dict) -> None:
        """Broadcast a WebSocket event."""
        event = WSEvent(type=event_type, payload=payload)
        await self._ws.broadcast(event)
