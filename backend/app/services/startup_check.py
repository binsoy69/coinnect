import asyncio
import logging
from typing import Dict

from app.core.config import Settings
from app.api.ws import ConnectionManager
from app.drivers.serial_manager import SerialManager
from app.drivers.bill_controller import BillController
from app.drivers.coin_security_controller import CoinSecurityController
from app.drivers.camera_controller import CameraControllerBase
from app.services.receipt_service import ReceiptService
from app.ml.bill_authenticator import BillAuthenticatorBase
from app.services.machine_status import MachineStatus
from app.models.events import WSEvent, WSEventType

logger = logging.getLogger(__name__)


class StartupCheckService:
    def __init__(
        self,
        settings: Settings,
        serial_manager: SerialManager,
        bill_controller: BillController,
        coin_controller: CoinSecurityController,
        camera: CameraControllerBase,
        receipt_service: ReceiptService,
        authenticator: BillAuthenticatorBase,
        machine_status: MachineStatus,
        ws_manager: ConnectionManager,
    ):
        self._settings = settings
        self._serial_manager = serial_manager
        self._bill_controller = bill_controller
        self._coin_controller = coin_controller
        self._camera = camera
        self._receipt_service = receipt_service
        self._authenticator = authenticator
        self._status = machine_status
        self._ws = ws_manager
        self._lock = asyncio.Lock()

    async def run_checks(self) -> Dict[str, str]:
        """Runs all diagnostic checks and updates the MachineStatus store.

        Returns a dictionary of component names mapping to their error messages (empty if all OK).
        """
        async with self._lock:
            logger.info("Running system startup diagnostic checks...")
            errors = {}

            # 1. Arduino Mega #1 (Bill) connection & ping
            try:
                if not self._serial_manager.bill_connection or not self._serial_manager.bill_connection.is_connected:
                    if self._serial_manager.bill_connection:
                        logger.info("Attempting to connect Arduino Mega #1 (Bill)...")
                        await self._serial_manager.bill_connection.connect()
                    else:
                        errors["arduino_bill"] = "Bill connection not initialized"
                
                if "arduino_bill" not in errors:
                    pong = await self._bill_controller.ping()
                    if not pong or pong.message != "PONG":
                        errors["arduino_bill"] = "Failed to receive PONG response from Bill Controller"
                    else:
                        self._status.update_bill_device(connection="connected")
            except Exception as e:
                errors["arduino_bill"] = f"Bill controller connection failed: {str(e)}"
                self._status.update_bill_device(connection="disconnected", last_error=str(e))

            # 2. Arduino Mega #2 (Coin & Security) connection & ping
            try:
                if not self._serial_manager.coin_connection or not self._serial_manager.coin_connection.is_connected:
                    if self._serial_manager.coin_connection:
                        logger.info("Attempting to connect Arduino Mega #2 (Coin/Security)...")
                        await self._serial_manager.coin_connection.connect()
                    else:
                        errors["arduino_coin"] = "Coin connection not initialized"

                if "arduino_coin" not in errors:
                    pong = await self._coin_controller.ping()
                    if not pong or pong.message != "PONG":
                        errors["arduino_coin"] = "Failed to receive PONG response from Coin/Security Controller"
                    else:
                        self._status.update_coin_device(connection="connected")
            except Exception as e:
                errors["arduino_coin"] = f"Coin controller connection failed: {str(e)}"
                self._status.update_coin_device(connection="disconnected", last_error=str(e))

            for name, controller in (("arduino_bill", self._bill_controller), ("arduino_coin", self._coin_controller)):
                if name not in errors:
                    try:
                        await controller.verify_converter_protocol()
                        if name == "arduino_coin":
                            await controller.verify_intake_capabilities()
                    except Exception as exc:
                        errors[name] = f"Converter firmware upgrade required: {exc}"

            # 3. Camera check
            try:
                if not self._settings.use_mock_hardware:
                    logger.info("Initializing camera for diagnostic check...")
                    await self._camera.initialize()
                    frame = await self._camera.capture_frame()
                    if frame is None or frame.size == 0:
                        errors["camera"] = "Captured camera frame is empty"
            except Exception as e:
                errors["camera"] = f"Camera initialization failed: {str(e)}"

            # 4. Printer check
            if self._settings.paperang_enabled:
                try:
                    logger.info("Verifying Bluetooth printer connection...")
                    connected = await self._receipt_service.check_connection()
                    if not connected:
                        errors["printer"] = "Printer disconnected or Bluetooth discovery failed"
                except Exception as e:
                    errors["printer"] = f"Printer connection verification failed: {str(e)}"

            # 5. YOLO ML Models check
            if not self._settings.use_mock_hardware:
                try:
                    logger.info("Verifying YOLO model pre-loading...")
                    await self._authenticator.preload_models()
                    if self._authenticator.load_errors:
                        failed = [f"{k}: {v}" for k, v in self._authenticator.load_errors.items()]
                        errors["yolo_models"] = f"Failed to load models: {', '.join(failed)}"
                except Exception as e:
                    errors["yolo_models"] = f"YOLO model check failed: {str(e)}"

            # Update thread-safe machine status state
            self._status.update_startup_checks(performed=True, errors=errors)
            snapshot = self._status.snapshot()

            # Broadcast event to frontend clients
            logger.info(f"System checks complete. has_errors={snapshot.startup_checks.has_errors} errors={errors}")
            await self._ws.broadcast(WSEvent(
                type=WSEventType.STATE_CHANGE,
                payload={"startup_checks": snapshot.startup_checks.model_dump(mode="json")}
            ))

            return errors
