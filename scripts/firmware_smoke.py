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
        self._next_command_id = 1
        # Opening USB serial resets most Arduino boards. Let boot messages arrive.
        time.sleep(self.settle)
        self._drain_boot_lines()

    def close(self) -> None:
        self.serial.close()

    def _read_json_line(self) -> dict[str, Any] | None:
        raw = self.serial.readline()
        if not raw:
            return None
        try:
            text = raw.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise RuntimeError(
                f"{self.name}: invalid UTF-8 from controller: {raw.hex()}"
            ) from exc
        if not text:
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{self.name}: invalid JSON from controller: "
                f"text={text!r} raw={raw.hex()}"
            ) from exc
        if not isinstance(data, dict):
            raise RuntimeError(
                f"{self.name}: controller returned non-object JSON: {data!r}"
            )
        return data

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
        request = dict(payload)
        command_id = self._next_command_id
        self._next_command_id += 1
        request["id"] = command_id
        line = json.dumps(request, separators=(",", ":")) + "\n"
        print(f"[{self.name}] tx: {line.strip()}")
        encoded = line.encode("utf-8")
        if self.name == "coin":
            # Match the backend's Uno-safe transport: terminate any stale
            # fragment, then keep the 64-byte UART ring below capacity while
            # MFRC522 polling may briefly block the firmware loop.
            self.serial.write(b"\n")
            self.serial.flush()
            time.sleep(0.05)
            for offset in range(0, len(encoded), 16):
                self.serial.write(encoded[offset:offset + 16])
                self.serial.flush()
                if offset + 16 < len(encoded):
                    time.sleep(0.02)
        else:
            self.serial.write(encoded)
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
            if data.get("id") != command_id:
                raise RuntimeError(
                    f"{self.name}: response ID mismatch: expected {command_id}, "
                    f"got {data.get('id')!r}: {data}"
                )
            expected_operation_id = request.get("operation_id")
            if (
                expected_operation_id is not None
                and data.get("operation_id") != expected_operation_id
            ):
                raise RuntimeError(
                    f"{self.name}: operation ID mismatch: expected "
                    f"{expected_operation_id}, got {data.get('operation_id')!r}: {data}"
                )
            return data

        raise TimeoutError(f"{self.name}: no response for {payload['cmd']}")


def require_ok(response: dict[str, Any], command: str) -> None:
    status = response.get("status")
    if status not in {"OK", "READY"}:
        raise RuntimeError(f"{command} failed: {response}")


def require_error(response: dict[str, Any], command: str, code: str) -> None:
    if response.get("status") != "ERROR" or response.get("code") != code:
        raise RuntimeError(f"{command} expected ERROR/{code}: {response}")


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
        ]:
            require_ok(probe.command(payload), payload["cmd"])

        for iteration in range(1, args.iterations + 1):
            capabilities = probe.command({"cmd": "CAPABILITIES"})
            require_ok(capabilities, "CAPABILITIES")
            if capabilities.get("converter_protocol") != 2:
                raise RuntimeError(f"Expected converter protocol 2: {capabilities}")

            operation_id = str(uuid.uuid4())
            status = probe.command(
                {"cmd": "DISPENSE_OPERATION_STATUS", "operation_id": operation_id}
            )
            require_ok(status, "DISPENSE_OPERATION_STATUS")
            if status.get("operation_status") != "NOT_FOUND":
                raise RuntimeError(
                    "Safe recovery probe found controller state requiring "
                    f"reconciliation on iteration {iteration}: {status}"
                )

            acknowledgement = probe.command(
                {"cmd": "DISPENSE_OPERATION_ACK", "operation_id": operation_id}
            )
            require_error(acknowledgement, "DISPENSE_OPERATION_ACK", "NOT_FOUND")

            # Check a short reply after UUID recovery replies: stack corruption
            # can damage later responses even when the long reply succeeded.
            pong = probe.command({"cmd": "PING"})
            require_ok(pong, "PING")
            if pong.get("message") != "PONG":
                raise RuntimeError(f"Expected intact PONG on iteration {iteration}: {pong}")

            disabled = probe.command(
                {"cmd": "COIN_ACCEPTOR_ENABLE", "enabled": False}
            )
            require_ok(disabled, "COIN_ACCEPTOR_ENABLE")
            if disabled.get("enabled") is not False:
                raise RuntimeError(
                    f"Coin acceptor did not report disabled: {disabled}"
                )

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
    parser.add_argument(
        "--iterations",
        type=int,
        default=25,
        help="number of repeated safe coin-controller recovery probes",
    )
    parser.add_argument("--actuate", action="store_true")
    parser.add_argument("--skip-bill", action="store_true")
    parser.add_argument("--skip-coin", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.iterations < 1:
        raise SystemExit("--iterations must be at least 1")
    if not args.skip_bill:
        check_bill(args)
    if not args.skip_coin:
        check_coin(args)
    print("Firmware smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
