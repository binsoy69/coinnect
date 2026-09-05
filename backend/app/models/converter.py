"""Pydantic schemas, enums, and structured error codes for money converter transactions."""

import enum
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class AcceptancePhase(str, enum.Enum):
    """Customer cash intake phase."""
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


class ConverterIntakeState(str, enum.Enum):
    """Bill intake operation lifecycle state."""
    PREPARED = "PREPARED"
    RETAINED = "RETAINED"
    RETURNED = "RETURNED"
    UNCERTAIN = "UNCERTAIN"


class CoinSessionState(str, enum.Enum):
    """Coin acceptor session state on controller."""
    ACTIVE = "ACTIVE"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    UNCERTAIN = "UNCERTAIN"


class ConverterErrorCode(str, enum.Enum):
    """Documented structured error codes for converter operations."""
    QUOTE_CHANGED = "QUOTE_CHANGED"
    PAYOUT_REAPPROVAL_REQUIRED = "PAYOUT_REAPPROVAL_REQUIRED"
    INSUFFICIENT_INVENTORY = "INSUFFICIENT_INVENTORY"
    UNSUPPORTED_DENOMINATION = "UNSUPPORTED_DENOMINATION"
    EXCEEDS_COMMAND_LIMIT = "EXCEEDS_COMMAND_LIMIT"
    LOCKED_OUT = "LOCKED_OUT"
    ACCOUNTING_FAULT = "ACCOUNTING_FAULT"
    CASH_ALREADY_ACCEPTED = "CASH_ALREADY_ACCEPTED"
    TRANSACTION_NOT_ACTIVE = "TRANSACTION_NOT_ACTIVE"
    TRANSACTION_NOT_CONFIRMABLE = "TRANSACTION_NOT_CONFIRMABLE"
    INVALID_PARAM = "INVALID_PARAM"
    HARDWARE_FAULT = "HARDWARE_FAULT"
    TIMEOUT = "TIMEOUT"
    TIMEOUT_AFTER_CASH = "TIMEOUT_AFTER_CASH"
    AMBIGUOUS_DISPENSE = "AMBIGUOUS_DISPENSE"
    PARTIAL_DISPENSE = "PARTIAL_DISPENSE"
    EXCESS_REFUND_UNAVAILABLE = "EXCESS_REFUND_UNAVAILABLE"
    TAMPER_DETECTED = "TAMPER_DETECTED"
    NOT_HOMED = "NOT_HOMED"


class PayoutItem(BaseModel):
    """Exact typed payout item."""
    denom: str  # e.g. "PHP_20"
    denom_type: Literal["bill", "coin"]
    count: int
    value: int  # Integer peso value per unit


class ConverterQuotePayload(BaseModel):
    """Proposal payload returned to client and stored in ConverterQuote."""
    id: str
    transaction_id: Optional[str] = None
    service_type: str
    input_amount: int
    fee: int
    total_due: int
    payout_amount: int
    items: List[PayoutItem] = Field(default_factory=list)
    requested_counts: Optional[Dict[str, int]] = None
    is_substitution: bool = False
    substitution_notice: Optional[str] = None
    created_at: str
    expires_at: str


class ConverterClaimSnapshot(BaseModel):
    """Customer claim obligation details."""
    claim_ticket_code: str
    amount: int
    currency: str = "PHP"
    reason_code: str
    reason_message: Optional[str] = None
    status: str
    is_provisional: bool = False
    ambiguous_amount: int = 0


class ConverterMetadata(BaseModel):
    """Metadata stored in transactions.converter_metadata JSON column."""
    revision: int = 1
    approved_quote_id: Optional[str] = None
    pending_quote_id: Optional[str] = None
    acceptance_phase: AcceptancePhase = AcceptancePhase.OPEN
    warning_at: Optional[str] = None
    expires_at: Optional[str] = None
    coin_session_id: Optional[int] = None
    termination_reason: Optional[str] = None


class ConverterSnapshot(BaseModel):
    """Authoritative converter transaction snapshot."""
    accounting_fault: bool = False
    transaction_id: str
    type: str
    state: str
    target_amount: int
    fee: int
    total_due: int
    payout_amount: int
    inserted_amount: int
    dispensed_amount: int
    inserted_denominations: Dict[str, int] = Field(default_factory=dict)
    dispense_plan: Optional[dict] = None
    dispense_result: Optional[dict] = None
    selected_dispense_denoms: List[int] = Field(default_factory=list)
    selected_dispense_counts: Optional[Dict[str, int]] = Field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    claim_ticket_code: Optional[str] = None
    shortfall: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Converter-specific additions
    revision: int = 1
    approved_quote: Optional[ConverterQuotePayload] = None
    pending_quote: Optional[ConverterQuotePayload] = None
    acceptance_phase: AcceptancePhase = AcceptancePhase.OPEN
    warning_at: Optional[str] = None
    expires_at: Optional[str] = None
    server_time: str
    claim: Optional[ConverterClaimSnapshot] = None
    can_continue: bool = False
    can_confirm: bool = False
    can_request_claim: bool = False
