import pytest
from sqlalchemy import text, create_engine
from app.core.database import init_db, get_engine


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
