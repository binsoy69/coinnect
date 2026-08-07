"""Transaction REST API endpoints for money changer operations."""

import logging
from typing import Annotated, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, StrictInt, model_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transaction", tags=["transactions"])


# --- Request/Response Models ---


class StartTransactionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    type: Literal["bill-to-bill", "bill-to-coin", "coin-to-bill"]
    amount: Annotated[int, Field(strict=True, gt=0, le=1_000)]
    selected_dispense_denoms: List[StrictInt] = Field(default_factory=list)
    selected_dispense_counts: Optional[Dict[int, StrictInt]] = None

    @model_validator(mode="after")
    def validate_transaction_options(self):
        allowed_amounts = {
            "bill-to-bill": {20, 50, 100, 200, 500, 1000},
            "bill-to-coin": {20, 50, 100, 200},
            "coin-to-bill": {20, 50, 100, 200},
        }
        allowed_outputs = {
            "bill-to-bill": {20, 50, 100, 200, 500, 1000},
            "bill-to-coin": {1, 5, 10, 20},
            "coin-to-bill": {20, 50, 100, 200, 500, 1000},
        }
        if self.amount not in allowed_amounts[self.type]:
            raise ValueError("Unsupported amount for transaction type")
        allowed = allowed_outputs[self.type]
        if any(denom not in allowed for denom in self.selected_dispense_denoms):
            raise ValueError("Unsupported dispense denomination")
        if self.selected_dispense_counts is not None:
            for denom, count in self.selected_dispense_counts.items():
                limit = 50 if self.type == "bill-to-coin" else 20
                if denom not in allowed or count < 0 or count > limit:
                    raise ValueError("Invalid requested denomination count")
        return self


class SimulateInsertRequest(BaseModel):
    denom: int  # Denomination value (e.g., 100 for PHP_100)
    insert_type: str = "bill"  # "bill" or "coin"


class TransactionResponse(BaseModel):
    transaction_id: str
    type: str
    state: str
    target_amount: int
    fee: int
    total_due: int
    payout_amount: int
    inserted_amount: int
    dispensed_amount: int
    inserted_denominations: dict = Field(default_factory=dict)
    dispense_plan: Optional[dict] = None
    dispense_result: Optional[dict] = None
    selected_dispense_denoms: list = Field(default_factory=list)
    selected_dispense_counts: Optional[dict] = Field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    claim_ticket_code: Optional[str] = None
    shortfall: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None


# --- Endpoints ---


@router.post("/", response_model=TransactionResponse)
async def start_transaction(req: StartTransactionRequest, request: Request):
    """Start a new money changer transaction."""
    orchestrator = request.app.state.transaction_orchestrator
    ewallet = getattr(request.app.state, "ewallet_orchestrator", None)
    if ewallet is not None and ewallet.has_active_transaction:
        raise HTTPException(
            status_code=409, detail="An e-wallet transaction is active"
        )
    try:
        state = await orchestrator.start_transaction(
            transaction_type=req.type,
            target_amount=req.amount,
            selected_dispense_denoms=req.selected_dispense_denoms,
            selected_dispense_counts=req.selected_dispense_counts,
        )
        return TransactionResponse(**state)
    except Exception as e:
        message = str(e)
        status = 423 if "maintenance mode" in message.lower() else 409 if "already in progress" in message else 422
        raise HTTPException(status_code=status, detail=_error_detail(e, message))


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(transaction_id: str, request: Request):
    """Get current state of a transaction."""
    orchestrator = request.app.state.transaction_orchestrator
    try:
        state = await orchestrator.get_transaction_state(transaction_id)
        return TransactionResponse(**state)
    except Exception as e:
        raise HTTPException(status_code=404, detail=_error_detail(e, str(e)))


@router.delete("/{transaction_id}", response_model=TransactionResponse)
async def cancel_transaction(transaction_id: str, request: Request):
    """Cancel an active transaction."""
    orchestrator = request.app.state.transaction_orchestrator
    try:
        if orchestrator.active_transaction_id != transaction_id:
            raise HTTPException(
                status_code=404, detail="Transaction not active"
            )
        state = await orchestrator.cancel_transaction()
        return TransactionResponse(**state)
    except HTTPException:
        raise
    except Exception as e:
        message = str(e)
        status = 409 if "CASH_ALREADY_ACCEPTED" in message else 422
        raise HTTPException(status_code=status, detail=_error_detail(e, message))


@router.post(
    "/{transaction_id}/confirm", response_model=TransactionResponse
)
async def confirm_transaction(transaction_id: str, request: Request):
    """Confirm transaction and trigger dispensing."""
    orchestrator = request.app.state.transaction_orchestrator
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
            return TransactionResponse(**state)
        state = await orchestrator.confirm_transaction()
        return TransactionResponse(**state)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=_error_detail(e, str(e)))


def _error_detail(exc: Exception, message: str) -> dict:
    transaction_id = getattr(exc, "transaction_id", None)
    code = "CASH_ALREADY_ACCEPTED" if "CASH_ALREADY_ACCEPTED" in message else exc.__class__.__name__.upper()
    return {
        "code": code,
        "message": message,
        "transaction_id": transaction_id,
        "state": None,
    }


@router.post("/{transaction_id}/accept-bill")
async def trigger_bill_acceptance(transaction_id: str, request: Request):
    """Trigger one bill acceptance cycle.

    In production: called when bill is detected at entry sensor.
    In dev/mock mode: called from frontend or keyboard simulation.
    """
    orchestrator = request.app.state.transaction_orchestrator
    try:
        if orchestrator.active_transaction_id != transaction_id:
            raise HTTPException(
                status_code=404, detail="Transaction not active"
            )
        state = await orchestrator.handle_bill_inserted()
        return state
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{transaction_id}/simulate-insert")
async def simulate_insert(
    transaction_id: str, req: SimulateInsertRequest, request: Request
):
    """Simulate a bill or coin insertion (development mode only).

    For keyboard simulation: sends a mock bill acceptance or coin event.
    """
    orchestrator = request.app.state.transaction_orchestrator
    settings = request.app.state.settings

    if (
        settings.environment.lower() == "production"
        or not settings.use_mock_hardware
        or not settings.use_mock_serial
    ):
        raise HTTPException(status_code=404, detail="Not found")

    try:
        if orchestrator.active_transaction_id != transaction_id:
            raise HTTPException(
                status_code=404, detail="Transaction not active"
            )

        if req.insert_type == "coin":
            # Simulate coin insertion via event
            state = await orchestrator.handle_coin_inserted(
                denom=req.denom, total=0
            )
            return state
        else:
            # For bill simulation with mock hardware, configure the mock
            # authenticator to return the requested denomination
            if settings.use_mock_hardware:
                bill_acceptor = request.app.state.bill_acceptor
                from app.core.constants import BillDenom
                from app.models.denominations import value_to_denom_string

                denom_str = value_to_denom_string(req.denom, "PHP")
                try:
                    denom = BillDenom(denom_str)
                    # Configure mock authenticator for this denomination
                    auth = bill_acceptor._auth
                    if hasattr(auth, "set_next_denomination"):
                        auth.set_next_denomination(denom)
                    if hasattr(auth, "set_accept_next"):
                        auth.set_accept_next()
                    # Configure mock GPIO for instant bill detection
                    gpio = bill_acceptor._gpio
                    if hasattr(gpio, "set_bill_at_entry"):
                        gpio.set_bill_at_entry(True)
                except (ValueError, KeyError):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid denomination: {req.denom}",
                    )

            state = await orchestrator.handle_bill_inserted()
            return state
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
