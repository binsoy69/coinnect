import asyncio
import json
import sys
from types import SimpleNamespace

import pytest

from app.core.constants import ControllerType
from app.core.errors import SerialError
from app.drivers.serial_manager import SerialConnection


class ReadySerial:
    def __init__(self, port, baudrate, timeout, controller="COIN_SECURITY"):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        self._lines = [
            (json.dumps({
                "event": "READY",
                "version": "test",
                "controller": controller,
            }) + "\n").encode()
        ]

    @property
    def in_waiting(self):
        return len(self._lines)

    def readline(self):
        return self._lines.pop(0) if self._lines else b""

    def close(self):
        self.is_open = False


@pytest.mark.asyncio
async def test_real_connection_waits_for_matching_ready(monkeypatch):
    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=ReadySerial))
    queue = asyncio.Queue()
    connection = SerialConnection(
        port="/dev/test-coin",
        baud_rate=115200,
        controller_type=ControllerType.COIN_SECURITY,
        event_queue=queue,
        ready_timeout=0.5,
    )

    await connection.connect()

    assert connection.is_connected
    ready = await queue.get()
    assert ready["event"] == "READY"
    assert ready["controller"] == "COIN_SECURITY"
    await connection.disconnect()


@pytest.mark.asyncio
async def test_real_connection_rejects_wrong_controller(monkeypatch):
    def wrong_serial(port, baudrate, timeout):
        return ReadySerial(port, baudrate, timeout, controller="BILL")

    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=wrong_serial))
    connection = SerialConnection(
        port="/dev/test-coin",
        baud_rate=115200,
        controller_type=ControllerType.COIN_SECURITY,
        event_queue=asyncio.Queue(),
        ready_timeout=0.5,
    )

    with pytest.raises(SerialError, match="Controller mismatch"):
        await connection.connect()

