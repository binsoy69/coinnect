import logging
import sys
from contextlib import asynccontextmanager

# Reconfigure standard streams to use UTF-8 and replace invalid characters, preventing UnicodeEncodeErrors on platforms with limited default locales (e.g. latin-1 on RPi)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.ws import ConnectionManager
from app.core.config import get_settings
from app.core.database import close_db, get_session_factory, init_db
from app.core.errors import SerialError
from app.core.logging import setup_logging
from app.drivers.bill_controller import BillController
from app.drivers.coin_security_controller import CoinSecurityController
from app.drivers.serial_manager import SerialManager
from app.services.bill_acceptor import BillAcceptor
from app.services.dispense_orchestrator import DispenseOrchestrator
from app.services.event_dispatcher import EventDispatcher
from app.services.forex_rate_service import ForexRateService
from app.services.forex_transaction_orchestrator import ForexTransactionOrchestrator
from app.services.ewallet_orchestrator import EWalletOrchestrator
from app.services.machine_status import MachineStatus
from app.services.paymongo_client import PayMongoClient
from app.services.transaction_orchestrator import TransactionOrchestrator
from app.services.admin_session import AdminSessionService
from app.services.inventory_service import InventoryService
from app.services.receipt_service import ReceiptService
from app.services.operation_mode import OperationModeManager
from app.services.claim_service import ClaimService
from app.services.gateway_inbox import GatewayInboxWorker

logger = logging.getLogger(__name__)


