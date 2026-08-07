import asyncio
import json

import pytest

from app.core.constants import ControllerType
from app.core.errors import SerialError
from app.drivers.serial_manager import SerialConnection


class RespondingSerial:
    def __init__(self):
        self.is_open = True
        self.writes: list[bytes] = []
        self._line = bytearray()
        self.connection: SerialConnection | None = None

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        for byte in data:
            if byte == ord("\n"):
                if self._line:
                    command = json.loads(self._line.decode("utf-8"))
                    asyncio.get_running_loop().call_soon(
                        self.connection._resolve_in_loop,
                        {"status": "OK", "id": command["id"]},
                    )
                self._line.clear()
            else:
                self._line.append(byte)
        return len(data)


@pytest.mark.asyncio
async def test_coin_command_is_resynchronized_and_written_in_bounded_chunks():
    connection = SerialConnection(
        port="COIN",
        baud_rate=115200,
        controller_type=ControllerType.COIN_SECURITY,
        event_queue=asyncio.Queue(),
        write_chunk_size=16,
        write_chunk_delay=0,
        resync_delay=0,
    )
    serial = RespondingSerial()
    serial.connection = connection
    connection._serial = serial
    connection._loop = asyncio.get_running_loop()

    operation_id = "550e8400-e29b-41d4-a716-446655440000"
    response = await connection.send_command(
        {
            "cmd": "COIN_DISPENSE",
            "denom": 20,
            "count": 1,
            "operation_id": operation_id,
        }
    )

    assert response["status"] == "OK"
    assert serial.writes[0] == b"\n"
    assert all(len(chunk) <= 16 for chunk in serial.writes[1:])
    payload = b"".join(serial.writes[1:])
    assert payload.endswith(b"\n")
    assert json.loads(payload)["operation_id"] == operation_id


@pytest.mark.asyncio
async def test_unexpected_ready_fails_pending_command_as_controller_reset():
    connection = SerialConnection(
        port="COIN",
        baud_rate=115200,
        controller_type=ControllerType.COIN_SECURITY,
        event_queue=asyncio.Queue(),
    )
    connection._loop = asyncio.get_running_loop()
    connection._ready_received = True
    pending = connection._loop.create_future()
    connection._pending_responses[7] = pending

    connection._push_event(
        {
            "event": "READY",
            "version": "3.0.5-uno",
            "controller": "COIN_SECURITY",
            "reset_cause": 2,
        }
    )
    await asyncio.sleep(0)

    with pytest.raises(SerialError, match="Controller restarted"):
        await pending
    assert connection._pending_responses == {}
