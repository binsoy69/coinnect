"""SQLite database engine and session management.

Uses SQLAlchemy async with aiosqlite for non-blocking database access.
"""

import logging
import asyncio
import sqlite3
from pathlib import Path
from datetime import datetime
from sqlalchemy import event
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None


def _backup_before_forex_migration(database: str | None) -> None:
    if not database or database == ":memory:" or not Path(database).is_file():
        return
    with sqlite3.connect(database) as source:
        if source.execute("SELECT 1 FROM sqlite_master WHERE name='forex_sessions'").fetchone():
            return
        destination = f"{database}.{datetime.utcnow():%Y%m%dT%H%M%S%f}.pre-forex.backup"
        with open(destination, "xb"):
            pass
        with sqlite3.connect(destination) as backup:
            source.backup(backup)


def _backup_before_wallet_migration(database: str | None) -> None:
    """Use SQLite's backup API so committed WAL data is included in the copy."""
    if not database or database == ":memory:" or not Path(database).is_file():
        return
    with sqlite3.connect(database) as source:
        columns = {row[1] for row in source.execute("PRAGMA table_info(ewallet_transactions)")}
        intake_columns = {row[1] for row in source.execute("PRAGMA table_info(ewallet_intakes)")}
        if not columns or ("gateway_work" in columns and "resolution_notes" in intake_columns):
            return
        destination = f"{database}.{datetime.utcnow():%Y%m%dT%H%M%S%f}.pre-ewallet.backup"
        # Exclusive creation prevents an existing backup being overwritten.
        with open(destination, "xb"):
            pass
        with sqlite3.connect(destination) as backup:
            source.backup(backup)
        logger.info("Saved pre-migration database backup: %s", destination)


