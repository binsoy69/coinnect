"""Mock serial port for development and testing without hardware.

Drop-in replacement for pyserial.Serial. Two modes:
- Simple (mock_delay=0): instant canned responses, no state tracking.
- Realistic (mock_delay>0): simulates timing, internal state, and faults.
"""

import json
import threading
import time
from io import BytesIO
from typing import Dict, List, Optional

from app.core.constants import (
    DENOM_TO_SLOT,
    SLOT_POSITIONS,
    BillDenom,
    CoinDenom,
    ControllerType,
)


class MockSerial:
    def __init__(
        self,
        port: str = "",
        baudrate: int = 115200,
        timeout: Optional[float] = None,
        mock_delay: float = 0.0,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.mock_delay = mock_delay
        self.is_open = True

        self._read_buffer = BytesIO()
        self._lock = threading.Lock()

        # Determine controller identity from port name
        port_lower = port.lower()
        if "bill" in port_lower or "usb" in port_lower:
            self._controller = ControllerType.BILL
        else:
            self._controller = ControllerType.COIN_SECURITY

        # Realistic mode internal state
        self._homed = False
        self._current_position = 0
        self._current_slot = 0
        self._locked = True
        self._coin_total = 0
        self._tamper_active = False

        # Fault injection
        self._fault_next: Optional[str] = None
        self._pending_events: List[dict] = []

    @property
    def in_waiting(self) -> int:
        with self._lock:
            pos = self._read_buffer.tell()
            self._read_buffer.seek(0, 2)
            end = self._read_buffer.tell()
            self._read_buffer.seek(pos)
            return end - pos

    def write(self, data: bytes) -> int:
        with self._lock:
            try:
                line = data.decode("utf-8").strip()
                cmd_json = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._buffer_response({"status": "ERROR", "code": "PARSE_ERROR"})
                return len(data)

            responses = self._dispatch_command(cmd_json)
            for resp in responses:
                self._buffer_response(resp)

            return len(data)

    def readline(self) -> bytes:
        # Block until a line is available or timeout
        deadline = time.monotonic() + (self.timeout or 5.0)
        while time.monotonic() < deadline:
            with self._lock:
                line = self._read_buffer.readline()
                if line and line.endswith(b"\n"):
                    # Compact buffer: move remaining data to start
                    remaining = self._read_buffer.read()
                    self._read_buffer = BytesIO(remaining)
                    return line
                # Reset position if we didn't get a full line
                self._read_buffer.seek(0)
            time.sleep(0.01)
        return b""

    def read(self, size: int = 1) -> bytes:
        with self._lock:
            return self._read_buffer.read(size)

    def close(self) -> None:
        self.is_open = False

    def reset_input_buffer(self) -> None:
        with self._lock:
            self._read_buffer = BytesIO()

    # --- Fault injection API ---

    def inject_fault(self, error_code: str) -> None:
        """Next command will return this error instead of success."""
        self._fault_next = error_code

    def inject_event(self, event: dict) -> None:
        """Queue an unsolicited event to be read."""
        with self._lock:
            self._buffer_response(event)

    def set_state(self, **kwargs) -> None:
        """Override internal state for testing."""
        for key, value in kwargs.items():
            attr = f"_{key}"
            if hasattr(self, attr):
                setattr(self, attr, value)

    # --- Internal dispatch ---

    def _buffer_response(self, data: dict) -> None:
        """Add a JSON response line to the read buffer."""
        line = json.dumps(data) + "\n"
        current_pos = self._read_buffer.tell()
        self._read_buffer.seek(0, 2)  # seek to end
        self._read_buffer.write(line.encode("utf-8"))
        self._read_buffer.seek(current_pos)

    def _dispatch_command(self, cmd_json: dict) -> List[dict]:
        # Check for injected fault
        if self._fault_next:
            code = self._fault_next
            self._fault_next = None
            return [{"status": "ERROR", "code": code}]

        cmd = cmd_json.get("cmd", "")

        # Simulate delay in realistic mode
        if self.mock_delay > 0:
            self._apply_delay(cmd, cmd_json)

        handlers = {
            "SORT": self._handle_sort,
            "HOME": self._handle_home,
            "SORT_STATUS": self._handle_sort_status,
            "DISPENSE": self._handle_dispense,
            "DISPENSE_STATUS": self._handle_dispense_status,
            "COIN_DISPENSE": self._handle_coin_dispense,
            "COIN_CHANGE": self._handle_coin_change,
            "COIN_RESET": self._handle_coin_reset,
            "SECURITY_LOCK": self._handle_security_lock,
            "SECURITY_UNLOCK": self._handle_security_unlock,
            "SECURITY_STATUS": self._handle_security_status,
            "PING": self._handle_ping,
            "VERSION": self._handle_version,
            "RESET": self._handle_reset,
        }

        handler = handlers.get(cmd)
        if handler is None:
            return [{"status": "ERROR", "code": "UNKNOWN_CMD"}]

        return handler(cmd_json)

    def _apply_delay(self, cmd: str, cmd_json: dict) -> None:
        """Apply realistic timing delays based on command type."""
        delays = {
            "SORT": self.mock_delay * 1.5,
            "HOME": self.mock_delay * 3.0,
            "DISPENSE": self.mock_delay * 0.7 * cmd_json.get("count", 1),
            "COIN_DISPENSE": self.mock_delay * 0.25 * cmd_json.get("count", 1),
            "COIN_CHANGE": self.mock_delay * 1.0,
        }
        delay = delays.get(cmd, self.mock_delay * 0.1)
        time.sleep(delay)

    # --- Bill Controller handlers (Arduino #1) ---

    def _handle_sort(self, cmd: dict) -> List[dict]:
        denom_str = cmd.get("denom", "")
        try:
            denom = BillDenom(denom_str)
        except ValueError:
            return [{"status": "ERROR", "code": "INVALID_DENOM"}]

        if self.mock_delay > 0 and not self._homed:
            return [{"status": "ERROR", "code": "NOT_HOMED"}]

        slot = DENOM_TO_SLOT[denom]
        self._current_slot = slot.value
        self._current_position = SLOT_POSITIONS[slot]
        return [{"status": "READY", "slot": slot.value}]

    def _handle_home(self, cmd: dict) -> List[dict]:
        self._homed = True
        self._current_position = 0
        self._current_slot = 0
        return [{"status": "OK", "position": 0}]

    def _handle_sort_status(self, cmd: dict) -> List[dict]:
        return [{
            "status": "OK",
            "position": self._current_position,
            "slot": self._current_slot,
            "homed": self._homed,
        }]

    def _handle_dispense(self, cmd: dict) -> List[dict]:
        denom_str = cmd.get("denom", "")
        count = cmd.get("count", 0)

        try:
            BillDenom(denom_str)
        except ValueError:
            return [{"status": "ERROR", "code": "INVALID_DENOM"}]

        if not isinstance(count, int) or count < 1 or count > 20:
            return [{"status": "ERROR", "code": "INVALID_COUNT"}]

        return [{"status": "OK", "dispensed": count}]

    def _handle_dispense_status(self, cmd: dict) -> List[dict]:
        denom_str = cmd.get("denom", "")
        try:
            BillDenom(denom_str)
        except ValueError:
            return [{"status": "ERROR", "code": "INVALID_DENOM"}]
        return [{"status": "OK", "ready": True}]

    # --- Coin & Security handlers (Arduino #2) ---

    def _handle_coin_dispense(self, cmd: dict) -> List[dict]:
        denom = cmd.get("denom", 0)
        count = cmd.get("count", 0)

        valid_denoms = {d.value for d in CoinDenom}
        if denom not in valid_denoms:
            return [{"status": "ERROR", "code": "INVALID_DENOM"}]
        if not isinstance(count, int) or count < 1 or count > 50:
            return [{"status": "ERROR", "code": "INVALID_COUNT"}]

        return [{"status": "OK", "dispensed": count}]

    def _handle_coin_change(self, cmd: dict) -> List[dict]:
        amount = cmd.get("amount", 0)
        if not isinstance(amount, int) or amount < 1:
            return [{"status": "ERROR", "code": "INVALID_COUNT"}]

        # Greedy coin breakdown
        remaining = amount
        breakdown: Dict[str, int] = {}
        for coin in [20, 10, 5, 1]:
            if remaining >= coin:
                count = remaining // coin
                breakdown[str(coin)] = count
                remaining -= coin * count

        return [{"status": "OK", "breakdown": breakdown}]

    def _handle_coin_reset(self, cmd: dict) -> List[dict]:
        prev = self._coin_total
        self._coin_total = 0
        return [{"status": "OK", "previous_total": prev}]

    def _handle_security_lock(self, cmd: dict) -> List[dict]:
        self._locked = True
        return [{"status": "OK", "locked": True}]

    def _handle_security_unlock(self, cmd: dict) -> List[dict]:
        self._locked = False
        return [{"status": "OK", "locked": False}]

    def _handle_security_status(self, cmd: dict) -> List[dict]:
        return [{
            "status": "OK",
            "locked": self._locked,
            "tamper_a": self._tamper_active,
        }]

    # --- System handlers ---

    def _handle_ping(self, cmd: dict) -> List[dict]:
        return [{"status": "OK", "message": "PONG"}]

    def _handle_version(self, cmd: dict) -> List[dict]:
        return [{
            "status": "OK",
            "version": "2.0.0",
            "controller": self._controller.value,
        }]

    def _handle_reset(self, cmd: dict) -> List[dict]:
        self._homed = False
        self._current_position = 0
        self._current_slot = 0
        self._coin_total = 0
        self._tamper_active = False
        return [{"status": "OK"}]
