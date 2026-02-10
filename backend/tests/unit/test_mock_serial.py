import json

import pytest

from app.drivers.mock_serial import MockSerial


class TestMockSerialSimpleMode:
    """Tests for MockSerial with mock_delay=0 (simple mode)."""

    @pytest.fixture
    def bill_mock(self):
        return MockSerial(port="MOCK_BILL", baudrate=115200, timeout=1.0)

    @pytest.fixture
    def coin_mock(self):
        return MockSerial(port="MOCK_COIN", baudrate=115200, timeout=1.0)

    def _send_and_read(self, mock: MockSerial, cmd: dict) -> dict:
        data = (json.dumps(cmd) + "\n").encode()
        mock.write(data)
        line = mock.readline()
        return json.loads(line.decode())

    # --- Bill Controller (Arduino #1) ---

    def test_sort_valid_denom(self, bill_mock):
        resp = self._send_and_read(bill_mock, {"cmd": "SORT", "denom": "PHP_100"})
        assert resp["status"] == "READY"
        assert resp["slot"] == 3

    def test_sort_invalid_denom(self, bill_mock):
        resp = self._send_and_read(bill_mock, {"cmd": "SORT", "denom": "INVALID"})
        assert resp["status"] == "ERROR"
        assert resp["code"] == "INVALID_DENOM"

    def test_home(self, bill_mock):
        resp = self._send_and_read(bill_mock, {"cmd": "HOME"})
        assert resp["status"] == "OK"
        assert resp["position"] == 0

    def test_sort_status(self, bill_mock):
        resp = self._send_and_read(bill_mock, {"cmd": "SORT_STATUS"})
        assert resp["status"] == "OK"
        assert "homed" in resp
        assert "position" in resp

    def test_dispense(self, bill_mock):
        resp = self._send_and_read(
            bill_mock, {"cmd": "DISPENSE", "denom": "PHP_500", "count": 3}
        )
        assert resp["status"] == "OK"
        assert resp["dispensed"] == 3

    def test_dispense_invalid_denom(self, bill_mock):
        resp = self._send_and_read(
            bill_mock, {"cmd": "DISPENSE", "denom": "BAD", "count": 1}
        )
        assert resp["status"] == "ERROR"

    def test_dispense_invalid_count(self, bill_mock):
        resp = self._send_and_read(
            bill_mock, {"cmd": "DISPENSE", "denom": "PHP_100", "count": 25}
        )
        assert resp["status"] == "ERROR"
        assert resp["code"] == "INVALID_COUNT"

    def test_dispense_status(self, bill_mock):
        resp = self._send_and_read(
            bill_mock, {"cmd": "DISPENSE_STATUS", "denom": "PHP_100"}
        )
        assert resp["status"] == "OK"
        assert resp["ready"] is True

    # --- Coin & Security Controller (Arduino #2) ---

    def test_coin_dispense(self, coin_mock):
        resp = self._send_and_read(
            coin_mock, {"cmd": "COIN_DISPENSE", "denom": 5, "count": 3}
        )
        assert resp["status"] == "OK"
        assert resp["dispensed"] == 3

    def test_coin_dispense_invalid_denom(self, coin_mock):
        resp = self._send_and_read(
            coin_mock, {"cmd": "COIN_DISPENSE", "denom": 7, "count": 1}
        )
        assert resp["status"] == "ERROR"
        assert resp["code"] == "INVALID_DENOM"

    def test_coin_change(self, coin_mock):
        resp = self._send_and_read(
            coin_mock, {"cmd": "COIN_CHANGE", "amount": 47}
        )
        assert resp["status"] == "OK"
        breakdown = resp["breakdown"]
        total = sum(int(k) * v for k, v in breakdown.items())
        assert total == 47

    def test_coin_change_breakdown_correct(self, coin_mock):
        resp = self._send_and_read(
            coin_mock, {"cmd": "COIN_CHANGE", "amount": 47}
        )
        b = resp["breakdown"]
        # 47 = 2*20 + 0*10 + 1*5 + 2*1
        assert b.get("20") == 2
        assert b.get("5") == 1
        assert b.get("1") == 2

    def test_coin_reset(self, coin_mock):
        resp = self._send_and_read(coin_mock, {"cmd": "COIN_RESET"})
        assert resp["status"] == "OK"
        assert "previous_total" in resp

    def test_security_lock(self, coin_mock):
        resp = self._send_and_read(coin_mock, {"cmd": "SECURITY_LOCK"})
        assert resp["status"] == "OK"
        assert resp["locked"] is True

    def test_security_unlock(self, coin_mock):
        resp = self._send_and_read(coin_mock, {"cmd": "SECURITY_UNLOCK"})
        assert resp["status"] == "OK"
        assert resp["locked"] is False

    def test_security_status(self, coin_mock):
        resp = self._send_and_read(coin_mock, {"cmd": "SECURITY_STATUS"})
        assert resp["status"] == "OK"
        assert "locked" in resp
        assert "tamper_a" in resp

    # --- System commands ---

    def test_ping(self, bill_mock):
        resp = self._send_and_read(bill_mock, {"cmd": "PING"})
        assert resp["status"] == "OK"
        assert resp["message"] == "PONG"

    def test_version_bill(self, bill_mock):
        resp = self._send_and_read(bill_mock, {"cmd": "VERSION"})
        assert resp["controller"] == "BILL"
        assert resp["version"] == "2.0.0"

    def test_version_coin(self, coin_mock):
        resp = self._send_and_read(coin_mock, {"cmd": "VERSION"})
        assert resp["controller"] == "COIN_SECURITY"

    def test_unknown_command(self, bill_mock):
        resp = self._send_and_read(bill_mock, {"cmd": "NONEXISTENT"})
        assert resp["status"] == "ERROR"
        assert resp["code"] == "UNKNOWN_CMD"

    def test_invalid_json(self, bill_mock):
        bill_mock.write(b"not json\n")
        line = bill_mock.readline()
        resp = json.loads(line.decode())
        assert resp["status"] == "ERROR"
        assert resp["code"] == "PARSE_ERROR"


