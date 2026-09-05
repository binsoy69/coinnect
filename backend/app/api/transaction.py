"""Transaction REST API endpoints for money changer operations."""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Annotated, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, StrictInt, model_validator

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.errors import QuoteChangedError, PayoutReapprovalRequiredError
from app.models.converter import ConverterQuotePayload, PayoutItem
from app.models.db_models import ConverterQuote
from app.services.converter_payout_planner import plan_payout

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transaction", tags=["transactions"])


# --- Request/Response Models ---


class StartTransactionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    quote_id: Optional[str] = None
    type: Optional[Literal["bill-to-bill", "bill-to-coin", "coin-to-bill"]] = None
    amount: Optional[Annotated[int, Field(strict=True, gt=0, le=1_000)]] = None
    selected_dispense_denoms: List[StrictInt] = Field(default_factory=list)
    selected_dispense_counts: Optional[Dict[int, StrictInt]] = None

    @model_validator(mode="after")
    def validate_transaction_options(self):
        if self.quote_id:
            return self
        raise ValueError("A customer-approved quote_id is required")


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

    # Converter snapshot fields
    revision: Optional[int] = 1
    approved_quote: Optional[dict] = None
    pending_quote: Optional[dict] = None
    acceptance_phase: Optional[str] = "OPEN"
    accounting_fault: bool = False
    warning_at: Optional[str] = None
    expires_at: Optional[str] = None
    server_time: Optional[str] = None
    claim: Optional[dict] = None
    can_continue: Optional[bool] = False
    can_confirm: Optional[bool] = False
    can_request_claim: Optional[bool] = False


class TransactionOptionItem(BaseModel):
    amount: int
    enabled: bool
    reason_code: Optional[str] = None
    reason: Optional[str] = None


class TransactionOptionsResponse(BaseModel):
    service_type: str
    fee: int
    options: List[TransactionOptionItem]


class CreateQuoteRequest(BaseModel):
    model_config = {"extra": "forbid"}

    type: Literal["bill-to-bill", "bill-to-coin", "coin-to-bill"]
    amount: Annotated[int, Field(strict=True, gt=0, le=1_000)]
    requested_counts: Optional[Dict[str, StrictInt]] = None


# --- Endpoints ---


@router.get("/options", response_model=TransactionOptionsResponse)
async def get_transaction_options(
    type: Literal["bill-to-bill", "bill-to-coin", "coin-to-bill"],
    request: Request,
):
    """Return configured fee and supported input amounts with feasibility status and reasons."""
    settings = getattr(request.app.state, "settings", None) or get_settings()
    fee_map = {
        "bill-to-bill": settings.fee_bill_to_bill,
        "bill-to-coin": settings.fee_bill_to_coin,
        "coin-to-bill": settings.fee_coin_to_bill,
    }
    fee = fee_map[type]

    allowed_amounts = {
        "bill-to-bill": [20, 50, 100, 200, 500, 1000],
        "bill-to-coin": [20, 50, 100, 200],
        "coin-to-bill": [20, 50, 100, 200],
    }
    amounts = allowed_amounts[type]

    machine_status = getattr(request.app.state, "machine_status", None)
    if machine_status:
        snapshot = machine_status.snapshot()
        available_bills = snapshot.consumables.bill_dispenser_counts
        available_coins = snapshot.consumables.coin_counts
    else:
        available_bills = {}
        available_coins = {}

    options: List[TransactionOptionItem] = []
    for amt in amounts:
        if type in {"bill-to-bill", "bill-to-coin"}:
            payout = amt - fee
            if payout <= 0:
                options.append(
                    TransactionOptionItem(
                        amount=amt,
                        enabled=False,
                        reason_code="FEE_EXCEEDS_AMOUNT",
                        reason=f"Transaction fee of ₱{fee} equals or exceeds selected amount ₱{amt}",
                    )
                )
                continue
        else:
            payout = amt

        plan = plan_payout(type, payout, available_bills, available_coins)
        if plan.success:
            options.append(
                TransactionOptionItem(
                    amount=amt,
                    enabled=True,
                    reason_code=None,
                    reason=None,
                )
            )
        else:
            options.append(
                TransactionOptionItem(
                    amount=amt,
                    enabled=False,
                    reason_code=plan.reason_code,
                    reason=plan.reason,
                )
            )

    return TransactionOptionsResponse(service_type=type, fee=fee, options=options)


