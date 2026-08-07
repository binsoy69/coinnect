#!/usr/bin/env python3
"""Serial smoke checks for Coinnect Arduino firmware.

Default checks are non-actuating protocol probes. Pass --actuate only after
bare-board, wiring, and one-actuator-at-a-time checks are safe.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

try:
    import serial
except ImportError:  # pragma: no cover - host environment helper
    print("pyserial is required. Install with: pip install pyserial", file=sys.stderr)
    raise


@dataclass
class FirmwarePort:
    name: str
    port: str
    baud: int
    timeout: float
    settle: float

    def __post_init__(self) -> None:
        self.serial = serial.Serial(self.port, self.baud, timeout=self.timeout)
        # Opening USB serial resets most Arduino boards. Let boot messages arrive.
        time.sleep(self.settle)
        self._drain_boot_lines()

    def close(self) -> None:
        self.serial.close()

    def _read_json_line(self) -> dict[str, Any] | None:
        raw = self.serial.readline()
        if not raw:
            return None
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"[{self.name}] non-json: {text}")
            return None

    def _drain_boot_lines(self) -> None:
        previous_timeout = self.serial.timeout
        self.serial.timeout = 0.1
        deadline = time.monotonic() + 0.75
        try:
            while time.monotonic() < deadline:
                data = self._read_json_line()
                if data is None:
                    continue
                print(f"[{self.name}] boot: {json.dumps(data, sort_keys=True)}")
        finally:
            self.serial.timeout = previous_timeout

    def command(self, payload: dict[str, Any]) -> dict[str, Any]:
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        print(f"[{self.name}] tx: {line.strip()}")
        self.serial.write(line.encode("utf-8"))
        self.serial.flush()

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            data = self._read_json_line()
            if data is None:
                continue
            if "event" in data:
                print(f"[{self.name}] event: {json.dumps(data, sort_keys=True)}")
                continue
            print(f"[{self.name}] rx: {json.dumps(data, sort_keys=True)}")
            if "status" not in data:
                raise RuntimeError(f"{self.name}: response missing status: {data}")
            return data

        raise TimeoutError(f"{self.name}: no response for {payload['cmd']}")


def require_ok(response: dict[str, Any], command: str) -> None:
    status = response.get("status")
    if status not in {"OK", "READY"}:
        raise RuntimeError(f"{command} failed: {response}")


def check_bill(args: argparse.Namespace) -> None:
    probe = FirmwarePort("bill", args.bill_port, args.baud, args.timeout, args.settle)
    try:
        for payload in [
            {"cmd": "PING"},
            {"cmd": "VERSION"},
            {"cmd": "SORT_STATUS"},
            {"cmd": "DISPENSE_STATUS", "denom": "PHP_20"},
        ]:
            require_ok(probe.command(payload), payload["cmd"])

        if args.actuate:
            operation_id = str(uuid.uuid4())
            for payload in [
                {"cmd": "HOME"},
                {"cmd": "SORT", "denom": "PHP_20"},
                {"cmd": "DISPENSE", "denom": "PHP_20", "count": 1, "operation_id": operation_id},
                {"cmd": "DISPENSE_OPERATION_STATUS", "operation_id": operation_id},
                {"cmd": "DISPENSE", "denom": "PHP_20", "count": 1, "operation_id": operation_id},
            ]:
                require_ok(probe.command(payload), payload["cmd"])
    finally:
        probe.close()


def check_coin(args: argparse.Namespace) -> None:
    probe = FirmwarePort("coin", args.coin_port, args.baud, args.timeout, args.settle)
    try:
        for payload in [
            {"cmd": "PING"},
            {"cmd": "VERSION"},
            {"cmd": "SECURITY_STATUS"},
            {"cmd": "COIN_STATUS"},
            {"cmd": "COIN_RESET"},
        ]:
            require_ok(probe.command(payload), payload["cmd"])

        if args.actuate:
            operation_id = str(uuid.uuid4())
            for payload in [
                {"cmd": "COIN_ACCEPTOR_ENABLE", "enabled": True},
                {"cmd": "COIN_ACCEPTOR_ENABLE", "enabled": False},
                {"cmd": "COIN_SORTER_POSITION", "position": "LEFT"},
                {"cmd": "COIN_SORTER_POSITION", "position": "RIGHT"},
                {"cmd": "COIN_SORTER_POSITION", "position": "CENTER"},
                {"cmd": "COIN_DISPENSE", "denom": 1, "count": 1, "operation_id": operation_id},
                {"cmd": "DISPENSE_OPERATION_STATUS", "operation_id": operation_id},
                {"cmd": "COIN_DISPENSE", "denom": 1, "count": 1, "operation_id": operation_id},
                {"cmd": "SECURITY_LOCK"},
                {"cmd": "SECURITY_UNLOCK"},
                {"cmd": "SECURITY_LOCK"},
            ]:
                require_ok(probe.command(payload), payload["cmd"])
    finally:
        probe.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bill-port", default="/dev/ttyUSB0")
    parser.add_argument("--coin-port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--settle", type=float, default=2.0)
    parser.add_argument("--actuate", action="store_true")
    parser.add_argument("--skip-bill", action="store_true")
    parser.add_argument("--skip-coin", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.skip_bill:
        check_bill(args)
    if not args.skip_coin:
        check_coin(args)
    print("Firmware smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
