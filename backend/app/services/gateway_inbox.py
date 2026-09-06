"""Durable SQLite-backed PayMongo event inbox worker."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update

from app.models.db_models import GatewayEventRecord

logger = logging.getLogger(__name__)

class GatewayInboxWorker:
    def __init__(self, db_session_factory, orchestrator, settings):
        self._db_factory = db_session_factory
        self._orchestrator = orchestrator
        self._settings = settings
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        await self._recover_expired_leases()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while self._running:
            try:
                await self._recover_expired_leases()
                event_id = await self._lease_next()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Gateway inbox lease failed; retrying")
                await asyncio.sleep(1)
                continue
            if event_id is None:
                await asyncio.sleep(1)
                continue
            try:
                async with self._db_factory() as session:
                    row = await session.get(GatewayEventRecord, event_id)
                    payload = dict(row.payload)
                await self._orchestrator.process_gateway_event(
                    payload, persisted_event_id=event_id
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Gateway inbox event %s failed: %s", event_id, exc, exc_info=True)
                try:
                    await self._schedule_retry(event_id, str(exc))
                except Exception:
                    logger.exception("Gateway retry scheduling failed; lease recovery will retry")

    async def _lease_next(self) -> str | None:
        now = datetime.utcnow()
        async with self._db_factory() as session:
            row = (
                await session.execute(
                    select(GatewayEventRecord)
                    .where(
                        GatewayEventRecord.status.in_({"RECEIVED", "RETRY"}),
                        or_(
                            GatewayEventRecord.next_attempt_at.is_(None),
                            GatewayEventRecord.next_attempt_at <= now,
                        ),
                    )
                    .order_by(GatewayEventRecord.received_at, GatewayEventRecord.id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            claimed = await session.execute(
                update(GatewayEventRecord)
                .where(
                    GatewayEventRecord.id == row.id,
                    GatewayEventRecord.status.in_({"RECEIVED", "RETRY"}),
                )
                .values(
                    status="PROCESSING",
                    attempt_count=GatewayEventRecord.attempt_count + 1,
                    lease_expires_at=now + timedelta(
                        seconds=self._settings.paymongo_webhook_lease_seconds
                    ),
                )
            )
            await session.commit()
            return row.id if claimed.rowcount == 1 else None

    async def _schedule_retry(self, event_id: str, error: str) -> None:
        async with self._db_factory() as session:
            row = await session.get(GatewayEventRecord, event_id)
            if row is None or row.processed:
                return
            fast_retries = tuple(self._settings.paymongo_webhook_fast_retry_seconds)
            index = min(max(row.attempt_count - 1, 0), len(fast_retries) - 1)
            escalate = row.attempt_count == len(fast_retries)
            payload = dict(row.payload)
            delay = (
                fast_retries[index]
                if row.attempt_count <= len(fast_retries)
                else self._settings.paymongo_webhook_reconciliation_interval_seconds
            )
            row.status = "RETRY"
            row.processing_error = error[:1000]
            row.next_attempt_at = datetime.utcnow() + timedelta(seconds=delay)
            row.lease_expires_at = None
            await session.commit()
        if escalate:
            await self._orchestrator.escalate_gateway_event(payload, error)

    async def _recover_expired_leases(self) -> None:
        now = datetime.utcnow()
        async with self._db_factory() as session:
            await session.execute(
                update(GatewayEventRecord)
                .where(
                    GatewayEventRecord.status == "PROCESSING",
                    GatewayEventRecord.lease_expires_at < now,
                )
                .values(status="RETRY", next_attempt_at=now, lease_expires_at=None)
            )
            await session.commit()
