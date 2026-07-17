import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.config import Settings
from app.services.startup_check import StartupCheckService
from app.services.machine_status import MachineStatus
from app.api.ws import ConnectionManager
from app.drivers.serial_manager import SerialManager
from app.drivers.bill_controller import BillController
from app.drivers.coin_security_controller import CoinSecurityController
from app.drivers.camera_controller import CameraControllerBase
from app.services.receipt_service import ReceiptService
from app.ml.bill_authenticator import BillAuthenticatorBase
from app.models.serial_messages import PingResponse


@pytest.fixture
def mock_serial_manager():
    sm = MagicMock(spec=SerialManager)
    # mock connections
    bill_conn = MagicMock()
    bill_conn.is_connected = True
    bill_conn.connect = AsyncMock()
    
    coin_conn = MagicMock()
    coin_conn.is_connected = True
    coin_conn.connect = AsyncMock()

    sm.bill_connection = bill_conn
    sm.coin_connection = coin_conn
    return sm


@pytest.fixture
def mock_bill_controller():
    bc = MagicMock(spec=BillController)
    bc.ping = AsyncMock(return_value=PingResponse(status="OK", message="PONG"))
    return bc


@pytest.fixture
def mock_coin_controller():
    cc = MagicMock(spec=CoinSecurityController)
    cc.ping = AsyncMock(return_value=PingResponse(status="OK", message="PONG"))
    return cc


@pytest.fixture
def mock_camera():
    cam = MagicMock(spec=CameraControllerBase)
    cam.initialize = AsyncMock()
    import numpy as np
    cam.capture_frame = AsyncMock(return_value=np.zeros((10, 10, 3)))
    return cam


@pytest.fixture
def mock_receipt_service():
    rs = MagicMock(spec=ReceiptService)
    rs.check_connection = AsyncMock(return_value=True)
    return rs


@pytest.fixture
def mock_authenticator():
    auth = MagicMock(spec=BillAuthenticatorBase)
    auth.preload_models = AsyncMock()
    auth.load_errors = {}
    return auth


@pytest.fixture
def test_settings():
    return Settings(
        use_mock_serial=False,
        use_mock_hardware=False,
        paperang_enabled=True,
    )


@pytest.fixture
def machine_status(test_settings):
    return MachineStatus(test_settings)


@pytest.fixture
def ws_manager():
    wm = MagicMock(spec=ConnectionManager)
    wm.broadcast = AsyncMock()
    return wm


@pytest.mark.anyio
async def test_startup_checks_all_success(
    test_settings,
    mock_serial_manager,
    mock_bill_controller,
    mock_coin_controller,
    mock_camera,
    mock_receipt_service,
    mock_authenticator,
    machine_status,
    ws_manager,
):
    service = StartupCheckService(
        settings=test_settings,
        serial_manager=mock_serial_manager,
        bill_controller=mock_bill_controller,
        coin_controller=mock_coin_controller,
        camera=mock_camera,
        receipt_service=mock_receipt_service,
        authenticator=mock_authenticator,
        machine_status=machine_status,
        ws_manager=ws_manager,
    )

    errors = await service.run_checks()
    assert len(errors) == 0

    snap = machine_status.snapshot()
    assert snap.startup_checks.performed is True
    assert snap.startup_checks.has_errors is False
    assert len(snap.startup_checks.errors) == 0
    ws_manager.broadcast.assert_called_once()


@pytest.mark.anyio
async def test_startup_checks_failures(
    test_settings,
    mock_serial_manager,
    mock_bill_controller,
    mock_coin_controller,
    mock_camera,
    mock_receipt_service,
    mock_authenticator,
    machine_status,
    ws_manager,
):
    # Simulate Bill Controller Ping failure
    mock_bill_controller.ping.side_effect = Exception("Serial Timeout")
    
    # Simulate Camera frame grab failure
    mock_camera.capture_frame.side_effect = Exception("Hardware failure")

    # Simulate YOLO model load errors
    mock_authenticator.load_errors = {"PHP_auth": "File not found"}

    # Simulate Printer disconnected
    mock_receipt_service.check_connection.return_value = False

    service = StartupCheckService(
        settings=test_settings,
        serial_manager=mock_serial_manager,
        bill_controller=mock_bill_controller,
        coin_controller=mock_coin_controller,
        camera=mock_camera,
        receipt_service=mock_receipt_service,
        authenticator=mock_authenticator,
        machine_status=machine_status,
        ws_manager=ws_manager,
    )

    errors = await service.run_checks()
    assert len(errors) == 4
    assert "arduino_bill" in errors
    assert "camera" in errors
    assert "printer" in errors
    assert "yolo_models" in errors
    assert "arduino_coin" not in errors

    snap = machine_status.snapshot()
    assert snap.startup_checks.performed is True
    assert snap.startup_checks.has_errors is True
    assert snap.startup_checks.errors["arduino_bill"] == "Bill controller connection failed: Serial Timeout"
