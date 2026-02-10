import pytest

from app.core.config import Settings
from app.services.machine_status import MachineStatus


@pytest.fixture
def status():
    settings = Settings(
        use_mock_serial=True,
        serial_port_bill="MOCK",
        serial_port_coin="MOCK",
        low_bill_threshold=10,
        low_coin_threshold=5,
    )
    return MachineStatus(settings)


class TestSnapshot:
    def test_initial_snapshot(self, status):
        snap = status.snapshot()
        assert snap.bill_device.connection.value == "disconnected"
        assert snap.coin_device.connection.value == "disconnected"
        assert snap.sorter.homed is False
        assert snap.security.locked is True
        assert snap.security.tamper_active is False

    def test_snapshot_is_immutable_copy(self, status):
        snap1 = status.snapshot()
        status.update_sorter(homed=True)
        snap2 = status.snapshot()
        assert snap1.sorter.homed is False
        assert snap2.sorter.homed is True


class TestDeviceUpdates:
    def test_update_bill_device(self, status):
        status.update_bill_device(
            connection="connected", firmware_version="2.0.0"
        )
        snap = status.snapshot()
        assert snap.bill_device.connection.value == "connected"
        assert snap.bill_device.firmware_version == "2.0.0"
        assert snap.bill_device.controller_type == "BILL"

    def test_update_coin_device(self, status):
        status.update_coin_device(
            connection="connected", firmware_version="2.0.0"
        )
        snap = status.snapshot()
        assert snap.coin_device.connection.value == "connected"
        assert snap.coin_device.controller_type == "COIN_SECURITY"


class TestSorterUpdates:
    def test_update_sorter(self, status):
        status.update_sorter(homed=True, position=14600, slot=3)
        snap = status.snapshot()
        assert snap.sorter.homed is True
        assert snap.sorter.current_position == 14600
        assert snap.sorter.current_slot == 3


class TestSecurityUpdates:
    def test_update_locked(self, status):
        status.update_security(locked=False)
        snap = status.snapshot()
        assert snap.security.locked is False

    def test_update_tamper(self, status):
        status.update_security(tamper_active=True, sensor="A")
        snap = status.snapshot()
        assert snap.security.tamper_active is True
        assert snap.security.last_tamper_sensor == "A"
        assert snap.security.last_tamper_time is not None


class TestConsumables:
    def test_increment_bill_storage(self, status):
        status.increment_bill_storage("PHP_100", 5)
        snap = status.snapshot()
        assert snap.consumables.bill_storage_counts["PHP_100"] == 5

    def test_increment_usd_maps_to_usd_key(self, status):
        status.increment_bill_storage("USD_50", 2)
        snap = status.snapshot()
        assert snap.consumables.bill_storage_counts["USD"] == 2

    def test_decrement_bill_dispenser(self, status):
        status.set_dispenser_counts({"PHP_100": 20})
        status.decrement_bill_dispenser("PHP_100", 3)
        snap = status.snapshot()
        assert snap.consumables.bill_dispenser_counts["PHP_100"] == 17

    def test_decrement_doesnt_go_negative(self, status):
        status.decrement_bill_dispenser("PHP_100", 100)
        snap = status.snapshot()
        assert snap.consumables.bill_dispenser_counts["PHP_100"] == 0

    def test_increment_coin(self, status):
        status.increment_coin("PHP_5", 10)
        snap = status.snapshot()
        assert snap.consumables.coin_counts["PHP_5"] == 10

    def test_decrement_coin(self, status):
        status.set_coin_counts({"PHP_5": 20})
        status.decrement_coin("PHP_5", 5)
        snap = status.snapshot()
        assert snap.consumables.coin_counts["PHP_5"] == 15


class TestAlerts:
    def test_low_bill_alert(self, status):
        status.set_dispenser_counts({"PHP_100": 5})
        status.decrement_bill_dispenser("PHP_100", 0)
        alerts = status.get_alerts()
        low_alerts = [a for a in alerts if a.startswith("LOW_BILL")]
        assert any("PHP_100" in a for a in low_alerts)

    def test_empty_bill_alert(self, status):
        status.set_dispenser_counts({"PHP_100": 0})
        status.decrement_bill_dispenser("PHP_100", 0)
        alerts = status.get_alerts()
        assert any("EMPTY_BILL:PHP_100" in a for a in alerts)


class TestOnChangeCallback:
    def test_callback_fires(self, status):
        changes = []
        status.set_on_change(lambda: changes.append(1))
        status.update_sorter(homed=True)
        assert len(changes) == 1

    def test_callback_fires_on_consumable_change(self, status):
        changes = []
        status.set_on_change(lambda: changes.append(1))
        status.increment_bill_storage("PHP_100")
        assert len(changes) == 1
