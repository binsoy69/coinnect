import asyncio

import pytest

from app.core.config import Settings
from app.drivers.serial_manager import SerialManager


@pytest.fixture
def settings():
    return Settings(
        use_mock_serial=True,
        mock_delay=0.0,
        serial_port_bill="MOCK_BILL",
        serial_port_coin="MOCK_COIN",
        serial_timeout=2,
        environment="test",
    )


@pytest.fixture
async def serial_manager(settings):
    sm = SerialManager(settings)
    await sm.startup()
    yield sm
    await sm.shutdown()


class TestSerialManagerLifecycle:
    async def test_startup_creates_connections(self, serial_manager):
        assert serial_manager.bill_connection is not None
        assert serial_manager.coin_connection is not None
        assert serial_manager.bill_connection.is_connected
        assert serial_manager.coin_connection.is_connected

    async def test_shutdown_disconnects(self, settings):
        sm = SerialManager(settings)
        await sm.startup()
        assert sm.bill_connection.is_connected
        await sm.shutdown()
        assert not sm.bill_connection.is_connected


class TestBillCommands:
    async def test_ping(self, serial_manager):
        resp = await serial_manager.send_bill_command({"cmd": "PING"})
        assert resp["status"] == "OK"
        assert resp["message"] == "PONG"

    async def test_version(self, serial_manager):
        resp = await serial_manager.send_bill_command({"cmd": "VERSION"})
        assert resp["controller"] == "BILL"

    async def test_sort(self, serial_manager):
        resp = await serial_manager.send_bill_command(
            {"cmd": "SORT", "denom": "PHP_100"}
        )
        assert resp["status"] == "READY"
        assert resp["slot"] == 3

    async def test_home(self, serial_manager):
        resp = await serial_manager.send_bill_command({"cmd": "HOME"})
        assert resp["status"] == "OK"

    async def test_dispense(self, serial_manager):
        resp = await serial_manager.send_bill_command(
            {"cmd": "DISPENSE", "denom": "PHP_500", "count": 2}
        )
        assert resp["status"] == "OK"
        assert resp["dispensed"] == 2


class TestCoinCommands:
    async def test_ping(self, serial_manager):
        resp = await serial_manager.send_coin_command({"cmd": "PING"})
        assert resp["status"] == "OK"

    async def test_version(self, serial_manager):
        resp = await serial_manager.send_coin_command({"cmd": "VERSION"})
        assert resp["controller"] == "COIN_SECURITY"

    async def test_coin_dispense(self, serial_manager):
        resp = await serial_manager.send_coin_command(
            {"cmd": "COIN_DISPENSE", "denom": 5, "count": 3}
        )
        assert resp["status"] == "OK"
        assert resp["dispensed"] == 3

    async def test_coin_change(self, serial_manager):
        resp = await serial_manager.send_coin_command(
            {"cmd": "COIN_CHANGE", "amount": 47}
        )
        assert resp["status"] == "OK"
        total = sum(int(k) * v for k, v in resp["breakdown"].items())
        assert total == 47

    async def test_security_lock(self, serial_manager):
        resp = await serial_manager.send_coin_command({"cmd": "SECURITY_LOCK"})
        assert resp["locked"] is True

    async def test_security_unlock(self, serial_manager):
        resp = await serial_manager.send_coin_command({"cmd": "SECURITY_UNLOCK"})
        assert resp["locked"] is False


class TestEventQueue:
    async def test_injected_event_appears_in_queue(self, serial_manager):
        mock = serial_manager.coin_connection.mock_serial
        mock.inject_event({"event": "COIN_IN", "denom": 5, "total": 5})

        # Give the reader thread time to pick it up
        await asyncio.sleep(0.2)

        assert not serial_manager.event_queue.empty()
        event = await serial_manager.event_queue.get()
        assert event["event"] == "COIN_IN"
        assert event["denom"] == 5

    async def test_tamper_event(self, serial_manager):
        mock = serial_manager.coin_connection.mock_serial
        mock.inject_event({"event": "TAMPER", "sensor": "A"})

        await asyncio.sleep(0.2)

        event = await serial_manager.event_queue.get()
        assert event["event"] == "TAMPER"
