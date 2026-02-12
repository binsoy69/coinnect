"""GPIO controller for bill acceptor hardware.

Controls the bill conveyor motor (L298N driver), IR sensors,
and LED lighting on the Raspberry Pi.
"""

import asyncio
import logging
from abc import ABC, abstractmethod

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
    async def is_bill_at_entry(self) -> bool:
        """Check if bill is detected at entry IR sensor (GPIO5)."""

    @abstractmethod
    async def is_bill_in_position(self) -> bool:
        """Check if bill is at camera position IR sensor (GPIO6)."""

    @abstractmethod
    async def uv_led_on(self) -> None:
        """Turn on UV LED strip via relay (GPIO23)."""

    @abstractmethod
    async def uv_led_off(self) -> None:
        """Turn off UV LED strip."""

    @abstractmethod
    async def white_led_on(self) -> None:
        """Turn on white LED via MOSFET (GPIO24)."""

    @abstractmethod
    async def white_led_off(self) -> None:
        """Turn off white LED."""


class RPiGPIOController(GPIOControllerBase):
    """Real Raspberry Pi GPIO implementation.
    
    Pin assignments (from reference/02_bill_acceptor_system.md):
      GPIO17 -> L298N IN1 (motor direction 1)
      GPIO27 -> L298N IN2 (motor direction 2)
      GPIO22 -> L298N ENA (PWM enable)
      GPIO5  -> IR sensor 1 (bill entry) - LOW = detected
      GPIO6  -> IR sensor 2 (bill position) - LOW = detected
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

    def __init__(self):
        self._gpio = None
        self._pwm = None
        self._loop = None

    async def setup(self) -> None:
        self._loop = asyncio.get_event_loop()
        await self._loop.run_in_executor(None, self._setup_pins)

    def _setup_pins(self) -> None:
        import RPi.GPIO as GPIO
        self._gpio = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Motor control outputs
        GPIO.setup(self.MOTOR_IN1, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.MOTOR_IN2, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.MOTOR_ENA, GPIO.OUT, initial=GPIO.LOW)
        self._pwm = GPIO.PWM(self.MOTOR_ENA, self.PWM_FREQUENCY)
        self._pwm.start(0)

        # IR sensor inputs (with pull-up; LOW = detected)
        GPIO.setup(self.IR_ENTRY, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.IR_POSITION, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # LED outputs
        GPIO.setup(self.UV_LED, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.WHITE_LED, GPIO.OUT, initial=GPIO.LOW)

        logger.info("RPi GPIO initialized")

    async def cleanup(self) -> None:
        if self._pwm:
            await self._loop.run_in_executor(None, self._pwm.stop)
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

    async def is_bill_at_entry(self) -> bool:
        result = await self._loop.run_in_executor(
            None, self._gpio.input, self.IR_ENTRY
        )
        return result == self._gpio.LOW  # LOW = detected

    async def is_bill_in_position(self) -> bool:
        result = await self._loop.run_in_executor(
            None, self._gpio.input, self.IR_POSITION
        )
        return result == self._gpio.LOW  # LOW = detected

    async def uv_led_on(self) -> None:
        await self._loop.run_in_executor(
            None, self._gpio.output, self.UV_LED, self._gpio.HIGH
        )

    async def uv_led_off(self) -> None:
        await self._loop.run_in_executor(
            None, self._gpio.output, self.UV_LED, self._gpio.LOW
        )

    async def white_led_on(self) -> None:
        await self._loop.run_in_executor(
            None, self._gpio.output, self.WHITE_LED, self._gpio.HIGH
        )

    async def white_led_off(self) -> None:
        await self._loop.run_in_executor(
            None, self._gpio.output, self.WHITE_LED, self._gpio.LOW
        )
