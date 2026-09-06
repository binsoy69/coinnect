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
from app.models.db_models import (ClaimRecord, ClaimStatus, ForexClaimTicket, ForexClaimItem, TransactionRecord, ForexSession)
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

    async def create_forex(self, session, record, items, reason):
        ticket = (await session.execute(select(ForexClaimTicket).where(ForexClaimTicket.transaction_id == record.id))).scalar_one_or_none()
        if ticket is None:
            ticket = ForexClaimTicket(id=_ticket_code(), transaction_id=record.id, reason=reason)
            session.add(ticket)
            await session.flush()
        existing = {i.kind: i for i in (await session.execute(select(ForexClaimItem).where(ForexClaimItem.ticket_id == ticket.id))).scalars()}
        for data in items:
            item = existing.pop(data["kind"], None)
            if item is None:
                session.add(ForexClaimItem(id=str(uuid.uuid4()), ticket_id=ticket.id, **data))
            elif item.status != "RESOLVED":
                for key, value in data.items():
                    setattr(item, key, value)
        for item in existing.values():
            if item.status != "RESOLVED":
                item.amount = 0
                item.status = "OPEN"
        record.claim_ticket_code = ticket.id
        return ticket.id

    async def get_forex(self, transaction_id=None, ticket_id=None, session=None):
        if session is None:
            async with self._db_factory() as owned:
                return await self.get_forex(transaction_id, ticket_id, session=owned)
        statement = select(ForexClaimTicket)
        statement = statement.where(ForexClaimTicket.id == ticket_id) if ticket_id else statement.where(ForexClaimTicket.transaction_id == transaction_id)
        ticket = (await session.execute(statement)).scalar_one_or_none()
        if ticket is None:
            return None
        items = (await session.execute(select(ForexClaimItem).where(ForexClaimItem.ticket_id == ticket.id))).scalars().all()
        return {"claim_ticket_code": ticket.id, "transaction_id": ticket.transaction_id,
            "source_kind": "FOREX", "reason_message": ticket.reason,
            "created_at": ticket.created_at.isoformat(),
            "status": "RESOLVED" if all(i.status == "RESOLVED" for i in items) else "PROVISIONAL" if any(i.status == "PROVISIONAL" for i in items) else "OPEN",
            "items": [{"id": i.id, "kind": i.kind, "currency": i.currency, "amount": i.amount,
                       "status": i.status, "resolution_notes": i.resolution_notes} for i in items]}

    async def resolve_forex_item(self, ticket_id, item_id, operator, notes):
        if not notes.strip():
            raise ValueError("Settlement notes are required")
        async with self._db_factory() as session:
            ticket = await session.get(ForexClaimTicket, ticket_id)
            item = await session.get(ForexClaimItem, item_id)
            if not ticket or not item or item.ticket_id != ticket_id:
                raise ValueError("Claim item not found")
            if item.status == "PROVISIONAL":
                raise ValueError("Reconcile physical evidence before settling this item")
            if item.status != "RESOLVED":
                meta = await session.get(ForexSession, ticket.transaction_id)
                if meta:
                    meta.revision += 1
                item.status = "RESOLVED"
                item.resolved_at = datetime.utcnow()
                item.resolved_by = operator
                item.resolution_notes = notes
                await session.flush()
                items = (await session.execute(select(ForexClaimItem).where(ForexClaimItem.ticket_id == ticket_id))).scalars().all()
                if all(i.status == "RESOLVED" for i in items):
                    record = await session.get(TransactionRecord, ticket.transaction_id)
                    record.state = "RESOLVED"
                    record.resolved_at = datetime.utcnow()
                    record.resolved_by = operator
                    record.resolution_notes = notes
                await session.commit()
        return await self.get_forex(ticket_id=ticket_id)

    async def forex_legacy_audit(self):
        async with self._db_factory() as session:
            records = (await session.execute(select(TransactionRecord).where(TransactionRecord.type.like("forex-%")))).scalars().all()
            result = []
            for record in records:
                if await session.get(ForexSession, record.id):
                    continue
                result.append({"transaction_id": record.id, "state": record.state,
                    "claim_ticket_code": record.claim_ticket_code,
                    "reason": "Legacy forex accounting requires review; scalar totals may mix currencies",
                    "evidence": {"input_currency": record.from_currency, "output_currency": record.to_currency,
                                 "inserted": record.inserted_amount, "target": record.target_amount,
                                 "plan": record.dispense_plan, "result": record.dispense_result},
                    "proposed_action": "Reconstruct per-currency obligations from physical operation evidence; do not settle scalar totals"})
            return result

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
            if existing is not None and (existing.status == ClaimStatus.RESOLVED.value or existing.resolved_at is not None):
                return existing
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
            audience = {"kiosk_session_id": getattr(record, "session_id", None) or "legacy-unavailable"} if source_kind == "EWALLET" else {}
            await self._ws.broadcast(WSEvent(type=WSEventType.CLAIM_TICKET, payload=payload), **audience)
        except Exception as exc:
            logger.error("Claim %s broadcast failed: %s", existing.id, exc, exc_info=True)
        if created and self._receipt is not None and record is not None:
            try:
                await self._receipt.print_claim_ticket(
                    record,
                    claim_code=existing.claim_ticket_code,
                    shortfall=amount,
                    error_reason=reason_message or reason_code,
                    provisional=provisional,
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
