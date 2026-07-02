import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock

from app.services.paymongo_client import DisbursementResult, QRPaymentResult


def install_gateway(app):
    gateway = AsyncMock()
    gateway.create_qr_payment.return_value = QRPaymentResult(
        payment_intent_id="pi_api_1",
        status="awaiting_next_action",
        qr_image_url="https://sandbox.example/qr.png",
        test_url="https://sandbox.example/pay",
    )
    gateway.create_disbursement.return_value = DisbursementResult(
        batch_transfer_id="batch_tr_api_1",
        transfer_id="tr_api_1",
        status="pending",
    )
    gateway.verify_webhook_signature = (
        app.state.paymongo_client.verify_webhook_signature
    )
    app.state.paymongo_client = gateway
    app.state.ewallet_sandbox_service._gateway = gateway
    return gateway


async def test_config_requires_auth_and_reports_callback_urls(app_client):
    _app, client = app_client

    unauthorized = await client.get("/api/v1/ewallet-sandbox/config")
    assert unauthorized.status_code == 401

    login = await client.post(
        "/api/v1/auth/login", json={"pin": "123456"}
    )
    token = login.json()["token"]
    configured = await client.get(
        "/api/v1/ewallet-sandbox/config",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert configured.status_code == 200
    assert configured.json()["ready"] is True
    assert configured.json()["payment_callback_url"].endswith(
        "/callbacks/payment"
    )


async def test_authenticated_cash_out_session_lifecycle(authed_client):
    app, client = authed_client
    install_gateway(app)

    created = await client.post(
        "/api/v1/ewallet-sandbox/sessions",
        json={
            "provider": "gcash",
            "direction": "cash-out",
            "amount": 100,
        },
    )

    assert created.status_code == 201
    session = created.json()
    assert session["state"] == "PENDING_CALLBACK"
    detail = await client.get(
        f"/api/v1/ewallet-sandbox/sessions/{session['transaction_id']}"
    )
    assert detail.status_code == 200
    history = await client.get("/api/v1/ewallet-sandbox/sessions")
    assert history.json()[0]["transaction_id"] == session["transaction_id"]

    cancelled = await client.post(
        f"/api/v1/ewallet-sandbox/sessions/"
        f"{session['transaction_id']}/cancel"
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "CANCELLED"


async def test_unconfigured_session_creation_returns_503(authed_client):
    app, client = authed_client
    app.state.ewallet_sandbox_service._config.public_base_url = ""

    response = await client.post(
        "/api/v1/ewallet-sandbox/sessions",
        json={
            "provider": "maya",
            "direction": "cash-out",
            "amount": 100,
        },
    )

    assert response.status_code == 503
    assert "HEALTHCHECK_PUBLIC_BASE_URL" in response.json()["detail"]


async def test_payment_callback_is_public_and_signature_verified(app_client):
    app, client = app_client
    gateway = install_gateway(app)
    login = await client.post(
        "/api/v1/auth/login", json={"pin": "123456"}
    )
    token = login.json()["token"]
    created = await client.post(
        "/api/v1/ewallet-sandbox/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "maya",
            "direction": "cash-out",
            "amount": 100,
        },
    )
    session = created.json()
    gateway.get_payment_intent.return_value = {
        "id": session["gateway_payment_intent_id"],
        "attributes": {
            "amount": 10_000,
            "currency": "PHP",
            "status": "succeeded",
            "metadata": {
                "coinnect_transaction_id": session["transaction_id"]
            },
            "payments": [
                {
                    "id": "pay_api_1",
                    "attributes": {
                        "amount": 10_000,
                        "currency": "PHP",
                        "status": "paid",
                        "source": {"type": "qrph"},
                    },
                }
            ],
        },
    }
    payload = {
        "data": {
            "id": "evt_api_1",
            "attributes": {
                "type": "payment.paid",
                "data": {
                    "id": "pay_api_1",
                    "attributes": {
                        "payment_intent_id": (
                            session["gateway_payment_intent_id"]
                        ),
                        "status": "paid",
                    },
                },
            },
        }
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = int(time.time())
    digest = hmac.new(
        b"whsec_healthcheck",
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()

    invalid = await client.post(
        "/api/v1/ewallet-sandbox/callbacks/payment",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    valid = await client.post(
        "/api/v1/ewallet-sandbox/callbacks/payment",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Paymongo-Signature": f"t={timestamp},te={digest}",
        },
    )

    assert invalid.status_code == 401
    assert valid.status_code == 202
    assert valid.json()["accepted"] is True


async def test_transfer_webhook_is_public_and_signature_verified(app_client):
    app, client = app_client
    gateway = install_gateway(app)
    login = await client.post(
        "/api/v1/auth/login", json={"pin": "123456"}
    )
    token = login.json()["token"]
    created = await client.post(
        "/api/v1/ewallet-sandbox/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "gcash",
            "direction": "cash-in",
            "amount": 100,
            "mobile_number": "09171234567",
            "account_name": "Sandbox User",
        },
    )
    session = created.json()
    gateway.get_batch_transfer.return_value = {
        "id": session["gateway_batch_transfer_id"],
        "transfers": [
            {
                "id": session["gateway_transfer_id"],
                "status": "succeeded",
                "reference_number": session["transaction_id"],
                "amount": session["amount"] * 100,
                "currency": "PHP",
            }
        ],
    }
    payload = {
        "data": {
            "id": "evt_api_transfer_1",
            "attributes": {
                "type": "transfer.outward.successful",
                "data": {
                    "id": session["gateway_transfer_id"],
                    "attributes": {
                        "status": "succeeded",
                    },
                },
            },
        }
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = int(time.time())
    digest = hmac.new(
        b"whsec_healthcheck",
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()

    invalid = await client.post(
        "/api/v1/ewallet-sandbox/callbacks/payment",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    valid = await client.post(
        "/api/v1/ewallet-sandbox/callbacks/payment",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Paymongo-Signature": f"t={timestamp},te={digest}",
        },
    )

    assert invalid.status_code == 401
    assert valid.status_code == 202
    assert valid.json()["accepted"] is True
