"""Async PayMongo API client for QR Ph acceptance and wallet transfers."""

from __future__ import annotations

import base64
import asyncio
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import PaymentGatewayError


PROVIDER_BICS = {
    "gcash": "GXCHPHM2XXX",
    "maya": "PAPHPHM1XXX",
}


@dataclass(frozen=True)
class QRPaymentResult:
    payment_intent_id: str
    status: str
    qr_image_url: str
    test_url: str | None = None


@dataclass(frozen=True)
class DisbursementResult:
    batch_transfer_id: str
    transfer_id: str
    status: str


class PayMongoClient:
    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ):
        self._settings = settings
        self._http = http_client
        self._owns_http = http_client is None

    def verify_webhook_signature(
        self, raw_body: bytes, signature: str | None
    ) -> bool:
        if not signature or not self._settings.paymongo_webhook_secret:
            return False
        try:
            parts = dict(
                item.strip().split("=", 1)
                for item in signature.split(",")
                if "=" in item
            )
            timestamp = int(parts["t"])
        except (KeyError, TypeError, ValueError):
            return False
        if abs(int(time.time()) - timestamp) > (
            self._settings.paymongo_webhook_tolerance_seconds
        ):
            return False
        signature_key = "te" if self._settings.paymongo_sandbox else "li"
        provided = parts.get(signature_key, "")
        if not provided:
            return False
        expected = hmac.new(
            self._settings.paymongo_webhook_secret.encode(),
            f"{timestamp}.".encode() + raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, provided)

    async def create_qr_payment(
        self,
        *,
        amount_centavos: int,
        reference: str,
        idempotency_key: str,
        checkpoint=None,
    ) -> QRPaymentResult:
        intent = await self._request(
            "POST",
            "/v1/payment_intents",
            secret=True,
            idempotency_key=f"{idempotency_key}:intent",
            json={
                "data": {
                    "attributes": {
                        "amount": amount_centavos,
                        "currency": "PHP",
                        "payment_method_allowed": ["qrph"],
                        "description": f"Coinnect cash-out {reference}",
                        "metadata": {"coinnect_transaction_id": reference},
                    }
                }
            },
        )
        intent_data = intent["data"]
        intent_id = intent_data["id"]
        if checkpoint:
            await checkpoint("intent", {"id": intent_id})
        client_key = intent_data["attributes"]["client_key"]

        method = await self._request(
            "POST",
            "/v1/payment_methods",
            secret=False,
            idempotency_key=f"{idempotency_key}:method",
            json={"data": {"attributes": {"type": "qrph"}}},
        )
        method_id = method["data"]["id"]
        if checkpoint:
            await checkpoint("method", {"id": method_id})

        attached = await self._request(
            "POST",
            f"/v1/payment_intents/{intent_id}/attach",
            secret=False,
            idempotency_key=f"{idempotency_key}:attach",
            json={
                "data": {
                    "attributes": {
                        "payment_method": method_id,
                        "client_key": client_key,
                    }
                }
            },
        )
        attrs = attached["data"]["attributes"]
        next_action = attrs.get("next_action") or {}
        code = next_action.get("code") or {}
        qr_image_url = code.get("image_url")
        if not qr_image_url:
            raise PaymentGatewayError("PayMongo did not return a QR image")
        return QRPaymentResult(
            payment_intent_id=intent_id,
            status=attrs.get("status", "awaiting_next_action"),
            qr_image_url=qr_image_url,
            test_url=(
                next_action.get("test_url")
                or code.get("test_url")
                or attrs.get("test_url")
            ),
        )

    async def get_payment_intent(self, payment_intent_id: str) -> dict:
        response = await self._request(
            "GET",
            f"/v1/payment_intents/{payment_intent_id}",
            secret=True,
        )
        return response["data"]

    async def cancel_payment_intent(self, payment_intent_id: str) -> dict:
        response = await self._request(
            "POST",
            f"/v1/payment_intents/{payment_intent_id}/cancel",
            secret=True,
        )
        return response["data"]

    async def create_disbursement(
        self,
        *,
        provider: str,
        account_number: str,
        account_name: str,
        amount_centavos: int,
        reference: str,
        idempotency_key: str,
        callback_url: str | None = None,
    ) -> DisbursementResult:
        bic = PROVIDER_BICS.get(provider)
        if not bic:
            raise PaymentGatewayError(f"Unsupported wallet provider: {provider}")
        transfer_data = {
            "provider": "instapay",
            "amount": amount_centavos,
            "currency": "PHP",
            "purpose": "Disbursement",
            "description": f"Coinnect cash-in {reference}",
            "reference_number": reference,
            "source_account": {
                "number": self._settings.paymongo_source_account_number,
                "name": self._settings.paymongo_source_account_name,
                "bic": self._settings.paymongo_source_account_bic,
            },
            "destination_account": {
                "number": account_number,
                "name": account_name,
                "bic": bic,
            },
            "metadata": {"coinnect_transaction_id": reference},
        }
        if callback_url:
            transfer_data["callback_url"] = callback_url

        payload = {
            "transfers": [transfer_data]
        }
        response = await self._request(
            "POST",
            "/v2/batch_transfers",
            secret=True,
            idempotency_key=idempotency_key,
            json=payload,
        )
        data = response["data"]
        transfer = data["transfers"][0]
        return DisbursementResult(
            batch_transfer_id=data["id"],
            transfer_id=transfer["id"],
            status=transfer.get("status", "pending"),
        )

    async def get_batch_transfer(self, batch_transfer_id: str) -> dict:
        response = await self._request(
            "GET",
            f"/v2/batch_transfers/{batch_transfer_id}",
            secret=True,
        )
        data = response["data"]
        attrs = data.get("attributes") or {}
        if "transfers" not in data and "transfers" in attrs:
            data = {**data, "transfers": attrs["transfers"]}
        return data

    async def find_transfer(self, reference: str):
        from urllib.parse import urlencode
        response = await self._request("GET", "/v2/transfers?" + urlencode({"reference_number": reference}), secret=True)
        data = response.get("data") or []
        rows = data if isinstance(data, list) else data.get("transfers", [])
        matches = [row for row in rows if (row.get("attributes") or row).get("reference_number") == reference]
        if len(matches) > 1:
            raise PaymentGatewayError("Multiple transfers match the reference; manual reconciliation required")
        return matches[0] if matches else None

    async def close(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        secret: bool,
        idempotency_key: str | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self._settings.paymongo_api_url,
                timeout=self._settings.paymongo_timeout_seconds,
            )
        key = (
            self._settings.paymongo_secret_key
            if secret
            else self._settings.paymongo_public_key
        )
        if not key:
            raise PaymentGatewayError(
                "PayMongo API key is not configured",
                "PAYMONGO_NOT_CONFIGURED",
            )
        auth = base64.b64encode(f"{key}:".encode()).decode()
        attempts = max(1, self._settings.paymongo_max_retries)
        for attempt in range(attempts):
            try:
                headers = {
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/json",
                }
                if idempotency_key:
                    headers["Idempotency-Key"] = idempotency_key
                response = await self._http.request(
                    method,
                    path,
                    headers=headers,
                    json=json,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                retryable = (
                    exc.response.status_code in {409, 429}
                    or exc.response.status_code >= 500
                )
                if retryable and attempt < attempts - 1:
                    await asyncio.sleep(0.25 * (2**attempt))
                    continue
                detail = exc.response.text[:500]
                raise PaymentGatewayError(
                    f"PayMongo returned HTTP "
                    f"{exc.response.status_code}: {detail}"
                ) from exc
            except httpx.HTTPError as exc:
                if attempt < attempts - 1:
                    await asyncio.sleep(0.25 * (2**attempt))
                    continue
                raise PaymentGatewayError(
                    f"PayMongo request failed: {exc}"
                ) from exc
        raise PaymentGatewayError("PayMongo request failed after retries")
