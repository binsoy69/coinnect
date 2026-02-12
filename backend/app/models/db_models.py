"""SQLAlchemy ORM models for transaction persistence and write-ahead logging."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Integer, String
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


class WALAction(str, enum.Enum):
    """Write-ahead log action types."""

    RESERVE_INVENTORY = "RESERVE_INVENTORY"
    DISPENSE_START = "DISPENSE_START"
    DISPENSE_COMPLETE = "DISPENSE_COMPLETE"
    BILL_ACCEPTED = "BILL_ACCEPTED"
    TRANSACTION_CREATED = "TRANSACTION_CREATED"


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
    error_code: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
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