class TestMockSerialFaultInjection:
    def test_inject_fault(self):
        mock = MockSerial(port="MOCK_BILL", timeout=1.0)
        mock.inject_fault("JAM")
        data = (json.dumps({"cmd": "DISPENSE", "denom": "PHP_100", "count": 1}) + "\n").encode()
        mock.write(data)
        line = mock.readline()
        resp = json.loads(line.decode())
        assert resp["status"] == "ERROR"
        assert resp["code"] == "JAM"

    def test_fault_clears_after_one_use(self):
        mock = MockSerial(port="MOCK_BILL", timeout=1.0)
        mock.inject_fault("TIMEOUT")

        # First command: fault
        mock.write((json.dumps({"cmd": "PING"}) + "\n").encode())
        resp1 = json.loads(mock.readline().decode())
        assert resp1["status"] == "ERROR"

        # Second command: normal
        mock.write((json.dumps({"cmd": "PING"}) + "\n").encode())
        resp2 = json.loads(mock.readline().decode())
        assert resp2["status"] == "OK"

    def test_inject_event(self):
        mock = MockSerial(port="MOCK_COIN", timeout=1.0)
        mock.inject_event({"event": "COIN_IN", "denom": 5, "total": 5})
        line = mock.readline()
        evt = json.loads(line.decode())
        assert evt["event"] == "COIN_IN"
        assert evt["denom"] == 5


class TestMockSerialRealisticState:
    def test_sort_requires_homed_in_realistic_mode(self):
        mock = MockSerial(port="MOCK_BILL", timeout=1.0, mock_delay=0.01)
        data = (json.dumps({"cmd": "SORT", "denom": "PHP_100"}) + "\n").encode()
        mock.write(data)
        resp = json.loads(mock.readline().decode())
        assert resp["status"] == "ERROR"
        assert resp["code"] == "NOT_HOMED"

    def test_home_then_sort_works_in_realistic_mode(self):
        mock = MockSerial(port="MOCK_BILL", timeout=2.0, mock_delay=0.01)

        # Home first
        mock.write((json.dumps({"cmd": "HOME"}) + "\n").encode())
        resp = json.loads(mock.readline().decode())
        assert resp["status"] == "OK"

        # Now sort
        mock.write((json.dumps({"cmd": "SORT", "denom": "PHP_100"}) + "\n").encode())
        resp = json.loads(mock.readline().decode())
        assert resp["status"] == "READY"
        assert resp["slot"] == 3

    def test_set_state(self):
        mock = MockSerial(port="MOCK_BILL", timeout=1.0, mock_delay=0.01)
        mock.set_state(homed=True)
        mock.write((json.dumps({"cmd": "SORT", "denom": "PHP_20"}) + "\n").encode())
        resp = json.loads(mock.readline().decode())
        assert resp["status"] == "READY"
        assert resp["slot"] == 1

    def test_reset_clears_state(self):
        mock = MockSerial(port="MOCK_BILL", timeout=2.0, mock_delay=0.01)
        mock.set_state(homed=True)
        mock.write((json.dumps({"cmd": "RESET"}) + "\n").encode())
        json.loads(mock.readline().decode())

        # After reset, should not be homed
        mock.write((json.dumps({"cmd": "SORT_STATUS"}) + "\n").encode())
        resp = json.loads(mock.readline().decode())
        assert resp["homed"] is False
