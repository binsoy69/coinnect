import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.ws import ConnectionManager
from app.core.config import get_settings
from app.core.database import close_db, get_session_factory, init_db
from app.core.logging import setup_logging
from app.drivers.bill_controller import BillController
from app.drivers.coin_security_controller import CoinSecurityController
from app.drivers.serial_manager import SerialManager
from app.services.bill_acceptor import BillAcceptor
from app.services.dispense_orchestrator import DispenseOrchestrator
from app.services.event_dispatcher import EventDispatcher
from app.services.machine_status import MachineStatus
from app.services.transaction_orchestrator import TransactionOrchestrator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info(
        f"Coinnect backend starting "
        f"(env={settings.environment}, mock_serial={settings.use_mock_serial}, "
        f"mock_hw={settings.use_mock_hardware})"
    )

    # --- Phase 2: Serial communication layer ---
    serial_manager = SerialManager(settings)
    ws_manager = ConnectionManager()
    machine_status = MachineStatus(settings)
    event_dispatcher = EventDispatcher(
        serial_manager.event_queue, machine_status, ws_manager
    )

    # --- Phase 3: Database ---
    await init_db()

    # --- Phase 3: Hardware controllers (GPIO + Camera + ML) ---
    if settings.use_mock_hardware:
        from app.drivers.mock_camera_controller import MockCameraController
        from app.drivers.mock_gpio_controller import MockGPIOController
        from app.ml.mock_authenticator import MockBillAuthenticator

        gpio = MockGPIOController()
        camera = MockCameraController()
        authenticator = MockBillAuthenticator()
        logger.info("Using mock hardware controllers")
    else:
        from app.drivers.camera_controller import USBCameraController
        from app.drivers.gpio_controller import RPiGPIOController
        from app.ml.bill_authenticator import YOLOBillAuthenticator

        gpio = RPiGPIOController()
        camera = USBCameraController(settings.camera_device)
        authenticator = YOLOBillAuthenticator(
            settings.yolo_auth_model_path,
            settings.yolo_denom_model_path,
            settings.yolo_confidence_threshold,
        )
        logger.info("Using real hardware controllers")

    await gpio.setup()
    await camera.initialize()

    # --- Phase 3: Service layer ---
    bill_controller = BillController(serial_manager)
    coin_controller = CoinSecurityController(serial_manager)

    bill_acceptor = BillAcceptor(
        gpio=gpio,
        camera=camera,
        authenticator=authenticator,
        bill_controller=bill_controller,
        machine_status=machine_status,
        ws_manager=ws_manager,
        settings=settings,
    )

    dispense_orchestrator = DispenseOrchestrator(
        bill_controller=bill_controller,
        coin_controller=coin_controller,
        machine_status=machine_status,
        ws_manager=ws_manager,
    )

    transaction_orchestrator = TransactionOrchestrator(
        bill_acceptor=bill_acceptor,
        dispense_orchestrator=dispense_orchestrator,
        machine_status=machine_status,
        ws_manager=ws_manager,
        db_session_factory=get_session_factory(),
    )

    # Store on app state for dependency injection in endpoints
    app.state.serial_manager = serial_manager
    app.state.ws_manager = ws_manager
    app.state.machine_status = machine_status
    app.state.event_dispatcher = event_dispatcher
    app.state.settings = settings
    app.state.gpio = gpio
    app.state.camera = camera
    app.state.bill_acceptor = bill_acceptor
    app.state.dispense_orchestrator = dispense_orchestrator
    app.state.transaction_orchestrator = transaction_orchestrator

    # Startup
    await serial_manager.startup()
    await event_dispatcher.start()

    # Recover any transactions interrupted by crash/power loss
    await transaction_orchestrator.recover_pending_transactions()

    logger.info("Coinnect backend ready")
    yield

    # Shutdown
    logger.info("Coinnect backend shutting down")
    await event_dispatcher.stop()
    await serial_manager.shutdown()
    await camera.release()
    await gpio.cleanup()
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Coinnect Backend",
        version="0.1.0",
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
