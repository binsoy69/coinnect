"""Forex REST API endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forex", tags=["forex"])


# --- Request/Response Models ---


class ForexStartRequest(BaseModel):
    quote_id: str = Field(min_length=1, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ForexRatesResponse(BaseModel):
    availability: dict = {}
    rates: dict  # {"USD": 58.7656, "EUR": 61.7246}
    fetched_at: Optional[str] = None
    valid: bool = False
    online: bool = False
    enabled: bool = True
    fees: dict = {}  # {"usd-to-php": 5.0, ...}


class ForexQuoteResponse(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    input_amount: float
    converted_amount: float
    fee_percentage: float
    fee_amount: float
    output_amount: float


class ForexTransactionResponse(BaseModel):
    transaction_id: str
    type: str
    state: str
    target_amount: int
    fee: int
    total_due: int
    inserted_amount: int
    dispensed_amount: int
    inserted_denominations: dict = {}
    dispense_plan: Optional[dict] = None
    dispense_result: Optional[dict] = None
    selected_dispense_denoms: list = []
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    claim_ticket_code: Optional[str] = None
    shortfall: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    revision: int = 0
    deadline: Optional[str] = None
    quote: Optional[dict] = None
    payout_legs: dict = {}
    claim: Optional[dict] = None
    legacy_review_required: bool = False
    # Forex fields
    from_currency: Optional[str] = None
    to_currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    rate_locked_at: Optional[str] = None
    forex_fee_percentage: Optional[float] = None
    converted_amount_forex: Optional[int] = None


# --- Endpoints ---


@router.get("/rates", response_model=ForexRatesResponse)
async def get_forex_rates(request: Request):
    """Get current exchange rates and availability status."""
    forex_service = request.app.state.forex_rate_service
    return ForexRatesResponse(
        availability=await request.app.state.forex_transaction_orchestrator.availability(),
        rates=forex_service.current_rates,
        fetched_at=(
            forex_service._cache.fetched_at.isoformat()
            if forex_service._cache.fetched_at
            else None
        ),
        valid=forex_service.rates_valid,
        online=forex_service.is_online,
        enabled=forex_service.enabled,
        fees={
            "usd-to-php": forex_service.get_fee_percentage("usd-to-php"),
            "php-to-usd": forex_service.get_fee_percentage("php-to-usd"),
            "eur-to-php": forex_service.get_fee_percentage("eur-to-php"),
            "php-to-eur": forex_service.get_fee_percentage("php-to-eur"),
        },
    )


@router.get("/quote/{service_type}")
async def get_forex_quote(
    service_type: str, amount: int, request: Request
):
    """Get a conversion quote without starting a transaction.

    Query params:
        amount: Foreign currency amount

    Example: GET /api/v1/forex/quote/usd-to-php?amount=100
    """
    forex_service = request.app.state.forex_rate_service
    try:
        quote = await forex_service.create_quote(service_type, amount)
        return quote.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transaction", response_model=ForexTransactionResponse)
async def start_forex_transaction(req: ForexStartRequest, request: Request):
    """Start a new forex transaction with rate locking."""
    orchestrator = request.app.state.forex_transaction_orchestrator
    try:
        state = await orchestrator.start_transaction(
            quote_id=req.quote_id, idempotency_key=req.idempotency_key,
        )
        return ForexTransactionResponse(**_map_state(state))
    except Exception as e:
        detail = str(e)
        response_status = 423 if "maintenance mode" in detail.lower() else (
            409 if "already in progress" in detail else 400
        )
        raise HTTPException(status_code=response_status, detail=detail)


@router.get("/transaction/{transaction_id}", response_model=ForexTransactionResponse)
async def get_forex_transaction(transaction_id: str, request: Request):
    """Get forex transaction state."""
    orchestrator = request.app.state.forex_transaction_orchestrator
    try:
        state = await orchestrator.get_transaction_state(transaction_id)
        return ForexTransactionResponse(**_map_state(state))
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/transaction/{transaction_id}", response_model=ForexTransactionResponse)
async def cancel_forex_transaction(transaction_id: str, request: Request):
    """Cancel an active forex transaction."""
    orchestrator = request.app.state.forex_transaction_orchestrator
    try:
        if orchestrator.active_transaction_id != transaction_id:
            raise HTTPException(status_code=404, detail="Transaction not active")
        state = await orchestrator.cancel_transaction(transaction_id)
        return ForexTransactionResponse(**_map_state(state))
    except HTTPException:
        raise
    except Exception as e:
        message = str(e)
        raise HTTPException(
            status_code=409 if "CASH_ALREADY_ACCEPTED" in message else 422,
            detail={
                "code": "CASH_ALREADY_ACCEPTED" if "CASH_ALREADY_ACCEPTED" in message else "FOREX_TRANSACTION_ERROR",
                "message": message,
                "transaction_id": transaction_id,
                "state": None,
            },
        )


@router.post("/transaction/{transaction_id}/confirm", response_model=ForexTransactionResponse)
async def confirm_forex_transaction(transaction_id: str, request: Request):
    """Confirm forex transaction and trigger dispensing."""
    orchestrator = request.app.state.forex_transaction_orchestrator
    try:
        if orchestrator.active_transaction_id != transaction_id:
            try:
                state = await orchestrator.get_transaction_state(transaction_id)
            except Exception as exc:
                raise HTTPException(
                    status_code=404, detail="Transaction not found"
                ) from exc
            if state["state"] not in {"COMPLETE", "ERROR", "CLAIM_REQUIRED"}:
                raise HTTPException(
                    status_code=409, detail="Transaction is not confirmable"
                )
            return ForexTransactionResponse(**_map_state(state))
        state = await orchestrator.confirm_transaction(transaction_id)
        return ForexTransactionResponse(**_map_state(state))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transaction/{transaction_id}/accept-bill", response_model=ForexTransactionResponse)
async def trigger_forex_bill_acceptance(transaction_id: str, request: Request):
    """Trigger one bill acceptance cycle for forex transaction."""
    orchestrator = request.app.state.forex_transaction_orchestrator
    try:
        if orchestrator.active_transaction_id != transaction_id:
            raise HTTPException(
                status_code=404, detail="Transaction not active"
            )
        state = await orchestrator.handle_bill_inserted(transaction_id)
        return ForexTransactionResponse(**_map_state(state))
    except HTTPException:
        raise
    except Exception as e:
        message = str(e)
        raise HTTPException(
            status_code=409 if "CASH_ALREADY_ACCEPTED" in message else 422,
            detail={
                "code": "CASH_ALREADY_ACCEPTED" if "CASH_ALREADY_ACCEPTED" in message else "FOREX_TRANSACTION_ERROR",
                "message": message,
                "transaction_id": transaction_id,
                "state": None,
            },
        )


@router.post("/transaction/{transaction_id}/continue")
async def continue_forex(transaction_id: str, request: Request):
    orchestrator = request.app.state.forex_transaction_orchestrator
    if orchestrator.active_transaction_id != transaction_id:
        raise HTTPException(status_code=409, detail="Transaction is not active")
    try:
        return await orchestrator.continue_transaction(transaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/transaction/{transaction_id}/simulate-insert")
async def simulate_forex_insert(
    transaction_id: str, request: Request
):
    """Simulate bill insertion for forex (dev mode only).

    Body: {"denom": 100, "currency": "USD"}
    """
    orchestrator = request.app.state.forex_transaction_orchestrator
    settings = request.app.state.settings
    if (
        settings.environment.lower() == "production"
        or not settings.use_mock_hardware
        or not settings.use_mock_serial
    ):
        raise HTTPException(status_code=404, detail="Not found")
    body = await request.json()
    denom = body.get("denom", 0)
    currency = body.get("currency", "PHP")

    try:
        if orchestrator.active_transaction_id != transaction_id:
            raise HTTPException(status_code=404, detail="Transaction not active")

        if settings.use_mock_hardware:
            bill_acceptor = request.app.state.bill_acceptor
            from app.core.constants import BillDenom
            from app.models.denominations import value_to_denom_string

            denom_str = value_to_denom_string(denom, currency)
            try:
                bill_denom = BillDenom(denom_str)
                auth = bill_acceptor._auth
                if hasattr(auth, "set_next_denomination"):
                    auth.set_next_denomination(bill_denom)
                if hasattr(auth, "set_accept_next"):
                    auth.set_accept_next()
                gpio = bill_acceptor._gpio
                if hasattr(gpio, "set_bill_at_entry"):
                    gpio.set_bill_at_entry(True)
            except (ValueError, KeyError):
                raise HTTPException(status_code=400, detail=f"Invalid denomination: {denom}")

        state = await orchestrator.handle_bill_inserted(transaction_id)
        return state
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connectivity")
async def check_connectivity(request: Request):
    """Check if forex is currently available (online + valid rates)."""
    forex_service = request.app.state.forex_rate_service
    available = await forex_service.check_forex_available()
    return {
        "online": forex_service.is_online,
        "rates_valid": forex_service.rates_valid,
        "forex_available": available,
    }


def _map_state(state: dict) -> dict:
    """Map internal state dict to response fields."""
    mapped = dict(state)
    # Handle field name conflict: converted_amount -> converted_amount_forex
    if "converted_amount" in mapped:
        mapped["converted_amount_forex"] = mapped.pop("converted_amount")
    return mapped
