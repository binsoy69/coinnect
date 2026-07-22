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
            result = sync_conn.execute(text("PRAGMA table_info(transactions)"))
            columns = [row[1] for row in result.fetchall()]
            if columns and "selected_dispense_counts" not in columns:
                logger.info("Migrating schema: adding selected_dispense_counts to transactions table")
                sync_conn.execute(text("ALTER TABLE transactions ADD COLUMN selected_dispense_counts JSON"))

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
