"""Transaction REST API endpoints for money changer operations."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transaction", tags=["transactions"])


# --- Request/Response Models ---


class StartTransactionRequest(BaseModel):
    type: str  # "bill-to-bill", "bill-to-coin", "coin-to-bill"
    amount: int  # Target amount
    fee: int  # Transaction fee
    selected_dispense_denoms: List[int] = []  # e.g., [50, 100]


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
    inserted_amount: int
    dispensed_amount: int
    inserted_denominations: dict = {}
    dispense_plan: Optional[dict] = None
    dispense_result: Optional[dict] = None
    selected_dispense_denoms: list = []
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None


# --- Endpoints ---


@router.post("/", response_model=TransactionResponse)
async def start_transaction(req: StartTransactionRequest, request: Request):
    """Start a new money changer transaction."""
    orchestrator = request.app.state.transaction_orchestrator
    try:
        state = await orchestrator.start_transaction(
            transaction_type=req.type,
            target_amount=req.amount,
            fee=req.fee,
            selected_dispense_denoms=req.selected_dispense_denoms,
        )
        return TransactionResponse(**state)
    except Exception as e:
        if "already in progress" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(transaction_id: str, request: Request):
    """Get current state of a transaction."""
    orchestrator = request.app.state.transaction_orchestrator
    try:
        state = await orchestrator.get_transaction_state(transaction_id)
        return TransactionResponse(**state)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


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
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{transaction_id}/confirm", response_model=TransactionResponse
)
async def confirm_transaction(transaction_id: str, request: Request):
    """Confirm transaction and trigger dispensing."""
    orchestrator = request.app.state.transaction_orchestrator
    try:
        if orchestrator.active_transaction_id != transaction_id:
            raise HTTPException(
                status_code=404, detail="Transaction not active"
            )
        state = await orchestrator.confirm_transaction()
        return TransactionResponse(**state)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
                    if hasattr(gpio, "set_bill_in_position"):
                        gpio.set_bill_in_position(True)
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
