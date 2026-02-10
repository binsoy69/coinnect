import asyncio

import pytest
from unittest.mock import AsyncMock

from app.core.config import Settings
from app.models.events import WSEventType
from app.services.event_dispatcher import EventDispatcher
from app.services.machine_status import MachineStatus


@pytest.fixture
def settings():
    return Settings(
        use_mock_serial=True,
        serial_port_bill="MOCK",
        serial_port_coin="MOCK",
    )


@pytest.fixture
def machine_status(settings):
    return MachineStatus(settings)


@pytest.fixture
def ws_manager():
    manager = AsyncMock()
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture
def event_queue():
    return asyncio.Queue()


@pytest.fixture
def dispatcher(event_queue, machine_status, ws_manager):
    return EventDispatcher(event_queue, machine_status, ws_manager)


class TestCoinInEvent:
    async def test_coin_in_updates_status(
        self, dispatcher, event_queue, machine_status, ws_manager
    ):
        event_data = {
            "event": "COIN_IN", "denom": 5, "total": 5,
            "_controller": "COIN_SECURITY",
        }
        await dispatcher._handle_event(event_data)

        snap = machine_status.snapshot()
        assert snap.consumables.coin_counts["PHP_5"] == 1

    async def test_coin_in_broadcasts_ws(
        self, dispatcher, event_queue, machine_status, ws_manager
    ):
        event_data = {
            "event": "COIN_IN", "denom": 10, "total": 10,
            "_controller": "COIN_SECURITY",
        }
        await dispatcher._handle_event(event_data)

        ws_manager.broadcast.assert_called_once()
        call_args = ws_manager.broadcast.call_args[0][0]
        assert call_args.type == WSEventType.COIN_INSERTED
        assert call_args.payload["denom"] == 10


class TestTamperEvent:
    async def test_tamper_updates_security(
        self, dispatcher, event_queue, machine_status, ws_manager
    ):
        event_data = {
            "event": "TAMPER", "sensor": "A",
            "_controller": "COIN_SECURITY",
        }
        await dispatcher._handle_event(event_data)

        snap = machine_status.snapshot()
        assert snap.security.tamper_active is True
        assert snap.security.last_tamper_sensor == "A"

    async def test_tamper_broadcasts_ws(
        self, dispatcher, event_queue, machine_status, ws_manager
    ):
        event_data = {
            "event": "TAMPER", "sensor": "B",
            "_controller": "COIN_SECURITY",
        }
        await dispatcher._handle_event(event_data)

        call_args = ws_manager.broadcast.call_args[0][0]
        assert call_args.type == WSEventType.TAMPER
        assert call_args.payload["sensor"] == "B"


class TestDoorStateEvent:
    async def test_door_unlock_updates_security(
        self, dispatcher, event_queue, machine_status, ws_manager
    ):
        event_data = {
            "event": "DOOR_STATE", "locked": False,
            "_controller": "COIN_SECURITY",
        }
        await dispatcher._handle_event(event_data)

        snap = machine_status.snapshot()
        assert snap.security.locked is False


class TestReadyEvent:
    async def test_bill_ready_updates_device(
        self, dispatcher, event_queue, machine_status, ws_manager
    ):
        event_data = {
            "event": "READY", "version": "2.0.0", "controller": "BILL",
            "_controller": "BILL",
        }
        await dispatcher._handle_event(event_data)

        snap = machine_status.snapshot()
        assert snap.bill_device.connection.value == "connected"
        assert snap.bill_device.firmware_version == "2.0.0"

    async def test_coin_ready_updates_device(
        self, dispatcher, event_queue, machine_status, ws_manager
    ):
        event_data = {
            "event": "READY", "version": "2.0.0",
            "controller": "COIN_SECURITY",
            "_controller": "COIN_SECURITY",
        }
        await dispatcher._handle_event(event_data)

        snap = machine_status.snapshot()
        assert snap.coin_device.connection.value == "connected"

    async def test_ready_broadcasts_device_connected(
        self, dispatcher, event_queue, machine_status, ws_manager
    ):
        event_data = {
            "event": "READY", "version": "2.0.0", "controller": "BILL",
            "_controller": "BILL",
        }
        await dispatcher._handle_event(event_data)

        call_args = ws_manager.broadcast.call_args[0][0]
        assert call_args.type == WSEventType.DEVICE_CONNECTED
