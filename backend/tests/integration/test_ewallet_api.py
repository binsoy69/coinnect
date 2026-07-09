import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.router import api_router
from app.core.config import EWalletFeeTier, Settings
from app.models.db_models import Base
from app.services.ewallet_orchestrator import EWalletOrchestrator
from app.services.machine_status import MachineStatus
from app.services.paymongo_client import PayMongoClient, QRPaymentResult


@pytest.fixture
async def ewallet_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    settings = Settings(
        use_mock_hardware=True,
        paymongo_webhook_secret="whsec_test",
        ewallet_fee_tiers=[
            EWalletFeeTier(min=1, max=500, fee=15),
            EWalletFeeTier(min=501, max=None, fee=25),
        ],
    )
    gateway = PayMongoClient(settings)
    gateway.create_qr_payment = AsyncMock(
        return_value=QRPaymentResult(
            payment_intent_id="pi_api",
            status="awaiting_next_action",
            qr_image_url="data:image/png;base64,abc",
            test_url="https://test.paymongo.com/pi_api",
        )
    )
    gateway.get_payment_intent = AsyncMock()
    gateway.get_batch_transfer = AsyncMock()
    status = MachineStatus(settings)
    status.update_connectivity(internet_connected=True)
    status.set_dispenser_counts({"PHP_100": 10, "PHP_50": 10, "PHP_20": 10})
    status.set_coin_counts({"PHP_10": 10, "PHP_5": 10, "PHP_1": 10})
    ws = MagicMock()
    ws.broadcast = AsyncMock()
    orchestrator = EWalletOrchestrator(
        settings,
        gateway,
        MagicMock(),
        MagicMock(),
        status,
        ws,
        factory,
    )
    app = FastAPI()
    app.include_router(api_router)
    app.state.settings = settings
    app.state.paymongo_client = gateway
    app.state.ewallet_orchestrator = orchestrator
    app.state.db_session_factory = factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await engine.dispose()


@pytest.mark.asyncio
async def test_start_cashout_returns_paymongo_qr(ewallet_client):
    response = await ewallet_client.post(
        "/api/v1/ewallet/transactions",
        json={
            "provider": "gcash",
            "direction": "cash-out",
            "amount": 105,
        },
    )

    assert response.status_code == 201
    assert response.json()["qr_image_url"].startswith("data:image/png")
    assert response.json()["fee"] == 15
    assert response.json()["transfer_amount"] == 90


@pytest.mark.asyncio
async def test_cash_in_requires_mobile_number_and_account_name(ewallet_client):
    response = await ewallet_client.post(
        "/api/v1/ewallet/transactions",
        json={
            "provider": "gcash",
            "direction": "cash-in",
            "amount": 105,
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cash_out_rejects_identity_fields(ewallet_client):
    response = await ewallet_client.post(
        "/api/v1/ewallet/transactions",
        json={
            "provider": "maya",
            "direction": "cash-out",
            "amount": 105,
            "mobile_number": "09171234567",
            "account_name": "Test User",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_config_returns_backend_fee_tiers(ewallet_client):
    response = await ewallet_client.get("/api/v1/ewallet/config")

    assert response.status_code == 200
    assert response.json() == {
        "fee_tiers": [
            {"min": 1, "max": 500, "fee": 15},
            {"min": 501, "max": None, "fee": 25},
        ]
    }


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(ewallet_client):
    body = json.dumps({"data": {"id": "evt_bad"}}).encode()
    response = await ewallet_client.post(
        "/api/v1/ewallet/webhook",
        content=body,
        headers={"Paymongo-Signature": "invalid"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_accepts_valid_signature(ewallet_client):
    payload = {
        "data": {
            "id": "evt_unknown",
            "attributes": {
                "type": "payment.paid",
                "data": {
                    "id": "pay_unknown",
                    "attributes": {
                        "status": "paid",
                        "payment_intent_id": "pi_unknown",
                    },
                },
            },
        }
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = int(time.time())
    signature = hmac.new(
        b"whsec_test",
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    response = await ewallet_client.post(
        "/api/v1/ewallet/webhook",
        content=body,
        headers={
            "Paymongo-Signature": f"t={timestamp},te={signature},li="
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_webhook_accepts_transfer_successful(ewallet_client):
    payload = {
        "data": {
            "id": "evt_transfer_success",
            "attributes": {
                "type": "transfer.outward.successful",
                "data": {
                    "id": "tr_success",
                    "attributes": {
                        "status": "succeeded",
                        "reference_number": "tx_success",
                    },
                },
            },
        }
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = int(time.time())
    signature = hmac.new(
        b"whsec_test",
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    response = await ewallet_client.post(
        "/api/v1/ewallet/webhook",
        content=body,
        headers={
            "Paymongo-Signature": f"t={timestamp},te={signature},li="
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_webhook_accepts_transfer_failed(ewallet_client):
    payload = {
        "data": {
            "id": "evt_transfer_fail",
            "attributes": {
                "type": "transfer.outward.failed",
                "data": {
                    "id": "tr_failed",
                    "attributes": {
                        "status": "failed",
                        "reference_number": "tx_failed",
                    },
                },
            },
        }
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = int(time.time())
    signature = hmac.new(
        b"whsec_test",
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    response = await ewallet_client.post(
        "/api/v1/ewallet/webhook",
        content=body,
        headers={
            "Paymongo-Signature": f"t={timestamp},te={signature},li="
        },
    )
    assert response.status_code == 200
