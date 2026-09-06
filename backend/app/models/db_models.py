"""SQLAlchemy ORM models for transaction persistence and write-ahead logging."""

import enum
from datetime import datetime
"""SQLAlchemy ORM models for transaction persistence and write-ahead logging."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class TransactionState(str, enum.Enum):
    """Transaction lifecycle states."""

    IDLE = "IDLE"
    WAITING_FOR_BILL = "WAITING_FOR_BILL"
    AUTHENTICATING = "AUTHENTICATING"
    SORTING = "SORTING"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    DISPENSING = "DISPENSING"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
    CLAIM_REQUIRED = "CLAIM_REQUIRED"


class TransactionType(str, enum.Enum):
    """Money changer transaction types."""

    BILL_TO_BILL = "bill-to-bill"
    BILL_TO_COIN = "bill-to-coin"
    COIN_TO_BILL = "coin-to-bill"
    FOREX_USD_TO_PHP = "forex-usd-to-php"
    FOREX_PHP_TO_USD = "forex-php-to-usd"
    FOREX_EUR_TO_PHP = "forex-eur-to-php"
    FOREX_PHP_TO_EUR = "forex-php-to-eur"


class WALAction(str, enum.Enum):
    """Write-ahead log action types."""

    RESERVE_INVENTORY = "RESERVE_INVENTORY"
    DISPENSE_START = "DISPENSE_START"
    DISPENSE_COMPLETE = "DISPENSE_COMPLETE"
    BILL_ACCEPTED = "BILL_ACCEPTED"
    TRANSACTION_CREATED = "TRANSACTION_CREATED"
    FOREX_RATE_LOCKED = "FOREX_RATE_LOCKED"
    FOREX_CONVERSION_START = "FOREX_CONVERSION_START"


class WALStatus(str, enum.Enum):
    """Write-ahead log entry status."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    ROLLED_BACK = "ROLLED_BACK"


class ClaimStatus(str, enum.Enum):
    OPEN = "OPEN"
    PROVISIONAL = "PROVISIONAL"
    RESOLVED = "RESOLVED"


class PhysicalOperationState(str, enum.Enum):
    PLANNED = "PLANNED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    AMBIGUOUS = "AMBIGUOUS"
    RECONCILED = "RECONCILED"


class DispenseExecutionState(str, enum.Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    AMBIGUOUS = "AMBIGUOUS"


class TransactionRecord(Base):
    """Persistent record of a money changer transaction."""

    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(
        String, default=TransactionState.IDLE.value
    )
    target_amount: Mapped[int] = mapped_column(Integer, default=0)
    fee: Mapped[int] = mapped_column(Integer, default=0)
    total_due: Mapped[int] = mapped_column(Integer, default=0)
    inserted_amount: Mapped[int] = mapped_column(Integer, default=0)
    dispensed_amount: Mapped[int] = mapped_column(Integer, default=0)
    inserted_denominations: Mapped[dict] = mapped_column(
        JSON, default=dict
    )
    dispense_plan: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    dispense_result: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    selected_dispense_denoms: Mapped[list] = mapped_column(
        JSON, default=list
    )
    selected_dispense_counts: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    converter_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    # Forex-specific fields (nullable for non-forex transactions)
    from_currency: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    to_currency: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    exchange_rate: Mapped[Optional[float]] = mapped_column(nullable=True)
    rate_locked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    forex_fee_percentage: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )
    converted_amount: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    claim_ticket_code: Mapped[Optional[str]] = mapped_column(
        String, unique=True, nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    resolved_by: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )


class WALEntry(Base):
    """Write-ahead log entry for crash recovery.

    Each critical operation (inventory reservation, dispense start, etc.)
    is logged before execution. On recovery, pending entries are either
    completed or rolled back.
    """

    __tablename__ = "wal_entries"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    transaction_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String, default=WALStatus.PENDING.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class EWalletTransactionRecord(Base):
    """Persistent state for PayMongo-backed cash-in and cash-out."""

    __tablename__ = "ewallet_transactions"

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    request_key: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    policy_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submission_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    customer_present: Mapped[bool] = mapped_column(Boolean, default=True)
    change_due: Mapped[int] = mapped_column(Integer, default=0)
    change_dispensed: Mapped[int] = mapped_column(Integer, default=0)
    retained_amount: Mapped[int] = mapped_column(Integer, default=0)
    refunded_fee: Mapped[int] = mapped_column(Integer, default=0)
    wallet_credited: Mapped[int] = mapped_column(Integer, default=0)
    intake_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    gateway_work: Mapped[dict] = mapped_column(JSON, default=dict)
    __mapper_args__ = {"version_id_col": version}

    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    mobile_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    account_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    fee: Mapped[int] = mapped_column(Integer, nullable=False)
    transfer_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    total_due: Mapped[int] = mapped_column(Integer, nullable=False)
    inserted_amount: Mapped[int] = mapped_column(Integer, default=0)
    inserted_denominations: Mapped[dict] = mapped_column(JSON, default=dict)
    dispensed_amount: Mapped[int] = mapped_column(Integer, default=0)
    dispense_plan: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    dispense_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    gateway_payment_intent_id: Mapped[Optional[str]] = mapped_column(
        String, unique=True, nullable=True
    )
    gateway_batch_transfer_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    gateway_transfer_id: Mapped[Optional[str]] = mapped_column(
        String, unique=True, nullable=True
    )
    gateway_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    qr_image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    test_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    claim_ticket_code: Mapped[Optional[str]] = mapped_column(
        String, unique=True, nullable=True
    )
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    resolved_by: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )


