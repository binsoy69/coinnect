"""Typed wrapper around Arduino #2 (Coin & Security Controller) serial commands."""

import logging

from app.core.errors import HardwareError
from app.drivers.serial_manager import SerialManager
from app.models.serial_messages import (
    CoinAcceptorEnableResponse,
    CoinChangeResponse,
    CoinDispenseResponse,
    CoinResetResponse,
    CoinSessionStartResponse,
    CoinSessionStopResponse,
    CoinSessionStatusResponse,
    CoinSorterPositionResponse,
    CoinStatusResponse,
    OperationStatusResponse,
    EmergencyStopResponse,
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

    async def coin_dispense(self, denom: int, count: int, operation_id: str) -> CoinDispenseResponse:
        """Dispense `count` coins of the given denomination (1, 5, 10, 20).
        Duration: ~250ms per coin.
        """
        settings = self._serial._settings
        timeout = count * settings.coin_dispense_timeout_factor + settings.coin_dispense_timeout_base
        raw = await self._serial.send_coin_command(
            {"cmd": "COIN_DISPENSE", "denom": denom, "count": count, "operation_id": operation_id},
            timeout=timeout,
        )
        return self._parse_or_raise(raw, CoinDispenseResponse)

    async def operation_status(self, operation_id: str) -> OperationStatusResponse:
        raw = await self._serial.send_coin_command(
            {"cmd": "DISPENSE_OPERATION_STATUS", "operation_id": operation_id}
        )
        return self._parse_or_raise(raw, OperationStatusResponse)

    async def acknowledge_operation(self, operation_id: str) -> dict:
        raw = await self._serial.send_coin_command(
            {"cmd": "DISPENSE_OPERATION_ACK", "operation_id": operation_id}
        )
        if raw.get("status") == "ERROR":
            err = ErrorResponse(**raw)
            raise HardwareError(code=err.code.value, dispensed=err.dispensed)
        if raw.get("status") != "OK":
            raise HardwareError(code="INVALID_RESPONSE")
        return raw

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

    async def set_coin_acceptor_enabled(
        self, enabled: bool
    ) -> CoinAcceptorEnableResponse:
        """Enable or disable the coin acceptor gate signal on Arduino #2."""
        raw = await self._serial.send_coin_command(
            {"cmd": "COIN_ACCEPTOR_ENABLE", "enabled": enabled}
        )
        return self._parse_or_raise(raw, CoinAcceptorEnableResponse)

    async def coin_status(self) -> CoinStatusResponse:
        """Query acceptor enable state, sorter position, and session total."""
        raw = await self._serial.send_coin_command({"cmd": "COIN_STATUS"})
        return self._parse_or_raise(raw, CoinStatusResponse)

    async def coin_session_start(self, sid: int) -> CoinSessionStartResponse:
        """Start a managed coin intake session with monotonic session id."""
        settings = self._serial._settings
        raw = await self._serial.send_coin_command({
            "cmd": "COIN_SESSION_START", "sid": sid,
            "grace_ms": settings.coin_session_grace_ms,
            "timeout_ms": settings.coin_session_timeout_ms,
            "quiet_ms": settings.coin_session_quiet_ms,
        })
        return self._parse_or_raise(raw, CoinSessionStartResponse)

    async def coin_session_stop(self, sid: int) -> CoinSessionStopResponse:
        """Stop coin intake session, disable acceptor gate, and initiate drain."""
        raw = await self._serial.send_coin_command(
            {"cmd": "COIN_SESSION_STOP", "sid": sid}
        )
        return self._parse_or_raise(raw, CoinSessionStopResponse)

    async def coin_session_ack(self, sid: int) -> None:
        raw = await self._serial.send_coin_command({"cmd": "COIN_SESSION_ACK", "sid": sid})
        self._parse_or_raise(raw, EmergencyStopResponse)

    async def coin_session_status(self) -> CoinSessionStatusResponse:
        """Read four compact Uno responses; only a consistent closed set is final."""
        reports = []
        for denom in (1, 5, 10, 20):
            raw = await self._serial.send_coin_command({"cmd": "COIN_SESSION_STATUS", "denom": denom})
            if raw.get("status") == "ERROR":
                self._parse_or_raise(raw, CoinSessionStatusResponse)
            if "count" in raw:
                if raw.get("denom") != denom:
                    raise ValueError("Coin status denomination mismatch")
                reports.append((denom, raw, raw["count"]))
            else:
                # Mock transport uses the aggregate model internally.
                parsed = self._parse_or_raise(raw, CoinSessionStatusResponse)
                reports.append((denom, raw, getattr(parsed, f"count_{denom}")))
        sid = reports[0][1]["sid"]
        if any(raw["sid"] != sid for _, raw, _ in reports):
            raise ValueError("Coin status session changed during reconciliation")
        states = {raw["session_state"] for _, raw, _ in reports}
        state = "UNCERTAIN" if "UNCERTAIN" in states else "CLOSED" if states == {"CLOSED"} else "CLOSING"
        return CoinSessionStatusResponse(status="OK", sid=sid, session_state=state,
            **{f"count_{denom}": count for denom, _, count in reports})

    async def set_coin_sorter_position(
        self, position: str
    ) -> CoinSorterPositionResponse:
        """Move the coin sorter servo to CENTER, LEFT, or RIGHT."""
        raw = await self._serial.send_coin_command(
            {"cmd": "COIN_SORTER_POSITION", "position": position}
        )
        return self._parse_or_raise(raw, CoinSorterPositionResponse)

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

    async def emergency_stop(self) -> EmergencyStopResponse:
        """Immediately stop coin dispensers and disable acceptor gate."""
        raw = await self._serial.send_coin_command(
            {"cmd": "EMERGENCY_STOP"},
            timeout=5.0,
            priority=True,
        )
        return self._parse_or_raise(raw, EmergencyStopResponse)

    async def ping(self) -> PingResponse:
        raw = await self._serial.send_coin_command({"cmd": "PING"})
        return self._parse_or_raise(raw, PingResponse)

    async def version(self) -> VersionResponse:
        raw = await self._serial.send_coin_command({"cmd": "VERSION"})
        return self._parse_or_raise(raw, VersionResponse)

    async def verify_converter_protocol(self) -> None:
        response = await self._serial.send_coin_command({"cmd": "CAPABILITIES"})
        if response.get("status") != "OK" or response.get("converter_protocol") != 2:
            raise ValueError("Expected converter protocol 2")

    async def clear_emergency(self) -> None:
        raw = await self._serial.send_coin_command({"cmd": "EMERGENCY_CLEAR"})
        self._parse_or_raise(raw, EmergencyStopResponse)

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
