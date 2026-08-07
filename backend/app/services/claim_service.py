"""Centralized, durable customer-claim creation and reconciliation."""

from __future__ import annotations

import secrets
import string
import uuid
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.ws import ConnectionManager
from app.models.db_models import ClaimRecord, ClaimStatus
from app.models.events import WSEvent, WSEventType

logger = logging.getLogger(__name__)


def _ticket_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


class ClaimService:
    def __init__(
        self,
        db_session_factory: async_sessionmaker,
        ws_manager: ConnectionManager,
        receipt_service=None,
    ):
        self._db_factory = db_session_factory
        self._ws = ws_manager
        self._receipt = receipt_service

    async def create(
        self,
        *,
        source_kind: str,
        transaction_id: str,
        claim_kind: str,
        amount: int,
        currency: str,
        reason_code: str,
        reason_message: str | None = None,
        confirmed_dispensed_amount: int = 0,
        ambiguous_amount: int = 0,
        provisional: bool = False,
        record=None,
        session: AsyncSession | None = None,
    ) -> ClaimRecord:
        if amount < 0 or confirmed_dispensed_amount < 0 or ambiguous_amount < 0:
            raise ValueError("Claim monetary values cannot be negative")
        owns_session = session is None
        if owns_session:
            session = self._db_factory()
        try:
            existing = (
                await session.execute(
                    select(ClaimRecord).where(
                        ClaimRecord.source_kind == source_kind,
                        ClaimRecord.transaction_id == transaction_id,
                        ClaimRecord.claim_kind == claim_kind,
                    )
                )
            ).scalar_one_or_none()
            created = existing is None
            if created:
                existing = ClaimRecord(
                    id=str(uuid.uuid4()),
                    claim_ticket_code=_ticket_code(),
                    source_kind=source_kind,
                    transaction_id=transaction_id,
                    claim_kind=claim_kind,
                    status=(ClaimStatus.PROVISIONAL.value if provisional else ClaimStatus.OPEN.value),
                    amount=amount,
                    currency=currency,
                    confirmed_dispensed_amount=confirmed_dispensed_amount,
                    ambiguous_amount=ambiguous_amount,
                    reason_code=reason_code,
                    reason_message=reason_message,
                )
                session.add(existing)
            else:
                existing.status = ClaimStatus.PROVISIONAL.value if provisional else ClaimStatus.OPEN.value
                existing.amount = amount
                existing.currency = currency
                existing.confirmed_dispensed_amount = confirmed_dispensed_amount
                existing.ambiguous_amount = ambiguous_amount
                existing.reason_code = reason_code
                existing.reason_message = reason_message
                existing.updated_at = datetime.utcnow()
            if record is not None:
                record.claim_ticket_code = existing.claim_ticket_code
                record.state = "CLAIM_REQUIRED"
                record.error_code = reason_code
                record.error_message = reason_message
                record.completed_at = datetime.utcnow()
            await session.commit()
            await session.refresh(existing)
        finally:
            if owns_session:
                await session.close()

        payload = self.serialize(existing)
        payload["state"] = "CLAIM_REQUIRED"
        try:
            await self._ws.broadcast(WSEvent(type=WSEventType.CLAIM_TICKET, payload=payload))
        except Exception as exc:
            logger.error("Claim %s broadcast failed: %s", existing.id, exc, exc_info=True)
        if created and self._receipt is not None and record is not None:
            try:
                await self._receipt.print_claim_ticket(
                    record,
                    claim_code=existing.claim_ticket_code,
                    shortfall=amount,
                    error_reason=reason_message or reason_code,
                )
            except Exception as exc:
                logger.error("Claim %s printing failed: %s", existing.id, exc, exc_info=True)
        return existing

    @staticmethod
    def serialize(claim: ClaimRecord) -> dict:
        return {
            "claim_ticket_code": claim.claim_ticket_code,
            "transaction_id": claim.transaction_id,
            "source_kind": claim.source_kind,
            "claim_kind": claim.claim_kind,
            "status": claim.status,
            "amount": claim.amount,
            "currency": claim.currency,
            "confirmed_dispensed_amount": claim.confirmed_dispensed_amount,
            "ambiguous_amount": claim.ambiguous_amount,
            "reason_code": claim.reason_code,
            "reason_message": claim.reason_message,
            "created_at": claim.created_at.isoformat() if claim.created_at else None,
        }
