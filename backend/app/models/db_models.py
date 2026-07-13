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


class GatewayEventRecord(Base):
    """Processed PayMongo event IDs for replay protection."""

    __tablename__ = "gateway_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_error: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


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
