"""Script to inspect and adjust inventory counts in coinnect.db."""

import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.core.database import get_session_factory, init_db
from app.models.db_models import InventoryBalance


async def inspect_and_reset(storage_count: int = 5, dispenser_count: int = 50):
    await init_db()
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(InventoryBalance))
        balances = result.scalars().all()
        print("=== Current Inventory Balances ===")
        for b in balances:
            print(f"  [{b.location}] {b.denomination}: {b.count}")
            if b.location == "BILL_STORAGE":
                b.count = storage_count
            elif b.location in ("BILL_DISPENSER", "COIN_DISPENSER"):
                b.count = dispenser_count

        await session.commit()
        print(f"\nSuccessfully set BILL_STORAGE to {storage_count} and DISPENSERS to {dispenser_count}.")


if __name__ == "__main__":
    asyncio.run(inspect_and_reset(storage_count=5, dispenser_count=50))
