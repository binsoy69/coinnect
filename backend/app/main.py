import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.ws import ConnectionManager
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.drivers.serial_manager import SerialManager
from app.services.event_dispatcher import EventDispatcher
from app.services.machine_status import MachineStatus

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info(
        f"Coinnect backend starting "
        f"(env={settings.environment}, mock={settings.use_mock_serial})"
    )

    # Create shared instances
    serial_manager = SerialManager(settings)
    ws_manager = ConnectionManager()
    machine_status = MachineStatus(settings)
    event_dispatcher = EventDispatcher(
        serial_manager.event_queue, machine_status, ws_manager
    )

    # Store on app state for dependency injection in endpoints
    app.state.serial_manager = serial_manager
    app.state.ws_manager = ws_manager
    app.state.machine_status = machine_status
    app.state.event_dispatcher = event_dispatcher
    app.state.settings = settings

    # Startup
    await serial_manager.startup()
    await event_dispatcher.start()

    logger.info("Coinnect backend ready")
    yield

    # Shutdown
    logger.info("Coinnect backend shutting down")
    await event_dispatcher.stop()
    await serial_manager.shutdown()


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
