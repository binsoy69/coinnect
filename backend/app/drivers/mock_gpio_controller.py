"""Mock GPIO controller for development and testing without Raspberry Pi hardware."""

import asyncio
import logging
import time
from typing import List, Optional

from app.drivers.gpio_controller import GPIOControllerBase

logger = logging.getLogger(__name__)


class MockGPIOController(GPIOControllerBase):
    """Mock GPIO that simulates bill acceptor hardware behavior.
    
    Configurable parameters:
        bill_at_entry_delay: seconds until bill appears at entry sensor
        bill_in_position_delay: seconds until bill reaches camera position
        simulate_jam: if True, bill never reaches camera position
    """

    def __init__(
        self,
        bill_at_entry_delay: float = 0.0,
        bill_in_position_delay: float = 0.0,
        simulate_jam: bool = False,
    ):
        self.bill_at_entry_delay = bill_at_entry_delay
        self.bill_in_position_delay = bill_in_position_delay
        self.simulate_jam = simulate_jam

        # Observable state
        self.motor_state: str = "stopped"  # "stopped", "forward", "reverse"
        self.motor_speed: int = 0
        self.uv_led_state: bool = False
        self.white_led_state: bool = False

        # Simulated sensor state (controlled externally or by timing)
        self._bill_at_entry: bool = False
        self._bill_in_position: bool = False

        # Track motor start time for position simulation
        self._motor_forward_start: Optional[float] = None

        # Call log for test assertions
        self.call_log: List[str] = []
        self._is_setup = False

    async def setup(self) -> None:
        self.call_log.append("setup")
        self._is_setup = True
        logger.info("MockGPIO initialized")

    async def cleanup(self) -> None:
        self.call_log.append("cleanup")
        self.motor_state = "stopped"
        self.motor_speed = 0
        self.uv_led_state = False
        self.white_led_state = False
        self._is_setup = False
        logger.info("MockGPIO cleaned up")

    async def motor_forward(self, speed: int = 60) -> None:
        self.call_log.append(f"motor_forward({speed})")
        self.motor_state = "forward"
        self.motor_speed = speed
        self._motor_forward_start = time.monotonic()

    async def motor_reverse(self, speed: int = 80) -> None:
        self.call_log.append(f"motor_reverse({speed})")
        self.motor_state = "reverse"
        self.motor_speed = speed
        self._motor_forward_start = None

    async def motor_stop(self) -> None:
        self.call_log.append("motor_stop")
        self.motor_state = "stopped"
        self.motor_speed = 0
        self._motor_forward_start = None

    async def is_bill_at_entry(self) -> bool:
        # If externally set, use that
        if self._bill_at_entry:
            return True
        # Simulate bill appearing after delay
        if self.bill_at_entry_delay > 0:
            await asyncio.sleep(self.bill_at_entry_delay)
            self._bill_at_entry = True
            return True
        return self._bill_at_entry

    async def is_bill_in_position(self) -> bool:
        # If simulating jam, bill never reaches position
        if self.simulate_jam:
            return False
        # If externally set, use that
        if self._bill_in_position:
            return True
        # Simulate bill reaching position after motor runs forward for a delay
        if self.motor_state == "forward" and self._motor_forward_start is not None:
            elapsed = time.monotonic() - self._motor_forward_start
            if elapsed >= self.bill_in_position_delay:
                self._bill_in_position = True
                return True
        return self._bill_in_position

    async def uv_led_on(self) -> None:
        self.call_log.append("uv_led_on")
        self.uv_led_state = True

    async def uv_led_off(self) -> None:
        self.call_log.append("uv_led_off")
        self.uv_led_state = False

    async def white_led_on(self) -> None:
        self.call_log.append("white_led_on")
        self.white_led_state = True

    async def white_led_off(self) -> None:
        self.call_log.append("white_led_off")
        self.white_led_state = False

    # --- Test helpers ---

    def set_bill_at_entry(self, present: bool = True) -> None:
        """Manually set bill presence at entry sensor."""
        self._bill_at_entry = present

    def set_bill_in_position(self, present: bool = True) -> None:
        """Manually set bill presence at camera position."""
        self._bill_in_position = present

    def reset(self) -> None:
        """Reset all state for a fresh test."""
        self.motor_state = "stopped"
        self.motor_speed = 0
        self.uv_led_state = False
        self.white_led_state = False
        self._bill_at_entry = False
        self._bill_in_position = False
        self._motor_forward_start = None
        self.simulate_jam = False
        self.call_log.clear()
