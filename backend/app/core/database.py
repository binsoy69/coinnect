"""SQLite database engine and session management.

Uses SQLAlchemy async with aiosqlite for non-blocking database access.
"""

import logging
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


def get_engine():
    """Get or create the async engine singleton."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.db_url, echo=False)
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _migrate_schema(sync_conn):
            def table_columns(table_name: str) -> set[str]:
                result = sync_conn.execute(text(f"PRAGMA table_info({table_name})"))
                return {row[1] for row in result.fetchall()}

            transaction_columns = table_columns("transactions")
            if transaction_columns and "selected_dispense_counts" not in transaction_columns:
                logger.info("Migrating schema: adding selected_dispense_counts to transactions table")
                sync_conn.execute(text("ALTER TABLE transactions ADD COLUMN selected_dispense_counts JSON"))

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
