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


@pytest.mark.asyncio
async def test_init_db_adds_converter_metadata_and_tables(tmp_path, monkeypatch):
    db_file = tmp_path / "test_converter_migration.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    sync_engine = create_engine(f"sqlite:///{db_file}")

    # Create an old schema table with existing data
    with sync_engine.begin() as conn:
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
        conn.execute(text("""
            INSERT INTO transactions (id, type, state, target_amount, fee, total_due, inserted_amount, dispensed_amount)
            VALUES ('tx_legacy_1', 'bill-to-bill', 'COMPLETE', 100, 5, 100, 100, 95)
        """))

        # Verify converter_metadata is initially missing
        res = conn.execute(text("PRAGMA table_info(transactions)")).fetchall()
        cols = [r[1] for r in res]
        assert "converter_metadata" not in cols

    from app.core import config
    settings = config.get_settings()
    monkeypatch.setattr(settings, "db_url", db_url)

    import app.core.database as db_mod
    db_mod._engine = None
    db_mod._session_factory = None

    # First migration run
    await init_db()

    # Second migration run (test idempotence)
    await init_db()

    with sync_engine.connect() as conn:
        # Verify columns in transactions table
        res = conn.execute(text("PRAGMA table_info(transactions)")).fetchall()
        cols = [r[1] for r in res]
        assert "converter_metadata" in cols
        assert "selected_dispense_counts" in cols

        # Verify existing row preserved
        row = conn.execute(text("SELECT id, type, converter_metadata FROM transactions WHERE id = 'tx_legacy_1'")).one()
        assert row.id == "tx_legacy_1"
        assert row.type == "bill-to-bill"
        assert row.converter_metadata is None

        # Verify new converter tables exist
        tables_res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = {r[0] for r in tables_res}
        assert "converter_quotes" in table_names
        assert "converter_intake_operations" in table_names
        assert "converter_coin_sessions" in table_names

    # Test persistence of new models via async session
    from app.models.db_models import ConverterQuote, ConverterIntakeOperation, ConverterCoinSession
    from datetime import datetime, timezone, timedelta

    async with db_mod.get_session_factory()() as session:
        quote = ConverterQuote(
            id="quote-123",
            transaction_id="tx-123",
            service_type="bill-to-bill",
            input_amount=100,
            fee=5,
            total_due=100,
            payout_amount=95,
            items=[{"denom": "PHP_50", "denom_type": "bill", "count": 1, "value": 50}],
            is_substitution=False,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=120)
        )
        session.add(quote)

        intake_op = ConverterIntakeOperation(
            id="intake-op-1",
            transaction_id="tx-123",
            denomination="PHP_100",
            value=100,
            state="PREPARED",
            inventory_credited=False,
            transaction_credited=False
        )
        session.add(intake_op)

        coin_session = ConverterCoinSession(
            session_id=1,
            transaction_id="tx-123",
            state="ACTIVE",
            cursor_php_1=0,
            cursor_php_5=0,
            cursor_php_10=0,
            cursor_php_20=0
        )
        session.add(coin_session)
        await session.commit()

    async with db_mod.get_session_factory()() as session:
        fetched_quote = await session.get(ConverterQuote, "quote-123")
        assert fetched_quote is not None
        assert fetched_quote.payout_amount == 95

        fetched_op = await session.get(ConverterIntakeOperation, "intake-op-1")
        assert fetched_op is not None
        assert fetched_op.state == "PREPARED"

        from sqlalchemy import select
        res = await session.execute(select(ConverterCoinSession).where(ConverterCoinSession.session_id == 1))
        fetched_cs = res.scalar_one_or_none()
        assert fetched_cs is not None
        assert fetched_cs.state == "ACTIVE"

    await db_mod.close_db()