def get_engine():
    """Get or create the async engine singleton."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.db_url, echo=False)
        @event.listens_for(_engine.sync_engine, "connect")
        def durable_sqlite(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=FULL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory singleton."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def init_db() -> None:
    """Create all tables and perform lightweight schema migrations."""
    from sqlalchemy import text
    from app.models.db_models import Base

    engine = get_engine()
    await asyncio.to_thread(_backup_before_wallet_migration, engine.url.database)
    await asyncio.to_thread(_backup_before_forex_migration, engine.url.database)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _migrate_schema(sync_conn):
            def table_columns(table_name: str) -> set[str]:
                result = sync_conn.execute(text(f"PRAGMA table_info({table_name})"))
                return {row[1] for row in result.fetchall()}

            transaction_columns = table_columns("transactions")
            ewallet_columns = table_columns("ewallet_transactions")
            for name in ("ewallet_intakes", "ewallet_coin_sessions"):
                if "resolution_notes" not in table_columns(name):
                    sync_conn.execute(text(f"ALTER TABLE {name} ADD COLUMN resolution_notes VARCHAR"))
            additions = {
                "version": "INTEGER NOT NULL DEFAULT 1",
                "session_id": "VARCHAR", "request_key": "VARCHAR",
                "policy_version": "VARCHAR", "deadline": "DATETIME",
                "heartbeat_at": "DATETIME", "submission_at": "DATETIME",
                "customer_present": "BOOLEAN NOT NULL DEFAULT 0",
                "change_due": "INTEGER NOT NULL DEFAULT 0",
                "change_dispensed": "INTEGER NOT NULL DEFAULT 0",
                "retained_amount": "INTEGER NOT NULL DEFAULT 0",
                "refunded_fee": "INTEGER NOT NULL DEFAULT 0",
                "wallet_credited": "INTEGER NOT NULL DEFAULT 0",
                "intake_counts": "JSON NOT NULL DEFAULT '{}'",
                "gateway_work": "JSON NOT NULL DEFAULT '{}'",
            }
            for column, definition in additions.items():
                if column not in ewallet_columns:
                    sync_conn.execute(text(f"ALTER TABLE ewallet_transactions ADD COLUMN {column} {definition}"))
            if "wallet_credited" not in ewallet_columns:
                sync_conn.execute(text("UPDATE ewallet_transactions SET wallet_credited = transfer_amount WHERE direction = 'cash-in' AND state = 'COMPLETE'"))
                sync_conn.execute(text("UPDATE ewallet_transactions SET state = 'CLAIM_REQUIRED' WHERE direction = 'cash-in' AND state IN ('FAILED', 'CANCELLED') AND inserted_amount > 0 AND resolved_at IS NULL"))
            sync_conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ewallet_request_key ON ewallet_transactions (request_key)"))
            if transaction_columns and "selected_dispense_counts" not in transaction_columns:
                logger.info("Migrating schema: adding selected_dispense_counts to transactions table")
                sync_conn.execute(text("ALTER TABLE transactions ADD COLUMN selected_dispense_counts JSON"))

            if transaction_columns and "converter_metadata" not in transaction_columns:
                logger.info("Migrating schema: adding converter_metadata to transactions table")
                sync_conn.execute(text("ALTER TABLE transactions ADD COLUMN converter_metadata JSON"))

            gateway_columns = table_columns("gateway_events")
            if not gateway_columns:
                return

            # gateway_events originally served only as a replay-protection log.
            # The durable inbox added scheduling and lease fields later, so old
            # installations need these columns added without replaying history.
            inbox_columns = {
                "processed": "BOOLEAN NOT NULL DEFAULT 0",
                "status": "VARCHAR NOT NULL DEFAULT 'RECEIVED'",
                "attempt_count": "INTEGER NOT NULL DEFAULT 0",
                "next_attempt_at": "DATETIME",
                "lease_expires_at": "DATETIME",
                "received_at": "DATETIME",
                "processing_error": "VARCHAR",
            }
            added_columns = set()
            for column, definition in inbox_columns.items():
                if column not in gateway_columns:
                    logger.info("Migrating schema: adding %s to gateway_events table", column)
                    sync_conn.execute(
                        text(f"ALTER TABLE gateway_events ADD COLUMN {column} {definition}")
                    )
                    added_columns.add(column)

            if "processed" in added_columns:
                # Rows from the original replay-protection table represent
                # callbacks that already completed successfully.
                sync_conn.execute(text("UPDATE gateway_events SET processed = 1"))

            if "status" in added_columns:
                sync_conn.execute(
                    text(
                        "UPDATE gateway_events "
                        "SET status = CASE WHEN processed = 1 THEN 'PROCESSED' ELSE 'RECEIVED' END"
                    )
                )

            if "received_at" in added_columns:
                sync_conn.execute(
                    text(
                        "UPDATE gateway_events "
                        "SET received_at = COALESCE(processed_at, CURRENT_TIMESTAMP)"
                    )
                )

            gateway_info = sync_conn.execute(
                text("PRAGMA table_info(gateway_events)")
            ).fetchall()
            processed_at = next(
                (row for row in gateway_info if row[1] == "processed_at"), None
            )
            if processed_at is not None and processed_at[3]:
                logger.info(
                    "Migrating schema: making gateway_events.processed_at nullable"
                )
                # SQLite cannot remove a NOT NULL constraint with ALTER COLUMN.
                # Rebuild the table after populating every newly added field.
                sync_conn.execute(text("""
                    CREATE TABLE gateway_events_migrated (
                        id VARCHAR NOT NULL PRIMARY KEY,
                        event_type VARCHAR NOT NULL,
                        resource_id VARCHAR,
                        payload JSON NOT NULL,
                        processed BOOLEAN NOT NULL,
                        status VARCHAR NOT NULL,
                        attempt_count INTEGER NOT NULL,
                        next_attempt_at DATETIME,
                        lease_expires_at DATETIME,
                        received_at DATETIME NOT NULL,
                        processing_error VARCHAR,
                        processed_at DATETIME
                    )
                """))
                sync_conn.execute(text("""
                    INSERT INTO gateway_events_migrated (
                        id, event_type, resource_id, payload, processed, status,
                        attempt_count, next_attempt_at, lease_expires_at,
                        received_at, processing_error, processed_at
                    )
                    SELECT
                        id, event_type, resource_id, payload, processed, status,
                        attempt_count, next_attempt_at, lease_expires_at,
                        received_at, processing_error, processed_at
                    FROM gateway_events
                """))
                sync_conn.execute(text("DROP TABLE gateway_events"))
                sync_conn.execute(
                    text("ALTER TABLE gateway_events_migrated RENAME TO gateway_events")
                )

        await conn.run_sync(_migrate_schema)

    logger.info("Database tables initialized")


async def close_db() -> None:
    """Dispose engine. Called during app shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine disposed")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for dependency injection."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
