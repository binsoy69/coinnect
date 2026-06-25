"""PayMongo-only sandbox sessions for the maintenance healthcheck."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Integer, String, delete, select, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import Settings
from app.services.paymongo_client import PayMongoClient
from healthcheck_api.models import EWalletSandboxSessionCreate

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SandboxState(str, Enum):
    PENDING_CALLBACK = "PENDING_CALLBACK"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


TERMINAL_STATES = {
    SandboxState.VERIFIED.value,
    SandboxState.FAILED.value,
    SandboxState.TIMED_OUT.value,
    SandboxState.CANCELLED.value,
}


class SandboxBase(DeclarativeBase):
    pass


class SandboxSessionRecord(SandboxBase):
    __tablename__ = "ewallet_sandbox_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    mobile_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    account_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gateway_payment_intent_id: Mapped[Optional[str]] = mapped_column(
        String, unique=True, nullable=True
    )
    gateway_batch_transfer_id: Mapped[Optional[str]] = mapped_column(
        String, unique=True, nullable=True
    )
    gateway_transfer_id: Mapped[Optional[str]] = mapped_column(
        String, unique=True, nullable=True
    )
    gateway_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    qr_image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    test_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )


class CallbackAuditRecord(SandboxBase):
    __tablename__ = "ewallet_sandbox_callback_audit"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    callback_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )


@dataclass
class EWalletSandboxConfig:
    database_url: str = "sqlite+aiosqlite:///./healthcheck_ewallet.db"
    public_base_url: str = ""
    timeout_seconds: int = 600
    retention_limit: int = 100

    @classmethod
    def from_environment(cls) -> "EWalletSandboxConfig":
        return cls(
            database_url=os.environ.get(
                "HEALTHCHECK_EWALLET_DB_URL",
                "sqlite+aiosqlite:///./healthcheck_ewallet.db",
            ),
            public_base_url=os.environ.get(
                "HEALTHCHECK_PUBLIC_BASE_URL", ""
            ).rstrip("/"),
            timeout_seconds=int(
                os.environ.get(
                    "HEALTHCHECK_EWALLET_TIMEOUT_SECONDS", "600"
                )
            ),
            retention_limit=int(
                os.environ.get(
                    "HEALTHCHECK_EWALLET_RETENTION_LIMIT", "100"
                )
            ),
        )

    @property
    def payment_callback_url(self) -> str:
        return (
            f"{self.public_base_url}/api/v1/"
            "ewallet-sandbox/callbacks/payment"
        )

    @property
    def transfer_callback_url(self) -> str:
        return (
            f"{self.public_base_url}/api/v1/"
            "ewallet-sandbox/callbacks/transfer"
        )

    def readiness(self, settings: Settings) -> dict:
        missing: list[str] = []
        if not self.public_base_url:
            missing.append("HEALTHCHECK_PUBLIC_BASE_URL")
        elif not self.public_base_url.lower().startswith("https://"):
            missing.append(
                "HEALTHCHECK_PUBLIC_BASE_URL must use HTTPS"
            )
        if not settings.paymongo_sandbox:
            missing.append("PAYMONGO_SANDBOX must be true")
        if not settings.paymongo_secret_key.startswith("sk_test_"):
            missing.append("PAYMONGO_SECRET_KEY must be a test key")
        if not settings.paymongo_public_key.startswith("pk_test_"):
            missing.append("PAYMONGO_PUBLIC_KEY must be a test key")
        if not settings.paymongo_webhook_secret:
            missing.append("PAYMONGO_WEBHOOK_SECRET")
        if not settings.paymongo_source_account_number:
            missing.append("PAYMONGO_SOURCE_ACCOUNT_NUMBER")
        if not settings.paymongo_source_account_name:
            missing.append("PAYMONGO_SOURCE_ACCOUNT_NAME")
        if not settings.paymongo_source_account_bic:
            missing.append("PAYMONGO_SOURCE_ACCOUNT_BIC")
        return {
            "ready": not missing,
            "sandbox": settings.paymongo_sandbox,
            "missing": missing,
            "payment_callback_url": (
                self.payment_callback_url if self.public_base_url else None
            ),
            "transfer_callback_url": (
                self.transfer_callback_url if self.public_base_url else None
            ),
            "timeout_seconds": self.timeout_seconds,
        }


class SandboxConfigurationError(RuntimeError):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(
            "E-wallet sandbox is not configured: " + ", ".join(missing)
        )


async def create_sandbox_database(
    database_url: str,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as connection:
        await connection.run_sync(SandboxBase.metadata.create_all)
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, factory


class EWalletSandboxService:
    def __init__(
        self,
        settings: Settings,
        gateway: PayMongoClient,
        db_factory: async_sessionmaker[AsyncSession],
        config: EWalletSandboxConfig,
    ):
        self._settings = settings
        self._gateway = gateway
        self._db_factory = db_factory
        self._config = config
        self._expiry_task: asyncio.Task | None = None

    @property
    def config_status(self) -> dict:
        return self._config.readiness(self._settings)

    async def start(self) -> None:
        await self.expire_pending_sessions()
        await self.prune_completed_sessions()
        self._expiry_task = asyncio.create_task(self._expiry_loop())

    async def stop(self) -> None:
        if self._expiry_task is None:
            return
        self._expiry_task.cancel()
        try:
            await self._expiry_task
        except asyncio.CancelledError:
            pass
        self._expiry_task = None

    async def create_session(
        self, request: EWalletSandboxSessionCreate
    ) -> dict:
        readiness = self.config_status
        if not readiness["ready"]:
            raise SandboxConfigurationError(readiness["missing"])

        session_id = str(uuid.uuid4())
        expires_at = _utcnow() + timedelta(
            seconds=self._config.timeout_seconds
        )
        record = SandboxSessionRecord(
            id=session_id,
            provider=request.provider,
            direction=request.direction,
            amount=request.amount,
            mobile_number=request.mobile_number,
            account_name=request.account_name,
            state=SandboxState.PENDING_CALLBACK.value,
            expires_at=expires_at,
        )

        try:
            if request.direction == "cash-out":
                result = await self._gateway.create_qr_payment(
                    amount_centavos=request.amount * 100,
                    reference=session_id,
                    idempotency_key=(
                        f"healthcheck:{session_id}:qr"
                    ),
                )
                record.gateway_payment_intent_id = (
                    result.payment_intent_id
                )
                record.gateway_status = result.status
                record.qr_image_url = result.qr_image_url
                record.test_url = result.test_url
            else:
                result = await self._gateway.create_disbursement(
                    provider=request.provider,
                    account_number=request.mobile_number or "",
                    account_name=request.account_name or "",
                    amount_centavos=request.amount * 100,
                    reference=session_id,
                    idempotency_key=(
                        f"healthcheck:{session_id}:transfer"
                    ),
                    callback_url=self._config.transfer_callback_url,
                )
                record.gateway_batch_transfer_id = (
                    result.batch_transfer_id
                )
                record.gateway_transfer_id = result.transfer_id
                record.gateway_status = result.status
        except Exception as exc:
            record.state = SandboxState.FAILED.value
            record.error_code = "GATEWAY_CREATION_FAILED"
            record.error_message = str(exc)[:500]
            record.completed_at = _utcnow()
            async with self._db_factory() as session:
                session.add(record)
                await session.commit()
            raise

        async with self._db_factory() as session:
            session.add(record)
            await session.commit()
        await self.prune_completed_sessions()
        return self._serialize(record)

    async def get_session(self, session_id: str) -> dict:
        async with self._db_factory() as session:
            record = await session.get(SandboxSessionRecord, session_id)
            if record is None:
                raise KeyError(session_id)
            return self._serialize(record)

    async def list_sessions(self) -> list[dict]:
        async with self._db_factory() as session:
            result = await session.execute(
                select(SandboxSessionRecord).order_by(
                    SandboxSessionRecord.created_at.desc()
                )
            )
            return [
                self._serialize(record) for record in result.scalars()
            ]

    async def cancel_session(self, session_id: str) -> dict:
        async with self._db_factory() as session:
            record = await session.get(SandboxSessionRecord, session_id)
            if record is None:
                raise KeyError(session_id)
            if record.state == SandboxState.PENDING_CALLBACK.value:
                record.state = SandboxState.CANCELLED.value
                record.completed_at = _utcnow()
                await session.commit()
            return self._serialize(record)

    async def process_payment_event(self, event: dict) -> dict:
        event_id = str(event["id"])
        audit_id = f"payment:{event_id}"
        resource_id = event.get("resource_id")
        async with self._db_factory() as session:
            if await session.get(CallbackAuditRecord, audit_id):
                return {"duplicate": True}
            result = await session.execute(
                select(SandboxSessionRecord).where(
                    SandboxSessionRecord.gateway_payment_intent_id
                    == resource_id
                )
            )
            record = result.scalar_one_or_none()
            audit = CallbackAuditRecord(
                id=audit_id,
                callback_type="payment",
                resource_id=resource_id,
                session_id=record.id if record else None,
                outcome="received",
            )
            session.add(audit)
            if record is None:
                audit.outcome = "session_not_found"
                await session.commit()
                return {
                    "processed": False,
                    "reason": "session_not_found",
                }
            if record.state in TERMINAL_STATES:
                audit.outcome = "ignored_terminal"
                await session.commit()
                return self._serialize(record)
            session_id = record.id
            intent_id = record.gateway_payment_intent_id
            expected_amount = record.amount * 100
            await session.commit()

        if event.get("type") != "payment.paid":
            return await self._fail_session(
                session_id,
                "PAYMENT_EVENT_INVALID",
                "Expected payment.paid event",
                audit_id,
            )

        try:
            intent = await self._gateway.get_payment_intent(intent_id)
            self._validate_payment(
                intent,
                intent_id,
                session_id,
                expected_amount,
                event.get("payment_id"),
            )
        except SandboxVerificationError as exc:
            return await self._fail_session(
                session_id, exc.code, str(exc), audit_id
            )
        except Exception as exc:
            return await self._fail_session(
                session_id,
                "PAYMENT_RETRIEVAL_FAILED",
                str(exc),
                audit_id,
            )
        return await self._verify_session(
            session_id, "paid", audit_id
        )

    async def process_transfer_callback(
        self, batch_transfer_id: str
    ) -> dict:
        audit_id = f"transfer:{uuid.uuid4()}"
        async with self._db_factory() as session:
            result = await session.execute(
                select(SandboxSessionRecord).where(
                    SandboxSessionRecord.gateway_batch_transfer_id
                    == batch_transfer_id
                )
            )
            record = result.scalar_one_or_none()
            audit = CallbackAuditRecord(
                id=audit_id,
                callback_type="transfer",
                resource_id=batch_transfer_id,
                session_id=record.id if record else None,
                outcome="received",
            )
            session.add(audit)
            if record is None:
                audit.outcome = "session_not_found"
                await session.commit()
                return {
                    "processed": False,
                    "reason": "session_not_found",
                }
            if record.state in TERMINAL_STATES:
                audit.outcome = "ignored_terminal"
                await session.commit()
                return self._serialize(record)
            session_id = record.id
            transfer_id = record.gateway_transfer_id
            await session.commit()

        try:
            batch = await self._gateway.get_batch_transfer(
                batch_transfer_id
            )
            transfer = next(
                (
                    item
                    for item in (batch.get("transfers") or [])
                    if item.get("id") == transfer_id
                ),
                None,
            )
            if (
                batch.get("id") != batch_transfer_id
                or transfer is None
                or transfer.get("reference_number") != session_id
            ):
                raise SandboxVerificationError(
                    "TRANSFER_RECONCILIATION_MISMATCH",
                    "Batch transfer identifiers or reference did not match",
                )
            status = str(transfer.get("status") or "").lower()
        except SandboxVerificationError as exc:
            return await self._fail_session(
                session_id, exc.code, str(exc), audit_id
            )
        except Exception as exc:
            return await self._fail_session(
                session_id,
                "TRANSFER_RETRIEVAL_FAILED",
                str(exc),
                audit_id,
            )

        if status in {"success", "succeeded", "paid"}:
            return await self._verify_session(
                session_id, status, audit_id
            )
        if status in {
            "failed",
            "cancelled",
            "returned",
            "rejected",
        }:
            return await self._fail_session(
                session_id,
                "TRANSFER_FAILED",
                f"PayMongo transfer status: {status}",
                audit_id,
            )
        await self._update_audit(audit_id, "pending")
        return await self.get_session(session_id)

    async def expire_pending_sessions(self) -> int:
        now = _utcnow()
        async with self._db_factory() as session:
            result = await session.execute(
                update(SandboxSessionRecord)
                .where(
                    SandboxSessionRecord.state
                    == SandboxState.PENDING_CALLBACK.value,
                    SandboxSessionRecord.expires_at <= now,
                )
                .values(
                    state=SandboxState.TIMED_OUT.value,
                    completed_at=now,
                    error_code="CALLBACK_TIMEOUT",
                    error_message=(
                        "No verified PayMongo callback was received "
                        "before the session deadline"
                    ),
                )
            )
            await session.commit()
            return int(result.rowcount or 0)

    async def prune_completed_sessions(self) -> None:
        async with self._db_factory() as session:
            completed_ids = (
                await session.execute(
                    select(SandboxSessionRecord.id)
                    .where(
                        SandboxSessionRecord.state.in_(TERMINAL_STATES)
                    )
                    .order_by(
                        SandboxSessionRecord.completed_at.desc(),
                        SandboxSessionRecord.created_at.desc(),
                    )
                    .offset(self._config.retention_limit)
                )
            ).scalars().all()
            if not completed_ids:
                return
            await session.execute(
                delete(CallbackAuditRecord).where(
                    CallbackAuditRecord.session_id.in_(completed_ids)
                )
            )
            await session.execute(
                delete(SandboxSessionRecord).where(
                    SandboxSessionRecord.id.in_(completed_ids)
                )
            )
            await session.commit()

    async def _expiry_loop(self) -> None:
        while True:
            await asyncio.sleep(5)
            try:
                await self.expire_pending_sessions()
                await self.prune_completed_sessions()
            except Exception:
                logger.exception(
                    "E-wallet sandbox expiry maintenance failed"
                )

    async def _verify_session(
        self, session_id: str, gateway_status: str, audit_id: str
    ) -> dict:
        async with self._db_factory() as session:
            record = await session.get(SandboxSessionRecord, session_id)
            if record.state == SandboxState.PENDING_CALLBACK.value:
                record.state = SandboxState.VERIFIED.value
                record.gateway_status = gateway_status
                record.completed_at = _utcnow()
            audit = await session.get(CallbackAuditRecord, audit_id)
            audit.outcome = "verified"
            await session.commit()
            return self._serialize(record)

    async def _fail_session(
        self,
        session_id: str,
        code: str,
        message: str,
        audit_id: str,
    ) -> dict:
        async with self._db_factory() as session:
            record = await session.get(SandboxSessionRecord, session_id)
            if record.state == SandboxState.PENDING_CALLBACK.value:
                record.state = SandboxState.FAILED.value
                record.error_code = code
                record.error_message = message[:500]
                record.completed_at = _utcnow()
            audit = await session.get(CallbackAuditRecord, audit_id)
            audit.outcome = "failed"
            await session.commit()
            return self._serialize(record)

    async def _update_audit(self, audit_id: str, outcome: str) -> None:
        async with self._db_factory() as session:
            audit = await session.get(CallbackAuditRecord, audit_id)
            audit.outcome = outcome
            await session.commit()

    @staticmethod
    def _validate_payment(
        intent: dict,
        expected_intent_id: str,
        session_id: str,
        expected_amount: int,
        payment_id: str | None,
    ) -> None:
        attrs = intent.get("attributes") or {}
        if intent.get("id") != expected_intent_id:
            raise SandboxVerificationError(
                "PAYMENT_INTENT_MISMATCH",
                "Payment Intent identifier did not match",
            )
        if attrs.get("amount") != expected_amount:
            raise SandboxVerificationError(
                "PAYMENT_AMOUNT_MISMATCH", "Payment amount did not match"
            )
        if str(attrs.get("currency") or "").upper() != "PHP":
            raise SandboxVerificationError(
                "PAYMENT_CURRENCY_MISMATCH",
                "Payment currency was not PHP",
            )
        if attrs.get("status") != "succeeded":
            raise SandboxVerificationError(
                "PAYMENT_STATUS_MISMATCH",
                "Payment Intent was not succeeded",
            )
        if (attrs.get("metadata") or {}).get(
            "coinnect_transaction_id"
        ) != session_id:
            raise SandboxVerificationError(
                "PAYMENT_REFERENCE_MISMATCH",
                "Payment metadata reference did not match",
            )
        payment = next(
            (
                item
                for item in (attrs.get("payments") or [])
                if payment_id is None or item.get("id") == payment_id
            ),
            None,
        )
        if payment is None:
            raise SandboxVerificationError(
                "PAYMENT_NOT_FOUND", "Paid payment was not found"
            )
        payment_attrs = payment.get("attributes") or {}
        if payment_attrs.get("status") != "paid":
            raise SandboxVerificationError(
                "PAYMENT_STATUS_MISMATCH", "Payment was not paid"
            )
        if payment_attrs.get("amount") != expected_amount:
            raise SandboxVerificationError(
                "PAYMENT_AMOUNT_MISMATCH",
                "Paid amount did not match",
            )
        if str(payment_attrs.get("currency") or "").upper() != "PHP":
            raise SandboxVerificationError(
                "PAYMENT_CURRENCY_MISMATCH",
                "Paid currency was not PHP",
            )
        if (payment_attrs.get("source") or {}).get("type") != "qrph":
            raise SandboxVerificationError(
                "PAYMENT_SOURCE_MISMATCH",
                "Payment source was not QR Ph",
            )

    @staticmethod
    def _serialize(record: SandboxSessionRecord) -> dict:
        return {
            "transaction_id": record.id,
            "provider": record.provider,
            "direction": record.direction,
            "amount": record.amount,
            "state": record.state,
            "mobile_number": record.mobile_number,
            "account_name": record.account_name,
            "gateway_payment_intent_id": (
                record.gateway_payment_intent_id
            ),
            "gateway_batch_transfer_id": (
                record.gateway_batch_transfer_id
            ),
            "gateway_transfer_id": record.gateway_transfer_id,
            "gateway_status": record.gateway_status,
            "qr_image_url": record.qr_image_url,
            "test_url": record.test_url,
            "error_code": record.error_code,
            "error_message": record.error_message,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "expires_at": record.expires_at.isoformat(),
            "completed_at": (
                record.completed_at.isoformat()
                if record.completed_at
                else None
            ),
        }


class SandboxVerificationError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)
