"""Kiosk and PayMongo e-wallet APIs."""

from __future__ import annotations

from typing import Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Request,
    status,
)
from pydantic import BaseModel, Field, model_validator

router = APIRouter(prefix="/ewallet", tags=["e-wallet"])


class StartEWalletRequest(BaseModel):
    provider: Literal["gcash", "maya"]
    direction: Literal["cash-in", "cash-out"]
    mobile_number: str | None = Field(
        default=None,
        pattern=r"^09\d{9}$",
    )
    account_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
    )
    amount: int = Field(gt=0, le=50_000)

    @model_validator(mode="after")
    def validate_identity_fields(self):
        has_mobile = self.mobile_number is not None
        has_name = self.account_name is not None
        if self.direction == "cash-in" and not (has_mobile and has_name):
            raise ValueError(
                "Cash-in requires mobile_number and account_name"
            )
        if self.direction == "cash-out" and (has_mobile or has_name):
            raise ValueError(
                "Cash-out does not accept mobile_number or account_name"
            )
        return self


class SimulateCashRequest(BaseModel):
    denomination: int


@router.get("/config")
async def ewallet_config(request: Request):
    return {
        "fee_tiers": [
            tier.model_dump()
            for tier in request.app.state.settings.ewallet_fee_tiers
        ]
    }


@router.post("/transactions", status_code=status.HTTP_201_CREATED)
async def start_transaction(body: StartEWalletRequest, request: Request):
    money_changer = getattr(
        request.app.state, "transaction_orchestrator", None
    )
    if money_changer is not None and money_changer.has_active_transaction:
        raise HTTPException(
            status_code=409, detail="Another kiosk transaction is active"
        )
    try:
        return await request.app.state.ewallet_orchestrator.start_transaction(
            **body.model_dump()
        )
    except Exception as exc:
        response_status = (
            423 if "maintenance mode" in str(exc).lower() else 400
        )
        raise HTTPException(
            status_code=response_status, detail=str(exc)
        ) from exc


@router.get("/transactions/{transaction_id}")
async def get_transaction(transaction_id: str, request: Request):
    try:
        return await request.app.state.ewallet_orchestrator.get_transaction(
            transaction_id
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/transactions/{transaction_id}/accept-bill")
async def accept_bill(transaction_id: str, request: Request):
    try:
        return await request.app.state.ewallet_orchestrator.accept_bill(
            transaction_id
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/transactions/{transaction_id}/simulate-insert")
async def simulate_insert(
    transaction_id: str, body: SimulateCashRequest, request: Request
):
    if not request.app.state.settings.use_mock_hardware:
        raise HTTPException(status_code=403, detail="Mock hardware is disabled")
    try:
        return await request.app.state.ewallet_orchestrator.record_cash_insert(
            transaction_id, body.denomination
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/transactions/{transaction_id}/confirm")
async def confirm_transaction(transaction_id: str, request: Request):
    try:
        transaction = await request.app.state.ewallet_orchestrator.get_transaction(
            transaction_id
        )
        if transaction["direction"] != "cash-in":
            return transaction
        return await request.app.state.ewallet_orchestrator.confirm_cash_in(
            transaction_id
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/transactions/{transaction_id}")
async def cancel_transaction(transaction_id: str, request: Request):
    try:
        return await request.app.state.ewallet_orchestrator.cancel_transaction(
            transaction_id
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/webhook")
async def paymongo_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    signature = request.headers.get("Paymongo-Signature") or request.headers.get(
        "X-Paymongo-Signature"
    )
    gateway = request.app.state.paymongo_client
    if not gateway.verify_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = __import__("json").loads(raw_body)
        event = _normalize_gateway_event(payload)
        background_tasks.add_task(
            request.app.state.ewallet_orchestrator.process_gateway_event,
            event,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"accepted": True}


@router.post("/transfer-callback", status_code=status.HTTP_202_ACCEPTED)
async def transfer_callback(
    request: Request,
    background_tasks: BackgroundTasks,
):
    payload = await request.json()
    batch_transfer_id = _extract_batch_transfer_id(payload)
    if not batch_transfer_id:
        raise HTTPException(
            status_code=422,
            detail="Missing batch_transfer_id",
        )
    background_tasks.add_task(
        request.app.state.ewallet_orchestrator.process_transfer_callback,
        batch_transfer_id,
    )
    return {"accepted": True}


def _normalize_gateway_event(payload: dict) -> dict:
    data = payload.get("data", payload)
    attrs = data.get("attributes", {})
    nested = attrs.get("data") or {}
    nested_attrs = nested.get("attributes") or {}
    event_type = attrs.get("type") or data.get("type") or "transfer.updated"
    resource_id = nested.get("id") or data.get("id")
    payment_id = None
    if event_type.startswith("payment."):
        payment_id = nested.get("id")
        resource_id = nested_attrs.get("payment_intent_id")
    status_value = (
        nested_attrs.get("status")
        or data.get("status")
        or attrs.get("status")
        or (
            "succeeded"
            if event_type in {"payment.paid", "payment_intent.succeeded"}
            else None
        )
    )
    return {
        "id": str(
            data.get("id")
            or payload.get("id")
            or __import__("uuid").uuid4()
        ),
        "type": str(event_type),
        "resource_id": resource_id,
        "payment_id": payment_id,
        "status": status_value,
        "payload": payload,
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
    if isinstance(data_id, str) and data_id.startswith("batch_tr_"):
        candidates.append(data_id)
    return next(
        (
            str(candidate)
            for candidate in candidates
            if candidate
        ),
        None,
    )
