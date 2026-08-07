import pytest
from sqlalchemy import text, create_engine
from app.core.database import init_db


@pytest.mark.asyncio
async def test_init_db_adds_missing_selected_dispense_counts_column(tmp_path, monkeypatch):
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    # Create an old schema table without selected_dispense_counts
    sync_url = f"sqlite:///{db_file}"
    sync_engine = create_engine(sync_url)
    with sync_engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE transactions (
                id VARCHAR PRIMARY KEY,
                type VARCHAR NOT NULL,
                state VARCHAR,
                target_amount INTEGER,
                fee INTEGER,
                total_due INTEGER,
                inserted_amount INTEGER,
                dispensed_amount INTEGER
            )
        """))
        conn.commit()

        # Verify column is initially missing
        res = conn.execute(text("PRAGMA table_info(transactions)")).fetchall()
        cols = [r[1] for r in res]
        assert "selected_dispense_counts" not in cols

    # Patch settings to use the temporary database
    from app.core import config
    settings = config.get_settings()
    monkeypatch.setattr(settings, "db_url", db_url)

    # Force re-initialization of engine singleton
    import app.core.database as db_mod
    db_mod._engine = None

    # Run init_db
    await init_db()

    # Verify column was automatically added
    with sync_engine.connect() as conn:
        res = conn.execute(text("PRAGMA table_info(transactions)")).fetchall()
        cols = [r[1] for r in res]
        assert "selected_dispense_counts" in cols

    # Cleanup engine
    await db_mod.close_db()


@pytest.mark.asyncio
async def test_init_db_upgrades_legacy_gateway_events_without_replaying_rows(
    tmp_path, monkeypatch
):
    db_file = tmp_path / "test_gateway_migration.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    sync_engine = create_engine(f"sqlite:///{db_file}")

    with sync_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE gateway_events (
                id VARCHAR PRIMARY KEY,
                event_type VARCHAR NOT NULL,
                resource_id VARCHAR,
                payload JSON NOT NULL,
                processed_at DATETIME NOT NULL
            )
        """))
        conn.execute(
            text("""
                INSERT INTO gateway_events
                    (id, event_type, resource_id, payload, processed_at)
                VALUES
                    ('evt_legacy', 'payment.paid', 'pi_legacy', '{}',
                     '2026-01-02 03:04:05')
            """)
        )

    from app.core import config
    settings = config.get_settings()
    monkeypatch.setattr(settings, "db_url", db_url)

    import app.core.database as db_mod
    db_mod._engine = None
    db_mod._session_factory = None

    await init_db()

    from app.models.db_models import GatewayEventRecord

    async with db_mod.get_session_factory()() as session:
        session.add(
            GatewayEventRecord(
                id="evt_new_pending",
                event_type="payment.paid",
                resource_id="pi_new",
                payload={},
                processed=False,
            )
        )
        await session.commit()

    with sync_engine.connect() as conn:
        columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(gateway_events)"))
        }
        assert {
            "processed",
            "status",
            "attempt_count",
            "next_attempt_at",
            "lease_expires_at",
            "received_at",
            "processing_error",
        } <= columns

        row = conn.execute(
            text("""
                SELECT processed, status, attempt_count, received_at
                FROM gateway_events WHERE id = 'evt_legacy'
            """)
        ).one()
        assert row.processed == 1
        assert row.status == "PROCESSED"
        assert row.attempt_count == 0
        assert str(row.received_at) == "2026-01-02 03:04:05"

        table_info = conn.execute(text("PRAGMA table_info(gateway_events)")).fetchall()
        processed_at = next(row for row in table_info if row[1] == "processed_at")
        assert processed_at[3] == 0

        new_row = conn.execute(
            text("""
                SELECT status, processed_at, received_at
                FROM gateway_events WHERE id = 'evt_new_pending'
            """)
        ).one()
        assert new_row.status == "RECEIVED"
        assert new_row.processed_at is None
        assert new_row.received_at is not None

    await db_mod.close_db()


@pytest.mark.asyncio
async def test_init_db_preserves_unprocessed_gateway_events_for_inbox_retry(
    tmp_path, monkeypatch
):
    db_file = tmp_path / "test_partial_gateway_migration.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    sync_engine = create_engine(f"sqlite:///{db_file}")

    with sync_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE gateway_events (
                id VARCHAR PRIMARY KEY,
                event_type VARCHAR NOT NULL,
                resource_id VARCHAR,
                payload JSON NOT NULL,
                processed BOOLEAN NOT NULL,
                processing_error VARCHAR,
                processed_at DATETIME
            )
        """))
        conn.execute(
            text("""
                INSERT INTO gateway_events
                    (id, event_type, resource_id, payload, processed, processing_error)
                VALUES
                    ('evt_pending', 'payment.paid', 'pi_pending', '{}', 0, 'interrupted')
            """)
        )

    from app.core import config
    settings = config.get_settings()
    monkeypatch.setattr(settings, "db_url", db_url)

    import app.core.database as db_mod
    db_mod._engine = None
    db_mod._session_factory = None

    await init_db()

    with sync_engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT processed, status, attempt_count, received_at, processing_error
                FROM gateway_events WHERE id = 'evt_pending'
            """)
        ).one()
        assert row.processed == 0
        assert row.status == "RECEIVED"
        assert row.attempt_count == 0
        assert row.received_at is not None
        assert row.processing_error == "interrupted"

    await db_mod.close_db()
