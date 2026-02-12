import os

import pytest

# Force mock serial and hardware for all tests
os.environ["USE_MOCK_SERIAL"] = "true"
os.environ["USE_MOCK_HARDWARE"] = "true"
os.environ["MOCK_DELAY"] = "0"
os.environ["SERIAL_PORT_BILL"] = "MOCK_BILL"
os.environ["SERIAL_PORT_COIN"] = "MOCK_COIN"
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"

from app.api.ws import ConnectionManager
from app.core.config import Settings
from app.drivers.mock_camera_controller import MockCameraController
from app.drivers.mock_gpio_controller import MockGPIOController
from app.drivers.mock_serial import MockSerial
from app.ml.mock_authenticator import MockBillAuthenticator
from app.services.machine_status import MachineStatus


@pytest.fixture
def test_settings():
    return Settings(
        use_mock_serial=True,
        use_mock_hardware=True,
        mock_delay=0.0,
        serial_port_bill="MOCK_BILL",
        serial_port_coin="MOCK_COIN",
        environment="test",
        log_level="DEBUG",
        db_url="sqlite+aiosqlite:///:memory:",
        # Zero delays for fast tests
        led_stabilization_delay=0.0,
        bill_position_timeout=0.5,
        bill_store_duration=0.0,
        bill_eject_duration=0.0,
        bill_acceptance_timeout=1,
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


@pytest.fixture
def mock_gpio():
    gpio = MockGPIOController()
    gpio.set_bill_at_entry(True)
    gpio.set_bill_in_position(True)
    return gpio


@pytest.fixture
def mock_camera():
    cam = MockCameraController()
    cam._initialized = True
    return cam


@pytest.fixture
def mock_authenticator():
    return MockBillAuthenticator()


@pytest.fixture
async def db_session():
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from app.models.db_models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session
    await engine.dispose()
