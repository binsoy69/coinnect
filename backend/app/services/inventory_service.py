"""Persistent inventory balances and append-only adjustment history."""

from enum import Enum
from typing import Iterable

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.constants import BillDenom
from app.models.db_models import InventoryAdjustment, InventoryBalance
from app.services.machine_status import MachineStatus


class InventoryLocation(str, Enum):
    BILL_DISPENSER = "BILL_DISPENSER"
    COIN_DISPENSER = "COIN_DISPENSER"
    BILL_STORAGE = "BILL_STORAGE"


class InventoryUpdate(BaseModel):
    location: InventoryLocation
    denomination: str
    count: int = Field(ge=0)


BILL_DISPENSER_DENOMS = tuple(denom.value for denom in BillDenom)
COIN_DISPENSER_DENOMS = ("PHP_1", "PHP_5", "PHP_10", "PHP_20")
BILL_STORAGE_DENOMS = (
    "PHP_20",
    "PHP_50",
    "PHP_100",
    "PHP_200",
    "PHP_500",
    "PHP_1000",
    "USD",
    "EUR",
)
VALID_INVENTORY = {
    InventoryLocation.BILL_DISPENSER: BILL_DISPENSER_DENOMS,
    InventoryLocation.COIN_DISPENSER: COIN_DISPENSER_DENOMS,
    InventoryLocation.BILL_STORAGE: BILL_STORAGE_DENOMS,
}
ADMIN_REASONS = {"REFILL", "PHYSICAL_COUNT", "CORRECTION"}


class InventoryService:
    def __init__(
        self,
        db_session_factory: async_sessionmaker,
        machine_status: MachineStatus,
    ):
        self._db_factory = db_session_factory
        self.machine_status = machine_status
        self.settings = machine_status._settings

    async def initialize(self) -> None:
        async with self._db_factory() as session:
            rows = (await session.execute(select(InventoryBalance))).scalars().all()
            existing = {(row.location, row.denomination) for row in rows}
            for location, denominations in VALID_INVENTORY.items():
                for denomination in denominations:
                    if (location.value, denomination) not in existing:
                        session.add(
                            InventoryBalance(
                                location=location.value,
                                denomination=denomination,
                                count=0,
                            )
                        )
            await session.commit()
        await self._refresh_runtime()

    async def apply_admin_updates(
        self,
        updates: Iterable[InventoryUpdate],
        reason: str,
        session_id: str,
        note: str | None = None,
    ) -> None:
        updates = list(updates)
        if not updates:
            raise ValueError("At least one inventory update is required")
        if reason not in ADMIN_REASONS:
            raise ValueError("Invalid adjustment reason")
        self._validate_updates(updates)

        async with self._db_factory() as session:
            for update in updates:
                row = await self._get_balance(
                    session, update.location, update.denomination
                )
                if row.count == update.count:
                    continue
                old_count = row.count
                row.count = update.count
                session.add(
                    InventoryAdjustment(
                        location=update.location.value,
                        denomination=update.denomination,
                        old_count=old_count,
                        new_count=update.count,
                        delta=update.count - old_count,
                        reason=reason,
                        source="ADMIN",
                        note=note,
                        session_id=session_id,
                    )
                )
            await session.commit()
        await self._refresh_runtime()
        self.machine_status.set_inventory_consistent(True)

    async def adjust(
        self,
        location: InventoryLocation,
        denomination: str,
        delta: int,
        reason: str,
        reference_id: str | None = None,
    ) -> None:
        self._validate_key(location, denomination)
        async with self._db_factory() as session:
            row = await self._get_balance(session, location, denomination)
            new_count = row.count + delta
            if new_count < 0:
                raise ValueError("Insufficient persisted inventory")
            old_count = row.count
            row.count = new_count
            session.add(
                InventoryAdjustment(
                    location=location.value,
                    denomination=denomination,
                    old_count=old_count,
                    new_count=new_count,
                    delta=delta,
                    reason=reason,
                    source="SYSTEM",
                    reference_id=reference_id,
                )
            )
            await session.commit()
        await self._refresh_runtime()

    async def reserve(
        self,
        quantities: dict[tuple[str, str], int],
        reference_id: str | None = None,
    ) -> None:
        await self._apply_deltas(
            {key: -count for key, count in quantities.items()},
            reason="DISPENSE_RESERVED",
            reference_id=reference_id,
        )

    async def restore(
        self,
        quantities: dict[tuple[str, str], int],
        reference_id: str | None = None,
    ) -> None:
        await self._apply_deltas(
            quantities,
            reason="DISPENSE_RECONCILED",
            reference_id=reference_id,
        )

    async def list_adjustments(
        self, source: str | None = None, limit: int = 50
    ) -> list[InventoryAdjustment]:
        async with self._db_factory() as session:
            statement = select(InventoryAdjustment)
            if source:
                statement = statement.where(InventoryAdjustment.source == source)
            statement = statement.order_by(
                InventoryAdjustment.created_at.desc(),
                InventoryAdjustment.id.desc(),
            ).limit(limit)
            return list((await session.execute(statement)).scalars().all())

    async def _apply_deltas(
        self,
        deltas: dict[tuple[str, str], int],
        reason: str,
        reference_id: str | None,
    ) -> None:
        async with self._db_factory() as session:
            pending = []
            for (location_value, denomination), delta in deltas.items():
                location = InventoryLocation(location_value)
                self._validate_key(location, denomination)
                row = await self._get_balance(session, location, denomination)
                new_count = row.count + delta
                if new_count < 0:
                    raise ValueError("Insufficient persisted inventory")
                pending.append((row, location, denomination, delta, new_count))
            for row, location, denomination, delta, new_count in pending:
                old_count = row.count
                row.count = new_count
                session.add(
                    InventoryAdjustment(
                        location=location.value,
                        denomination=denomination,
                        old_count=old_count,
                        new_count=new_count,
                        delta=delta,
                        reason=reason,
                        source="SYSTEM",
                        reference_id=reference_id,
                    )
                )
            await session.commit()
        await self._refresh_runtime()

    async def _refresh_runtime(self) -> None:
        async with self._db_factory() as session:
            rows = (await session.execute(select(InventoryBalance))).scalars().all()
        grouped = {location.value: {} for location in InventoryLocation}
        for row in rows:
            grouped[row.location][row.denomination] = row.count
        self.machine_status.set_dispenser_counts(
            grouped[InventoryLocation.BILL_DISPENSER.value]
        )
        self.machine_status.set_coin_counts(
            grouped[InventoryLocation.COIN_DISPENSER.value]
        )
        self.machine_status.set_storage_counts(
            grouped[InventoryLocation.BILL_STORAGE.value]
        )

    def _validate_updates(self, updates: list[InventoryUpdate]) -> None:
        seen = set()
        for update in updates:
            self._validate_key(update.location, update.denomination)
            key = (update.location, update.denomination)
            if key in seen:
                raise ValueError("Duplicate inventory update")
            seen.add(key)

    @staticmethod
    def _validate_key(
        location: InventoryLocation, denomination: str
    ) -> None:
        if denomination not in VALID_INVENTORY[location]:
            raise ValueError(
                f"Invalid inventory key: {location.value}/{denomination}"
            )

    @staticmethod
    async def _get_balance(session, location, denomination):
        row = (
            await session.execute(
                select(InventoryBalance).where(
                    InventoryBalance.location == location.value,
                    InventoryBalance.denomination == denomination,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise ValueError(
                f"Invalid inventory key: {location.value}/{denomination}"
            )
        return row
