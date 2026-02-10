import os

import pytest

# Force mock serial for all tests
os.environ["USE_MOCK_SERIAL"] = "true"
os.environ["MOCK_DELAY"] = "0"
os.environ["SERIAL_PORT_BILL"] = "MOCK_BILL"
os.environ["SERIAL_PORT_COIN"] = "MOCK_COIN"
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "DEBUG"

from app.api.ws import ConnectionManager
from app.core.config import Settings
from app.drivers.mock_serial import MockSerial
from app.services.machine_status import MachineStatus


@pytest.fixture
def test_settings():
    return Settings(
        use_mock_serial=True,
        mock_delay=0.0,
        serial_port_bill="MOCK_BILL",
        serial_port_coin="MOCK_COIN",
        environment="test",
        log_level="DEBUG",
    )


@pytest.fixture
def mock_serial_bill():
    return MockSerial(port="MOCK_BILL", baudrate=115200, timeout=1.0)


@pytest.fixture
def mock_serial_coin():
    return MockSerial(port="MOCK_COIN", baudrate=115200, timeout=1.0)


@pytest.fixture
def machine_status(test_settings):
    return MachineStatus(test_settings)


@pytest.fixture
def ws_manager():
    return ConnectionManager()