async def _recover_physical_operations_for_startup(
    app: FastAPI,
    dispense_orchestrator: DispenseOrchestrator,
    claim_service: ClaimService,
) -> None:
    """Recover dispense state without taking the maintenance API offline.

    ``recover_started_operations`` marks inventory inconsistent before raising
    when a controller cannot acknowledge recovery. Allow the application to
    start so an operator can inspect and reconcile the affected operations.
    """
    app.state.startup_recovery_error = None
    try:
        await dispense_orchestrator.recover_started_operations(claim_service)
    except SerialError as exc:
        app.state.startup_recovery_error = str(exc)
        if (
            app.state.machine_status
            .should_block_dispensing_for_inventory_reconciliation()
        ):
            logger.critical(
                "Physical operation recovery is incomplete; dispensing remains "
                "disabled pending operator reconciliation: %s",
                exc,
            )
        else:
            logger.warning(
                "Physical operation recovery is incomplete and was recorded; "
                "dispensing remains enabled by reconciliation policy: %s",
                exc,
            )


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

    # --- Phase 3: Database ---
    await init_db()
    inventory_service = InventoryService(
        get_session_factory(), machine_status
    )
    await inventory_service.initialize()
    operation_mode = OperationModeManager()
    admin_sessions = AdminSessionService(settings, operation_mode)
    receipt_service = ReceiptService(settings)
    claim_service = ClaimService(
        get_session_factory(), ws_manager, receipt_service
    )
    bill_controller = BillController(serial_manager)
    coin_controller = CoinSecurityController(serial_manager)
    admin_sessions.set_coin_controller(coin_controller)
    event_dispatcher = EventDispatcher(
        serial_manager.event_queue,
        machine_status,
        ws_manager,
        inventory_service=inventory_service,
        admin_session_service=admin_sessions,
        coin_controller=coin_controller,
        bill_controller=bill_controller,
        serial_manager=serial_manager,
    )

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

        gpio = RPiGPIOController(settings=settings)
        camera = USBCameraController(settings.camera_device)
        authenticator = YOLOBillAuthenticator(
            settings.yolo_auth_model_path,
            settings.yolo_denom_model_path,
            settings.yolo_confidence_threshold,
            auth_model_path_usd=settings.yolo_auth_model_path_usd,
            denom_model_path_usd=settings.yolo_denom_model_path_usd,
            auth_model_path_eur=settings.yolo_auth_model_path_eur,
            denom_model_path_eur=settings.yolo_denom_model_path_eur,
        )
        logger.info("Using real hardware controllers")

    await gpio.setup()
    try:
        await camera.initialize()
    except Exception as exc:
        logger.error(f"Failed to initialize camera on startup (will be verified by diagnostics): {exc}")

    # --- Phase 3: Service layer ---

    bill_acceptor = BillAcceptor(
        gpio=gpio,
        camera=camera,
        authenticator=authenticator,
        bill_controller=bill_controller,
        machine_status=machine_status,
        ws_manager=ws_manager,
        settings=settings,
        inventory_service=inventory_service,
    )
    event_dispatcher.set_bill_acceptor(bill_acceptor)

    dispense_orchestrator = DispenseOrchestrator(
        bill_controller=bill_controller,
        coin_controller=coin_controller,
        machine_status=machine_status,
        ws_manager=ws_manager,
        inventory_service=inventory_service,
        db_session_factory=get_session_factory(),
    )

    transaction_orchestrator = TransactionOrchestrator(
        bill_acceptor=bill_acceptor,
        dispense_orchestrator=dispense_orchestrator,
        coin_controller=coin_controller,
        machine_status=machine_status,
        ws_manager=ws_manager,
        db_session_factory=get_session_factory(),
        operation_mode=operation_mode,
        receipt_service=receipt_service,
        claim_service=claim_service,
    )
    event_dispatcher.set_transaction_orchestrator(transaction_orchestrator)

    # --- Phase 5: Forex services ---
    forex_rate_service = ForexRateService(settings, ws_manager, machine_status, get_session_factory())

    forex_transaction_orchestrator = ForexTransactionOrchestrator(
        bill_acceptor=bill_acceptor,
        dispense_orchestrator=dispense_orchestrator,
        machine_status=machine_status,
        ws_manager=ws_manager,
        forex_rate_service=forex_rate_service,
        db_session_factory=get_session_factory(),
        operation_mode=operation_mode,
        receipt_service=receipt_service,
        claim_service=claim_service,
        inventory_service=inventory_service,
    )

    event_dispatcher.set_forex_orchestrator(forex_transaction_orchestrator)

    # --- Phase 4: PayMongo e-wallet services ---
    paymongo_client = PayMongoClient(settings)
    ewallet_orchestrator = EWalletOrchestrator(
        settings=settings,
        gateway=paymongo_client,
        inventory_service=inventory_service,
        bill_acceptor=bill_acceptor,
        dispenser=dispense_orchestrator,
        coin_controller=coin_controller,
        machine_status=machine_status,
        ws_manager=ws_manager,
        db_session_factory=get_session_factory(),
        operation_mode=operation_mode,
        receipt_service=receipt_service,
        claim_service=claim_service,
    )
    gateway_inbox = GatewayInboxWorker(
        get_session_factory(), ewallet_orchestrator, settings
    )
    event_dispatcher.set_ewallet_orchestrator(ewallet_orchestrator)

    # Store on app state for dependency injection in endpoints
    app.state.serial_manager = serial_manager
    app.state.ws_manager = ws_manager
    app.state.machine_status = machine_status
    app.state.event_dispatcher = event_dispatcher
    app.state.settings = settings
    app.state.gpio = gpio
    app.state.camera = camera
    app.state.bill_acceptor = bill_acceptor
    app.state.bill_controller = bill_controller
    app.state.coin_controller = coin_controller
    app.state.dispense_orchestrator = dispense_orchestrator
    app.state.transaction_orchestrator = transaction_orchestrator
    app.state.forex_rate_service = forex_rate_service
    app.state.forex_transaction_orchestrator = forex_transaction_orchestrator
    app.state.paymongo_client = paymongo_client
    app.state.ewallet_orchestrator = ewallet_orchestrator
    app.state.gateway_inbox = gateway_inbox
    app.state.db_session_factory = get_session_factory()
    app.state.inventory_service = inventory_service
    app.state.operation_mode = operation_mode
    app.state.admin_sessions = admin_sessions
    app.state.receipt_service = receipt_service
    app.state.claim_service = claim_service

    # Instantiate StartupCheckService
    from app.services.startup_check import StartupCheckService
    startup_check_service = StartupCheckService(
        settings=settings,
        serial_manager=serial_manager,
        bill_controller=bill_controller,
        coin_controller=coin_controller,
        camera=camera,
        receipt_service=receipt_service,
        authenticator=authenticator,
        machine_status=machine_status,
        ws_manager=ws_manager,
    )
    app.state.startup_check_service = startup_check_service

    # Startup
    try:
        await serial_manager.startup()
    except Exception as exc:
        logger.error(f"Failed to start serial manager: {exc}")
        raise
    
    # Update global constants map with environment settings
    from app.core.constants import update_slot_positions
    update_slot_positions(settings)
    
    # Push calibrated slot positions to Arduino Mega #1
    try:
        positions = [
            settings.slot_1_position,
            settings.slot_2_position,
            settings.slot_3_position,
            settings.slot_4_position,
            settings.slot_5_position,
            settings.slot_6_position,
            settings.slot_7_position,
            settings.slot_8_position,
        ]
        await bill_controller.set_slot_positions(positions)
        logger.info("Calibrated slot positions pushed to Arduino Mega #1")
    except Exception as exc:
        logger.error(f"Failed to push slot positions to Arduino Mega #1: {exc}")

    try:
        await coin_controller.set_coin_acceptor_enabled(False)
    except Exception as exc:
        logger.warning("Could not disable coin acceptor on startup: %s", exc)

    async def _background_home():
        try:
            logger.info("Initializing linear rail sorter homing sequence (background)...")
            await bill_controller.home()
            logger.info("Linear rail sorter homed successfully")
        except Exception as exc:
            logger.error(f"Failed to home linear rail sorter on startup: {exc}")

    import asyncio
    homing_task = asyncio.create_task(_background_home())
    app.state._homing_task = homing_task  # prevent GC

    logger.info("Scheduling asynchronous ML model pre-loading...")
    preload_task = asyncio.create_task(authenticator.preload_models())
    app.state._preload_task = preload_task  # prevent GC

    async def _background_printer_check():
        logger.info("Verifying printer connection in the background...")
        await receipt_service.check_connection()
        logger.info(f"Printer connection verified. Status: {receipt_service.is_connected}")
        machine_status.update_connectivity(printer_connected=receipt_service.is_connected)


    printer_check_task = asyncio.create_task(_background_printer_check())
    app.state._printer_check_task = printer_check_task  # prevent GC

    await event_dispatcher.start()

    # Recover any transactions interrupted by crash/power loss
    # Physical send intents are the recovery authority and must be resolved
    # before gateway events can authorize any further payout.
    await _recover_physical_operations_for_startup(
        app, dispense_orchestrator, claim_service
    )
    await transaction_orchestrator.recover_pending_transactions()
    await ewallet_orchestrator.recover_pending_transactions()
    await forex_transaction_orchestrator.recover_pending_transactions()
    await gateway_inbox.start()
    await ewallet_orchestrator.start()

    # Asynchronously run system startup diagnostic checks
    async def _run_startup_diagnostics():
        await asyncio.sleep(0.5)
        try:
            await startup_check_service.run_checks()
        except Exception as e:
            logger.error(f"Error running startup diagnostic checks: {e}")

    app.state._startup_diagnostics_task = asyncio.create_task(_run_startup_diagnostics())


    # Start forex rate service (fetches initial rates + starts periodic refresh)
    await forex_rate_service.start()

    logger.info("Coinnect backend ready")
    yield

    # Shutdown
    logger.info("Coinnect backend shutting down")
    await forex_transaction_orchestrator.stop()
    await forex_rate_service.stop()
    await gateway_inbox.stop()
    await ewallet_orchestrator.stop()
    await paymongo_client.close()
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

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        return JSONResponse(
            status_code=422,
            content={"detail": {
                "code": "VALIDATION_ERROR",
                "message": first.get("msg", "Request validation failed"),
                "transaction_id": request.path_params.get("transaction_id"),
                "state": None,
                "errors": jsonable_encoder(exc.errors()),
            }},
        )
    app.include_router(api_router)
    return app


app = create_app()