@router.post("/quote", response_model=ConverterQuotePayload)
async def create_quote(req: CreateQuoteRequest, request: Request):
    """Generate and store an exact payout proposal for user approval."""
    settings = getattr(request.app.state, "settings", None) or get_settings()
    fee_map = {
        "bill-to-bill": settings.fee_bill_to_bill,
        "bill-to-coin": settings.fee_bill_to_coin,
        "coin-to-bill": settings.fee_coin_to_bill,
    }
    allowed_amounts = {
        "bill-to-bill": {20, 50, 100, 200, 500, 1000},
        "bill-to-coin": {20, 50, 100, 200},
        "coin-to-bill": {20, 50, 100, 200},
    }
    if req.amount not in allowed_amounts[req.type]:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_PARAM", "message": f"Unsupported amount {req.amount} for {req.type}"},
        )

    fee = fee_map[req.type]
    if req.type in {"bill-to-bill", "bill-to-coin"}:
        total_due = req.amount
        payout = req.amount - fee
        if payout <= 0:
            raise HTTPException(
                status_code=422,
                detail={"code": "FEE_EXCEEDS_AMOUNT", "message": f"Fee of ₱{fee} equals or exceeds amount ₱{req.amount}"},
            )
    else:
        total_due = req.amount + fee
        payout = req.amount

    machine_status = getattr(request.app.state, "machine_status", None)
    if machine_status:
        snapshot = machine_status.snapshot()
        available_bills = snapshot.consumables.bill_dispenser_counts
        available_coins = snapshot.consumables.coin_counts
    else:
        available_bills = {}
        available_coins = {}

    plan = plan_payout(
        req.type,
        payout,
        available_bills,
        available_coins,
        requested_counts=req.requested_counts,
    )
    if not plan.success:
        raise HTTPException(
            status_code=422,
            detail={"code": plan.reason_code, "message": plan.reason},
        )

    quote_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc)
    expires_utc = now_utc + timedelta(seconds=120)

    session_factory = getattr(request.app.state, "db_session_factory", None) or get_session_factory()
    quote_record = ConverterQuote(
        id=quote_id,
        transaction_id=None,
        service_type=req.type,
        input_amount=req.amount,
        fee=fee,
        total_due=total_due,
        payout_amount=payout,
        items=[item.model_dump() for item in plan.items],
        requested_counts=plan.requested_counts,
        is_substitution=plan.is_substitution,
        substitution_notice=plan.substitution_notice,
        created_at=now_utc.replace(tzinfo=None),
        expires_at=expires_utc.replace(tzinfo=None),
    )
    async with session_factory() as session:
        session.add(quote_record)
        await session.commit()

    return ConverterQuotePayload(
        id=quote_id,
        transaction_id=None,
        service_type=req.type,
        input_amount=req.amount,
        fee=fee,
        total_due=total_due,
        payout_amount=payout,
        items=plan.items,
        requested_counts=plan.requested_counts,
        is_substitution=plan.is_substitution,
        substitution_notice=plan.substitution_notice,
        created_at=now_utc.isoformat(),
        expires_at=expires_utc.isoformat(),
    )


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
            quote_id=req.quote_id,
        )
        return TransactionResponse(**state)
    except QuoteChangedError as qce:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "QUOTE_CHANGED",
                "message": "Stock or fee changed since proposal was generated",
                "quote": qce.new_quote,
            },
        )
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


class ApproveQuoteRequest(BaseModel):
    model_config = {"extra": "forbid"}
    quote_id: str


@router.post(
    "/{transaction_id}/approve-quote", response_model=TransactionResponse
)
async def approve_quote(
    transaction_id: str, req: ApproveQuoteRequest, request: Request
):
    """Approve a replacement proposal for an active transaction."""
    orchestrator = request.app.state.transaction_orchestrator
    try:
        state = await orchestrator.approve_quote(transaction_id, req.quote_id)
        return TransactionResponse(**state)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=_error_detail(e, str(e)))


@router.post(
    "/{transaction_id}/claim", response_model=TransactionResponse
)
async def request_claim(transaction_id: str, request: Request):
    """Request termination and a cash claim before dispensing."""
    orchestrator = request.app.state.transaction_orchestrator
    try:
        state = await orchestrator.request_claim(transaction_id)
        return TransactionResponse(**state)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=_error_detail(e, str(e)))


@router.post(
    "/{transaction_id}/activity", response_model=TransactionResponse
)
async def record_transaction_activity(transaction_id: str, request: Request):
    """Record user interaction (e.g. screen touch) to reset the inactivity timer."""
    orchestrator = request.app.state.transaction_orchestrator
    try:
        if orchestrator.active_transaction_id != transaction_id:
            raise HTTPException(
                status_code=404, detail="Transaction not active"
            )
        state = await orchestrator.record_activity(transaction_id)
        return TransactionResponse(**state)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=_error_detail(e, str(e)))


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
    except PayoutReapprovalRequiredError as prre:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PAYOUT_REAPPROVAL_REQUIRED",
                "message": "Approved payout is no longer available. A revised payout has been proposed.",
                "pending_quote": prre.pending_quote,
                "transaction_id": prre.transaction_id,
            },
        )
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
            controller = orchestrator._coin_controller
            report = await controller._serial.send_coin_command({"cmd": "MOCK_COIN_INSERT", "denom": req.denom})
            if report.get("status") != "OK":
                raise HTTPException(status_code=400, detail="Coin intake is closed or denomination is invalid")
            state = await orchestrator.handle_coin_session_pulse(
                sid=report["sid"], seq=report["seq"], denom=report["denom"], count=report["count"]
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
