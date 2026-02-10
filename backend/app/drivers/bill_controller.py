"""Typed wrapper around Arduino #1 (Bill Controller) serial commands."""

import logging

from app.core.constants import BillDenom
from app.core.errors import HardwareError
from app.drivers.serial_manager import SerialManager
from app.models.serial_messages import (
    DispenseResponse,
    DispenseStatusResponse,
    ErrorResponse,
    HomeResponse,
    PingResponse,
    SortResponse,
    SortStatusResponse,
    VersionResponse,
)

logger = logging.getLogger(__name__)


class BillController:
    def __init__(self, serial_manager: SerialManager):
        self._serial = serial_manager

    async def sort(self, denom: BillDenom) -> SortResponse:
        """Move sorting rail to the slot for the given denomination.
        Typical: 0.7-5.5s depending on travel distance.
        """
        raw = await self._serial.send_bill_command(
            {"cmd": "SORT", "denom": denom.value},
            timeout=8.0,
        )
        return self._parse_or_raise(raw, SortResponse)

    async def home(self) -> HomeResponse:
        """Home the sorting rail to position 0. Duration: 5-10s."""
        raw = await self._serial.send_bill_command(
            {"cmd": "HOME"},
            timeout=12.0,
        )
        return self._parse_or_raise(raw, HomeResponse)

    async def sort_status(self) -> SortStatusResponse:
        """Query current sorter position, slot, and homed state."""
        raw = await self._serial.send_bill_command({"cmd": "SORT_STATUS"})
        return self._parse_or_raise(raw, SortStatusResponse)

    async def dispense(self, denom: BillDenom, count: int) -> DispenseResponse:
        """Dispense `count` bills of the given denomination.
        Duration: ~600-700ms per bill.
        """
        raw = await self._serial.send_bill_command(
            {"cmd": "DISPENSE", "denom": denom.value, "count": count},
            timeout=count * 2.0 + 5.0,
        )
        return self._parse_or_raise(raw, DispenseResponse)

    async def dispense_status(self, denom: BillDenom) -> DispenseStatusResponse:
        """Check if the dispenser for a denomination is ready."""
        raw = await self._serial.send_bill_command(
            {"cmd": "DISPENSE_STATUS", "denom": denom.value},
        )
        return self._parse_or_raise(raw, DispenseStatusResponse)

    async def ping(self) -> PingResponse:
        raw = await self._serial.send_bill_command({"cmd": "PING"})
        return self._parse_or_raise(raw, PingResponse)

    async def version(self) -> VersionResponse:
        raw = await self._serial.send_bill_command({"cmd": "VERSION"})
        return self._parse_or_raise(raw, VersionResponse)

    async def reset(self) -> None:
        await self._serial.send_bill_command({"cmd": "RESET"})

    @staticmethod
    def _parse_or_raise(raw: dict, success_model):
        if raw.get("status") == "ERROR":
            err = ErrorResponse(**raw)
            raise HardwareError(
                code=err.code.value,
                dispensed=err.dispensed,
            )
        return success_model(**raw)
