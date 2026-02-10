"""Typed wrapper around Arduino #2 (Coin & Security Controller) serial commands."""

import logging

from app.core.errors import HardwareError
from app.drivers.serial_manager import SerialManager
from app.models.serial_messages import (
    CoinChangeResponse,
    CoinDispenseResponse,
    CoinResetResponse,
    ErrorResponse,
    PingResponse,
    SecurityLockResponse,
    SecurityStatusResponse,
    SecurityUnlockResponse,
    VersionResponse,
)

logger = logging.getLogger(__name__)


class CoinSecurityController:
    def __init__(self, serial_manager: SerialManager):
        self._serial = serial_manager

    async def coin_dispense(self, denom: int, count: int) -> CoinDispenseResponse:
        """Dispense `count` coins of the given denomination (1, 5, 10, 20).
        Duration: ~250ms per coin.
        """
        raw = await self._serial.send_coin_command(
            {"cmd": "COIN_DISPENSE", "denom": denom, "count": count},
            timeout=count * 0.5 + 3.0,
        )
        return self._parse_or_raise(raw, CoinDispenseResponse)

    async def coin_change(self, amount: int) -> CoinChangeResponse:
        """Compute and dispense optimal change for the given amount.
        Uses greedy algorithm: 20, 10, 5, 1 peso coins.
        """
        raw = await self._serial.send_coin_command(
            {"cmd": "COIN_CHANGE", "amount": amount},
            timeout=10.0,
        )
        return self._parse_or_raise(raw, CoinChangeResponse)

    async def coin_reset(self) -> CoinResetResponse:
        """Reset the coin accumulator to zero. Returns previous total."""
        raw = await self._serial.send_coin_command({"cmd": "COIN_RESET"})
        return self._parse_or_raise(raw, CoinResetResponse)

    async def security_lock(self) -> SecurityLockResponse:
        """Engage the solenoid door lock."""
        raw = await self._serial.send_coin_command({"cmd": "SECURITY_LOCK"})
        return self._parse_or_raise(raw, SecurityLockResponse)

    async def security_unlock(self) -> SecurityUnlockResponse:
        """Disengage the solenoid door lock (requires RPi authorization)."""
        raw = await self._serial.send_coin_command({"cmd": "SECURITY_UNLOCK"})
        return self._parse_or_raise(raw, SecurityUnlockResponse)

    async def security_status(self) -> SecurityStatusResponse:
        """Query current lock state and tamper sensor status."""
        raw = await self._serial.send_coin_command({"cmd": "SECURITY_STATUS"})
        return self._parse_or_raise(raw, SecurityStatusResponse)

    async def ping(self) -> PingResponse:
        raw = await self._serial.send_coin_command({"cmd": "PING"})
        return self._parse_or_raise(raw, PingResponse)

    async def version(self) -> VersionResponse:
        raw = await self._serial.send_coin_command({"cmd": "VERSION"})
        return self._parse_or_raise(raw, VersionResponse)

    async def reset(self) -> None:
        await self._serial.send_coin_command({"cmd": "RESET"})

    @staticmethod
    def _parse_or_raise(raw: dict, success_model):
        if raw.get("status") == "ERROR":
            err = ErrorResponse(**raw)
            raise HardwareError(
                code=err.code.value,
                dispensed=err.dispensed,
            )
        return success_model(**raw)
