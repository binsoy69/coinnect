"""Kiosk and PayMongo e-wallet APIs."""

from __future__ import annotations

from typing import Literal
from datetime import datetime, timedelta
import secrets
import hashlib
from sqlalchemy import select
from app.api.kiosk_access import wallet_access
from app.models.db_models import KioskSession, EWalletTransactionRecord
from app.services.ewallet_policy import POLICY_VERSION, TERMINAL

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    status,
    Depends,
)
from pydantic import BaseModel, Field, model_validator

router = APIRouter(prefix="/ewallet", tags=["e-wallet"], dependencies=[Depends(wallet_access)])


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
    quote_id: str
    request_key: str = Field(min_length=16, max_length=128)
    policy_version: str | None = None

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


class QuoteRequest(BaseModel):
    provider: Literal["gcash", "maya"]
    direction: Literal["cash-in", "cash-out"]
    amount: int = Field(gt=0, le=50_000)


@router.post("/session")
async def create_session(request: Request):
    token = secrets.token_urlsafe(32)
    async with request.app.state.db_session_factory() as session:
        session.add(KioskSession(id=hashlib.sha256(token.encode()).hexdigest(),
                                 expires_at=datetime.utcnow()+timedelta(days=1)))
        await session.commit()
    return {"token": token}


@router.post("/quotes")
async def quote(body: QuoteRequest, request: Request):
    try:
        return await request.app.state.ewallet_orchestrator.quote(
            **body.model_dump(), session_id=request.state.kiosk_session)
    except Exception as exc:
        raise HTTPException(409, detail={"code": getattr(exc, "code", "QUOTE_UNAVAILABLE"), "message": str(exc)}) from exc


@router.get("/resume")
async def resume(request: Request):
    async with request.app.state.db_session_factory() as session:
        record = (await session.execute(select(EWalletTransactionRecord).where(
            EWalletTransactionRecord.session_id == request.state.kiosk_session
        ).order_by(EWalletTransactionRecord.created_at.desc()).limit(1))).scalar_one_or_none()
    return await request.app.state.ewallet_orchestrator.get_transaction(record.id) if record else None


@router.post("/transactions/{transaction_id}/continue")
async def continue_transaction(transaction_id: str, request: Request):
    return await request.app.state.ewallet_orchestrator.touch(transaction_id, True)


@router.post("/transactions/{transaction_id}/heartbeat")
async def heartbeat(transaction_id: str, request: Request):
    return await request.app.state.ewallet_orchestrator.touch(transaction_id)


@router.post("/transactions/{transaction_id}/coins")
async def open_coins(transaction_id: str, request: Request):
    try:
        return await request.app.state.ewallet_orchestrator.open_coins(transaction_id)
    except Exception as exc:
        raise HTTPException(409, detail={"code": "COIN_INTAKE_UNAVAILABLE", "message": str(exc)}) from exc


@router.get("/config")
async def ewallet_config(request: Request):
    return {
        "policy_version": POLICY_VERSION,
        "max_amount": 50_000,
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
            **body.model_dump(), session_id=request.state.kiosk_session
        )
    except Exception as exc:
        response_status = (
            423 if "maintenance mode" in str(exc).lower() else 400
        )
        raise HTTPException(
            status_code=response_status, detail={"code": getattr(exc, "code", "EWALLET_ERROR"), "message": str(exc)}
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
    settings = request.app.state.settings
    if (
        settings.environment.lower() == "production"
        or not settings.use_mock_hardware
        or not settings.use_mock_serial
    ):
        raise HTTPException(status_code=404, detail="Not found")
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
        message = str(exc)
        raise HTTPException(
            status_code=409,
            detail={
                "code": getattr(exc, "code", "EWALLET_TRANSACTION_ERROR"),
                "message": message,
                "transaction_id": transaction_id,
                "state": None,
            },
        ) from exc


@router.post("/webhook")
async def paymongo_webhook(request: Request):
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
        if not event.get("id") or not event.get("resource_id"):
            raise ValueError("Gateway event id and resource_id are required")
        return await request.app.state.ewallet_orchestrator.enqueue_gateway_event(event)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc




def _normalize_gateway_event(payload: dict) -> dict:
    data = payload.get("data", payload)
    attrs = data.get("attributes", {})
    nested = attrs.get("data") or {}
    nested_attrs = nested.get("attributes") or {}
    event_type = attrs.get("type") or data.get("type") or "transfer.updated"
    resource_id = nested.get("id") or data.get("id")
    resource_id = nested_attrs.get("transfer_id") or attrs.get("transfer_id") or resource_id
    if event_type in {"wallet_transaction", "send_payment", "send_payout"}:
        event_type = "transfer.updated"
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
            (f"callback:{data.get('id')}:{attrs.get('status')}:{attrs.get('updated_at')}" if event_type == "transfer.updated" else None)
            or data.get("id")
            or payload.get("id")
            or ""
        ),
        "type": str(event_type),
        "resource_id": resource_id,
        "payment_id": payment_id,
        "status": status_value,
        "payload": payload,
    }
