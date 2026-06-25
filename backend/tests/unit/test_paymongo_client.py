import hashlib
import hmac
import json
import time

import httpx
import pytest

from app.core.config import Settings
from app.services.paymongo_client import PayMongoClient


@pytest.fixture
def settings():
    return Settings(
        paymongo_secret_key="sk_test_example",
        paymongo_public_key="pk_test_example",
        paymongo_webhook_secret="whsec_example",
        paymongo_source_account_number="0000000001",
        paymongo_source_account_name="Coinnect",
        paymongo_source_account_bic="PAEYPHM2XXX",
        paymongo_transfer_callback_url=(
            "https://example.test/api/v1/ewallet/transfer-callback"
        ),
    )


def _signature_header(
    secret: str,
    body: bytes,
    *,
    timestamp: int | None = None,
    live: bool = False,
) -> str:
    timestamp = timestamp or int(time.time())
    signed_payload = f"{timestamp}.".encode() + body
    signature = hmac.new(
        secret.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    return (
        f"t={timestamp},te=,li={signature}"
        if live
        else f"t={timestamp},te={signature},li="
    )


def test_verify_webhook_signature_uses_paymongo_test_header(settings):
    client = PayMongoClient(settings)
    body = b'{"data":{"id":"evt_1"}}'
    signature = _signature_header("whsec_example", body)

    assert client.verify_webhook_signature(body, signature)
    assert not client.verify_webhook_signature(body + b" ", signature)


def test_verify_webhook_signature_uses_live_signature():
    settings = Settings(
        paymongo_webhook_secret="whsec_live",
        paymongo_sandbox=False,
    )
    client = PayMongoClient(settings)
    body = b'{"data":{"id":"evt_live"}}'

    assert client.verify_webhook_signature(
        body,
        _signature_header("whsec_live", body, live=True),
    )


def test_verify_webhook_signature_rejects_stale_or_malformed_header(settings):
    client = PayMongoClient(settings)
    body = b'{"data":{"id":"evt_1"}}'

    assert not client.verify_webhook_signature(
        body,
        _signature_header(
            "whsec_example",
            body,
            timestamp=int(time.time()) - 301,
        ),
    )
    assert not client.verify_webhook_signature(body, "not-a-signature")


@pytest.mark.asyncio
async def test_create_qr_payment_returns_gateway_fields(settings):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/payment_intents":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "pi_1",
                        "attributes": {"client_key": "pi_1_client"},
                    }
                },
            )
        if request.url.path == "/v1/payment_methods":
            return httpx.Response(200, json={"data": {"id": "pm_1"}})
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "pi_1",
                    "attributes": {
                        "status": "awaiting_next_action",
                        "next_action": {
                            "code": {"image_url": "data:image/png;base64,abc"},
                            "test_url": "https://test.paymongo.com/pi_1",
                        },
                    },
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.paymongo.com",
    ) as http:
        client = PayMongoClient(settings, http_client=http)
        result = await client.create_qr_payment(
            amount_centavos=10_500,
            reference="wallet-tx-1",
            idempotency_key="wallet-tx-1:qr",
        )

    assert result.payment_intent_id == "pi_1"
    assert result.qr_image_url.startswith("data:image/png")
    assert result.test_url == "https://test.paymongo.com/pi_1"
    assert requests[0].headers["Idempotency-Key"] == "wallet-tx-1:qr:intent"


@pytest.mark.asyncio
async def test_get_payment_intent_returns_attributes(settings):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/payment_intents/pi_1"
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "pi_1",
                    "attributes": {
                        "amount": 10_500,
                        "currency": "PHP",
                        "status": "succeeded",
                        "metadata": {
                            "coinnect_transaction_id": "wallet-tx-1"
                        },
                        "payments": [
                            {
                                "id": "pay_1",
                                "attributes": {
                                    "amount": 10_500,
                                    "currency": "PHP",
                                    "status": "paid",
                                    "source": {"type": "qrph"},
                                },
                            }
                        ],
                    },
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.paymongo.com",
    ) as http:
        client = PayMongoClient(settings, http_client=http)
        result = await client.get_payment_intent("pi_1")

    assert result["id"] == "pi_1"
    assert result["attributes"]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_create_disbursement_maps_gcash_to_instapay(settings):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "btr_1",
                    "transfers": [
                        {"id": "tr_1", "status": "pending"}
                    ],
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.paymongo.com",
    ) as http:
        client = PayMongoClient(settings, http_client=http)
        result = await client.create_disbursement(
            provider="gcash",
            account_number="09171234567",
            account_name="Test User",
            amount_centavos=9_000,
            reference="wallet-tx-1",
            idempotency_key="wallet-tx-1:transfer",
        )

    payload = __import__("json").loads(captured["request"].content)
    destination = payload["transfers"][0]["destination_account"]
    assert destination["bic"] == "GXCHPHM2XXX"
    assert result.transfer_id == "tr_1"
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_create_disbursement_accepts_callback_url_override(settings):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "btr_1",
                    "transfers": [{"id": "tr_1", "status": "pending"}],
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.paymongo.com",
    ) as http:
        client = PayMongoClient(settings, http_client=http)
        await client.create_disbursement(
            provider="maya",
            account_number="09181234567",
            account_name="Sandbox User",
            amount_centavos=10_000,
            reference="sandbox-session-1",
            idempotency_key="healthcheck:sandbox-session-1:transfer",
            callback_url=(
                "https://healthcheck.example.com/api/v1/"
                "ewallet-sandbox/callbacks/transfer"
            ),
        )

    payload = __import__("json").loads(captured["request"].content)
    assert payload["transfers"][0]["callback_url"] == (
        "https://healthcheck.example.com/api/v1/"
        "ewallet-sandbox/callbacks/transfer"
    )


@pytest.mark.asyncio
async def test_get_batch_transfer_returns_requested_transfer(settings):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v2/batch_transfers/btr_1"
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "btr_1",
                    "transfers": [
                        {
                            "id": "tr_1",
                            "status": "succeeded",
                            "reference_number": "wallet-tx-1",
                        }
                    ],
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.paymongo.com",
    ) as http:
        client = PayMongoClient(settings, http_client=http)
        result = await client.get_batch_transfer("btr_1")

    assert result["id"] == "btr_1"
    assert result["transfers"][0]["reference_number"] == "wallet-tx-1"


@pytest.mark.asyncio
async def test_retries_transient_paymongo_failure(settings):
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, text="temporary")
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "btr_2",
                    "transfers": [{"id": "tr_2", "status": "pending"}],
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.paymongo.com",
    ) as http:
        client = PayMongoClient(settings, http_client=http)
        result = await client.create_disbursement(
            provider="maya",
            account_number="09181234567",
            account_name="Test User",
            amount_centavos=10_000,
            reference="wallet-tx-2",
            idempotency_key="wallet-tx-2:transfer",
        )

    assert result.transfer_id == "tr_2"
    assert attempts == 2
