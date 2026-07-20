"""Script to populate balanced inventory across dispensers and bill storage in coinnect.db."""

import asyncio
import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.core.database import get_session_factory, init_db
from app.models.db_models import InventoryBalance

# Target initial balanced counts for standard operation:
# - DISPENSERS: 50 units per denomination (so dispensing always succeeds)
# - BILL STORAGE: 5 units per slot (so storage has 95% capacity available to accept bills)

DISPENSER_BILL_DENOMS = [
    "PHP_20", "PHP_50", "PHP_100", "PHP_200", "PHP_500", "PHP_1000",
    "USD_10", "USD_50", "EUR_5", "EUR_10",
]
DISPENSER_COIN_DENOMS = ["PHP_1", "PHP_5", "PHP_10", "PHP_20"]
STORAGE_SLOT_DENOMS = [
    "PHP_20", "PHP_50", "PHP_100", "PHP_200", "PHP_500", "PHP_1000",
    "USD", "EUR",
]


async def set_balanced_inventory():
    await init_db()
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(InventoryBalance))
        existing_rows = {
            (r.location, r.denomination): r for r in result.scalars().all()
        }

        # 1. Populate Bill Dispenser inventory (50 bills per denom)
        for denom in DISPENSER_BILL_DENOMS:
            key = ("BILL_DISPENSER", denom)
            if key in existing_rows:
                existing_rows[key].count = 50
            else:
                session.add(InventoryBalance(location="BILL_DISPENSER", denomination=denom, count=50))

        # 2. Populate Coin Dispenser inventory (50 coins per denom)
        for denom in DISPENSER_COIN_DENOMS:
            key = ("COIN_DISPENSER", denom)
            if key in existing_rows:
                existing_rows[key].count = 50
            else:
                session.add(InventoryBalance(location="COIN_DISPENSER", denomination=denom, count=50))

        # 3. Populate Bill Storage inventory (5 bills per slot, leaving 95 slots open to accept bills)
        for denom in STORAGE_SLOT_DENOMS:
            key = ("BILL_STORAGE", denom)
            if key in existing_rows:
                existing_rows[key].count = 5
            else:
                session.add(InventoryBalance(location="BILL_STORAGE", denomination=denom, count=5))

        await session.commit()
        print("Successfully updated database to balanced inventory!")
        print("- BILL_DISPENSER: 50 bills for all denominations (ready to dispense)")
        print("- COIN_DISPENSER: 50 coins for all denominations (ready to dispense)")
        print("- BILL_STORAGE: 5 bills per slot (ready to accept up to 95 more bills per slot)")


if __name__ == "__main__":
    asyncio.run(set_balanced_inventory())
