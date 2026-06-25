"""FastAPI app for the Coinnect health check maintenance program."""

from contextlib import asynccontextmanager
import json
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
from app.services.paymongo_client import PayMongoClient

from healthcheck_api.auth import AuthManager
from healthcheck_api.dependencies import require_auth
from healthcheck_api.ewallet_sandbox import (
    EWalletSandboxConfig,
    EWalletSandboxService,
    SandboxConfigurationError,
    create_sandbox_database,
)
from healthcheck_api.hardware import create_hardware_context
from healthcheck_api.models import (
    ComponentGroup,
    EWalletSandboxSessionCreate,
    HealthcheckStatus,
    LoginRequest,
    LoginResponse,
    TestRunResult,
)
from healthcheck_api.runner import DiagnosticsBusyError, DiagnosticsRunner

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_CORS_ORIGINS = [
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:4174",
    "http://127.0.0.1:4174",
]
DEFAULT_CORS_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost|"
    r"127\.0\.0\.1|"
    r"10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}|"
    r"169\.254(?:\.\d{1,3}){2}|"
    r"[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.local"
    r"):(?:5174|4174)$"
)


def healthcheck_env_file() -> Path:
    return Path(os.environ.get("HEALTHCHECK_ENV_FILE", DEFAULT_ENV_FILE))


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def healthcheck_cors_origins() -> list[str]:
    return (
        parse_csv(os.environ.get("HEALTHCHECK_CORS_ORIGINS"))
        or parse_csv(os.environ.get("CORS_ORIGINS"))
        or DEFAULT_CORS_ORIGINS
    )


def healthcheck_cors_origin_regex() -> str | None:
    value = os.environ.get("HEALTHCHECK_CORS_ORIGIN_REGEX")
    if value is None:
        return DEFAULT_CORS_ORIGIN_REGEX
    return value.strip() or None


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(dotenv_path=healthcheck_env_file())
    auth_manager = AuthManager()
    settings = Settings(_env_file=None)
    setup_logging(settings.log_level)

    hardware = await create_hardware_context(settings)
    runner = DiagnosticsRunner(hardware)
    sandbox_config = EWalletSandboxConfig.from_environment()
    sandbox_engine, sandbox_factory = await create_sandbox_database(
        sandbox_config.database_url
    )
    paymongo_client = PayMongoClient(settings)
    sandbox_service = EWalletSandboxService(
        settings,
        paymongo_client,
        sandbox_factory,
        sandbox_config,
    )
    await sandbox_service.start()

    app.state.auth_manager = auth_manager
    app.state.settings = settings
    app.state.hardware = hardware
    app.state.diagnostics_runner = runner
    app.state.paymongo_client = paymongo_client
    app.state.ewallet_sandbox_service = sandbox_service
    app.state.ewallet_sandbox_engine = sandbox_engine

    try:
        yield
    finally:
        await sandbox_service.stop()
        await paymongo_client.close()
        await sandbox_engine.dispose()
        await hardware.shutdown()


def create_app() -> FastAPI:
    load_dotenv(dotenv_path=healthcheck_env_file())
    app = FastAPI(
        title="Coinnect Health Check",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=healthcheck_cors_origins(),
        allow_origin_regex=healthcheck_cors_origin_regex(),
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
            printer=hardware.printer_snapshot,
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

    @app.get(
        "/api/v1/ewallet-sandbox/config",
        dependencies=[Depends(require_auth)],
    )
    async def ewallet_sandbox_config(request: Request):
        service: EWalletSandboxService = (
            request.app.state.ewallet_sandbox_service
        )
        return service.config_status

    @app.post(
        "/api/v1/ewallet-sandbox/sessions",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_auth)],
    )
    async def create_ewallet_sandbox_session(
        payload: EWalletSandboxSessionCreate,
        request: Request,
    ):
        service: EWalletSandboxService = (
            request.app.state.ewallet_sandbox_service
        )
        try:
            return await service.create_session(payload)
        except SandboxConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

    @app.get(
        "/api/v1/ewallet-sandbox/sessions",
        dependencies=[Depends(require_auth)],
    )
    async def list_ewallet_sandbox_sessions(request: Request):
        service: EWalletSandboxService = (
            request.app.state.ewallet_sandbox_service
        )
        return await service.list_sessions()

    @app.get(
        "/api/v1/ewallet-sandbox/sessions/{session_id}",
        dependencies=[Depends(require_auth)],
    )
    async def get_ewallet_sandbox_session(
        session_id: str,
        request: Request,
    ):
        service: EWalletSandboxService = (
            request.app.state.ewallet_sandbox_service
        )
        try:
            return await service.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="E-wallet sandbox session not found",
            ) from exc

    @app.post(
        "/api/v1/ewallet-sandbox/sessions/{session_id}/cancel",
        dependencies=[Depends(require_auth)],
    )
    async def cancel_ewallet_sandbox_session(
        session_id: str,
        request: Request,
    ):
        service: EWalletSandboxService = (
            request.app.state.ewallet_sandbox_service
        )
        try:
            return await service.cancel_session(session_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="E-wallet sandbox session not found",
            ) from exc

    @app.post(
        "/api/v1/ewallet-sandbox/callbacks/payment",
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def ewallet_sandbox_payment_callback(request: Request):
        raw_body = await request.body()
        signature = request.headers.get(
            "Paymongo-Signature"
        ) or request.headers.get("X-Paymongo-Signature")
        gateway: PayMongoClient = request.app.state.paymongo_client
        if not gateway.verify_webhook_signature(raw_body, signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )
        try:
            payload = json.loads(raw_body)
            event = _normalize_gateway_event(payload)
            service: EWalletSandboxService = (
                request.app.state.ewallet_sandbox_service
            )
            await service.process_payment_event(event)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return {"accepted": True}

    @app.post(
        "/api/v1/ewallet-sandbox/callbacks/transfer",
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def ewallet_sandbox_transfer_callback(request: Request):
        payload = await request.json()
        batch_transfer_id = _extract_batch_transfer_id(payload)
        if not batch_transfer_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing batch_transfer_id",
            )
        service: EWalletSandboxService = (
            request.app.state.ewallet_sandbox_service
        )
        await service.process_transfer_callback(batch_transfer_id)
        return {"accepted": True}


def _normalize_gateway_event(payload: dict) -> dict:
    data = payload.get("data", payload)
    attrs = data.get("attributes") or {}
    nested = attrs.get("data") or {}
    nested_attrs = nested.get("attributes") or {}
    event_type = attrs.get("type") or data.get("type")
    if not event_type:
        raise ValueError("Missing PayMongo event type")
    resource_id = nested.get("id") or data.get("id")
    payment_id = None
    if str(event_type).startswith("payment."):
        payment_id = nested.get("id")
        resource_id = nested_attrs.get("payment_intent_id")
    return {
        "id": str(data.get("id") or payload.get("id")),
        "type": str(event_type),
        "resource_id": resource_id,
        "payment_id": payment_id,
    }


def _extract_batch_transfer_id(payload: dict) -> str | None:
    candidates = [
        payload.get("batch_transfer_id"),
        payload.get("data", {}).get("batch_transfer_id"),
        payload.get("data", {}).get("attributes", {}).get(
            "batch_transfer_id"
        ),
    ]
    data_id = payload.get("data", {}).get("id")
    if isinstance(data_id, str) and data_id.startswith(
        ("batch_tr_", "btr_")
    ):
        candidates.append(data_id)
    return next(
        (str(candidate) for candidate in candidates if candidate),
        None,
    )


app = create_app()
