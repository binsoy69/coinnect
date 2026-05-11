"""FastAPI app for the Coinnect health check maintenance program."""

from contextlib import asynccontextmanager
import os
from pathlib import Path
import sys

SHARED_BACKEND_PATH = Path(__file__).resolve().parents[3] / "backend"
if str(SHARED_BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(SHARED_BACKEND_PATH))

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.core.config import Settings
from app.core.logging import setup_logging

from healthcheck_api.auth import AuthManager
from healthcheck_api.dependencies import require_auth
from healthcheck_api.hardware import create_hardware_context
from healthcheck_api.models import (
    ComponentGroup,
    HealthcheckStatus,
    LoginRequest,
    LoginResponse,
    TestRunResult,
)
from healthcheck_api.runner import DiagnosticsBusyError, DiagnosticsRunner

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def healthcheck_env_file() -> Path:
    return Path(os.environ.get("HEALTHCHECK_ENV_FILE", DEFAULT_ENV_FILE))


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(dotenv_path=healthcheck_env_file())
    auth_manager = AuthManager()
    settings = Settings(_env_file=None)
    setup_logging(settings.log_level)

    hardware = await create_hardware_context(settings)
    runner = DiagnosticsRunner(hardware)

    app.state.auth_manager = auth_manager
    app.state.settings = settings
    app.state.hardware = hardware
    app.state.diagnostics_runner = runner

    try:
        yield
    finally:
        await hardware.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Coinnect Health Check",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5174", "http://localhost:4174"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_routes(app)
    return app


def register_routes(app: FastAPI) -> None:
    @app.post("/api/v1/auth/login", response_model=LoginResponse)
    async def login(payload: LoginRequest, request: Request):
        token = request.app.state.auth_manager.login(payload.pin)
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid PIN",
            )
        return LoginResponse(token=token)

    @app.get(
        "/api/v1/components",
        response_model=list[ComponentGroup],
        dependencies=[Depends(require_auth)],
    )
    async def components(request: Request):
        runner: DiagnosticsRunner = request.app.state.diagnostics_runner
        return runner.component_groups

    @app.get(
        "/api/v1/status",
        response_model=HealthcheckStatus,
        dependencies=[Depends(require_auth)],
    )
    async def healthcheck_status(request: Request):
        hardware = request.app.state.hardware
        runner: DiagnosticsRunner = request.app.state.diagnostics_runner
        return HealthcheckStatus(
            serial=hardware.serial_snapshot,
            gpio=hardware.gpio_snapshot,
            camera=hardware.camera_snapshot,
            busy=runner.busy,
            recent_run_count=len(runner.recent_runs),
        )

    @app.post(
        "/api/v1/tests/{test_id}/run",
        response_model=TestRunResult,
        dependencies=[Depends(require_auth)],
    )
    async def run_test(test_id: str, request: Request):
        runner: DiagnosticsRunner = request.app.state.diagnostics_runner
        try:
            return await runner.run(test_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown test")
        except DiagnosticsBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @app.get(
        "/api/v1/runs/recent",
        response_model=list[TestRunResult],
        dependencies=[Depends(require_auth)],
    )
    async def recent_runs(request: Request):
        runner: DiagnosticsRunner = request.app.state.diagnostics_runner
        return runner.recent_runs


app = create_app()