class KioskSession(Base):
    __tablename__ = "kiosk_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EWalletQuote(Base):
    __tablename__ = "ewallet_quotes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class InventoryHold(Base):
    __tablename__ = "inventory_holds"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    quantities: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String, default="HELD")


class EWalletIntake(Base):
    __tablename__ = "ewallet_intakes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    medium: Mapped[str] = mapped_column(String, nullable=False)
    denomination: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String, default="PREPARED")
    resolution_notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EWalletCoinSession(Base):
    __tablename__ = "ewallet_coin_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sid: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String, default="OPEN")
    resolution_notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class GatewayEventRecord(Base):
    """Processed PayMongo event IDs for replay protection."""

    __tablename__ = "gateway_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="RECEIVED")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processing_error: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ClaimRecord(Base):
    """Unified, auditable customer obligation."""

    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("source_kind", "transaction_id", "claim_kind", name="uq_claim_source_kind"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    claim_ticket_code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source_kind: Mapped[str] = mapped_column(String, nullable=False)
    transaction_id: Mapped[str] = mapped_column(String, nullable=False)
    claim_kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default=ClaimStatus.OPEN.value)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    confirmed_dispensed_amount: Mapped[int] = mapped_column(Integer, default=0)
    ambiguous_amount: Mapped[int] = mapped_column(Integer, default=0)
    reason_code: Mapped[str] = mapped_column(String, nullable=False)
    reason_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class DispenseExecution(Base):
    """Exactly-once ownership record for one transaction payout."""

    __tablename__ = "dispense_executions"
    __table_args__ = (
        UniqueConstraint("source_kind", "transaction_id", name="uq_dispense_execution_source"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_kind: Mapped[str] = mapped_column(String, nullable=False)
    transaction_id: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, default=DispenseExecutionState.PLANNED.value)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_amount: Mapped[int] = mapped_column(Integer, default=0)
    ambiguous_amount: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class PhysicalOperation(Base):
    """Durable intent and outcome for one controller dispense command."""

    __tablename__ = "physical_operations"
    __table_args__ = (
        UniqueConstraint("execution_id", "sequence", name="uq_physical_operation_sequence"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    execution_id: Mapped[str] = mapped_column(String, nullable=False)
    transaction_id: Mapped[str] = mapped_column(String, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    controller: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, default="DISPENSE")
    denomination: Mapped[str] = mapped_column(String, nullable=False)
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)
    denomination_value: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_count: Mapped[int] = mapped_column(Integer, default=0)
    inventory_reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str] = mapped_column(String, default=PhysicalOperationState.PLANNED.value)
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reconciliation_notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reconciled_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class InventoryBalance(Base):
    """Current persisted count for one physical inventory location."""

    __tablename__ = "inventory_balances"
    __table_args__ = (
        UniqueConstraint(
            "location", "denomination", name="uq_inventory_location_denom"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    location: Mapped[str] = mapped_column(String, nullable=False)
    denomination: Mapped[str] = mapped_column(String, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class InventoryAdjustment(Base):
    """Append-only audit record for an inventory balance change."""

    __tablename__ = "inventory_adjustments"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    location: Mapped[str] = mapped_column(String, nullable=False)
    denomination: Mapped[str] = mapped_column(String, nullable=False)
    old_count: Mapped[int] = mapped_column(Integer, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class ConverterQuote(Base):
    """Stored proposals for money converter transactions."""

    __tablename__ = "converter_quotes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    transaction_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    service_type: Mapped[str] = mapped_column(String, nullable=False)
    input_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    fee: Mapped[int] = mapped_column(Integer, nullable=False)
    total_due: Mapped[int] = mapped_column(Integer, nullable=False)
    payout_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    items: Mapped[list] = mapped_column(JSON, default=list)
    requested_counts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_substitution: Mapped[bool] = mapped_column(Boolean, default=False)
    substitution_notice: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False
    )


class ForexQuoteRecord(Base):
    __tablename__ = "forex_quotes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ForexSession(Base):
    __tablename__ = "forex_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    quote_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    quote: Mapped[dict] = mapped_column(JSON, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    legs: Mapped[dict] = mapped_column(JSON, default=dict)
    payout_started: Mapped[bool] = mapped_column(Boolean, default=False)


class ForexIntake(Base):
    __tablename__ = "forex_intakes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    denomination: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String, default="PREPARED")
    resolved_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class ForexClaimTicket(Base):
    __tablename__ = "forex_claim_tickets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ForexClaimItem(Base):
    __tablename__ = "forex_claim_items"
    __table_args__ = (UniqueConstraint("ticket_id", "kind", name="uq_forex_claim_item"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, default="OPEN")
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class ForexSetting(Base):
    __tablename__ = "forex_settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)


class ConverterIntakeOperation(Base):
    """Durable bill intake operation record."""

    __tablename__ = "converter_intake_operations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    denomination: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String, default="PREPARED")
    inventory_credited: Mapped[bool] = mapped_column(Boolean, default=False)
    transaction_credited: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ConverterCoinSession(Base):
    """Persisted coin session state and cumulative count cursors."""

    __tablename__ = "converter_coin_sessions"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    session_id: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, index=True
    )
    transaction_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String, default="ACTIVE")
    cursor_php_1: Mapped[int] = mapped_column(Integer, default=0)
    cursor_php_5: Mapped[int] = mapped_column(Integer, default=0)
    cursor_php_10: Mapped[int] = mapped_column(Integer, default=0)
    cursor_php_20: Mapped[int] = mapped_column(Integer, default=0)
    final_count_php_1: Mapped[int] = mapped_column(Integer, default=0)
    final_count_php_5: Mapped[int] = mapped_column(Integer, default=0)
    final_count_php_10: Mapped[int] = mapped_column(Integer, default=0)
    final_count_php_20: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
