"""GPIO controller for bill acceptor hardware.

Controls the bill conveyor motor (L298N driver), entry IR sensor,
and LED lighting on the Raspberry Pi.
"""

import asyncio
import logging
from abc import ABC, abstractmethod

from typing import Optional
from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class GPIOControllerBase(ABC):
    """Abstract base for GPIO pin control."""

    @abstractmethod
    async def setup(self) -> None:
        """Initialize GPIO pins."""

    @abstractmethod
    async def cleanup(self) -> None:
        """Release GPIO resources."""

    @abstractmethod
    async def motor_forward(self, speed: int = 60) -> None:
        """Run conveyor motor forward at given speed (0-100 PWM duty cycle)."""

    @abstractmethod
    async def motor_reverse(self, speed: int = 80) -> None:
        """Run conveyor motor in reverse at given speed."""

    @abstractmethod
    async def motor_stop(self) -> None:
        """Stop conveyor motor."""

    @abstractmethod
    async def motor_brake(self) -> None:
        """Active brake conveyor motor."""

    @abstractmethod
    async def is_bill_at_entry(self) -> bool:
        """Check if bill is detected at entry IR sensor (GPIO5)."""

    @abstractmethod
    async def is_bill_at_position(self) -> bool:
        """Check if bill is detected at position IR sensor (GPIO6)."""

    @abstractmethod
    async def uv_led_on(self) -> None:
        """Turn on UV LED strip via relay (GPIO23)."""

    @abstractmethod
    async def uv_led_off(self) -> None:
        """Turn off UV LED strip."""

    @abstractmethod
    async def white_led_on(self, brightness: int = 100) -> None:
        """Turn on white LED via MOSFET (GPIO24) with configurable brightness (0-100)."""

    @abstractmethod
    async def white_led_off(self) -> None:
        """Turn off white LED."""


class RPiGPIOController(GPIOControllerBase):
    """Real Raspberry Pi GPIO implementation.
    
    Pin assignments (from reference/02_bill_acceptor_system.md):
      GPIO17 -> L298N IN1 (motor direction 1)
      GPIO27 -> L298N IN2 (motor direction 2)
      GPIO22 -> L298N ENA (PWM enable)
      GPIO5  -> IR sensor (bill entry) - LOW = detected
      GPIO23 -> UV LED relay - HIGH = on
      GPIO24 -> White LED MOSFET - HIGH = on
    """

    # Pin constants
    MOTOR_IN1 = 17
    MOTOR_IN2 = 27
    MOTOR_ENA = 22
    IR_ENTRY = 5
    IR_POSITION = 6
    UV_LED = 23
    WHITE_LED = 24
    PWM_FREQUENCY = 1000  # 1kHz PWM

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._gpio = None
        self._pwm = None
        self._white_led_pwm = None
        self._loop = None

    async def setup(self) -> None:
        self._loop = asyncio.get_event_loop()
        await self._loop.run_in_executor(None, self._setup_pins)

    def _setup_pins(self) -> None:
        try:
            import RPi.GPIO as GPIO
        except ModuleNotFoundError as exc:
            if not (exc.name and exc.name.startswith("RPi")):
                raise
            raise RuntimeError(
                "RPi.GPIO is required when USE_MOCK_HARDWARE=false. "
                "On the Raspberry Pi, activate backend/venv and run "
                "`pip install -r requirements.txt` to install rpi-lgpio, "
                "or set USE_MOCK_HARDWARE=true for mock hardware startup."
            ) from exc

        self._gpio = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Motor control outputs
        GPIO.setup(self.MOTOR_IN1, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.MOTOR_IN2, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.MOTOR_ENA, GPIO.OUT, initial=GPIO.LOW)
        self._pwm = GPIO.PWM(self.MOTOR_ENA, self.PWM_FREQUENCY)
        self._pwm.start(0)

        # Entry IR sensor input
        pud_entry = (
            GPIO.PUD_UP if self._settings.ir_entry_active_low else GPIO.PUD_DOWN
        )
        GPIO.setup(self.IR_ENTRY, GPIO.IN, pull_up_down=pud_entry)

        # Position IR sensor input
        pud_position = (
            GPIO.PUD_UP if self._settings.ir_position_active_low else GPIO.PUD_DOWN
        )
        GPIO.setup(self.IR_POSITION, GPIO.IN, pull_up_down=pud_position)

        # LED outputs
        GPIO.setup(self.UV_LED, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.WHITE_LED, GPIO.OUT, initial=GPIO.LOW)
        self._white_led_pwm = GPIO.PWM(self.WHITE_LED, self.PWM_FREQUENCY)
        self._white_led_pwm.start(0)

        logger.info("RPi GPIO initialized")

    async def cleanup(self) -> None:
        if self._pwm:
            await self._loop.run_in_executor(None, self._pwm.stop)
        if self._white_led_pwm:
            await self._loop.run_in_executor(None, self._white_led_pwm.stop)
        if self._gpio:
            await self._loop.run_in_executor(None, self._gpio.cleanup)
        logger.info("RPi GPIO cleaned up")

    async def motor_forward(self, speed: int = 60) -> None:
        def _forward():
            self._gpio.output(self.MOTOR_IN1, self._gpio.HIGH)
            self._gpio.output(self.MOTOR_IN2, self._gpio.LOW)
            self._pwm.ChangeDutyCycle(speed)
        await self._loop.run_in_executor(None, _forward)

    async def motor_reverse(self, speed: int = 80) -> None:
        def _reverse():
            self._gpio.output(self.MOTOR_IN1, self._gpio.LOW)
            self._gpio.output(self.MOTOR_IN2, self._gpio.HIGH)
            self._pwm.ChangeDutyCycle(speed)
        await self._loop.run_in_executor(None, _reverse)

    async def motor_stop(self) -> None:
        def _stop():
            self._gpio.output(self.MOTOR_IN1, self._gpio.LOW)
            self._gpio.output(self.MOTOR_IN2, self._gpio.LOW)
            self._pwm.ChangeDutyCycle(0)
        await self._loop.run_in_executor(None, _stop)

    async def motor_brake(self) -> None:
        def _brake():
            self._gpio.output(self.MOTOR_IN1, self._gpio.HIGH)
            self._gpio.output(self.MOTOR_IN2, self._gpio.HIGH)
            self._pwm.ChangeDutyCycle(100)
        await self._loop.run_in_executor(None, _brake)

    async def is_bill_at_entry(self) -> bool:
        result = await self._loop.run_in_executor(
            None, self._gpio.input, self.IR_ENTRY
        )
        expected = (
            self._gpio.LOW if self._settings.ir_entry_active_low else self._gpio.HIGH
        )
        return result == expected

    async def is_bill_at_position(self) -> bool:
        result = await self._loop.run_in_executor(
            None, self._gpio.input, self.IR_POSITION
        )
        expected = (
            self._gpio.LOW
            if self._settings.ir_position_active_low
            else self._gpio.HIGH
        )
        return result == expected

    async def uv_led_on(self) -> None:
        await self._loop.run_in_executor(
            None, self._gpio.output, self.UV_LED, self._gpio.HIGH
        )

    async def uv_led_off(self) -> None:
        await self._loop.run_in_executor(
            None, self._gpio.output, self.UV_LED, self._gpio.LOW
        )

    async def white_led_on(self, brightness: int = 100) -> None:
        def _on():
            self._white_led_pwm.ChangeDutyCycle(brightness)
        await self._loop.run_in_executor(None, _on)

    async def white_led_off(self) -> None:
        def _off():
            self._white_led_pwm.ChangeDutyCycle(0)
        await self._loop.run_in_executor(None, _off)
