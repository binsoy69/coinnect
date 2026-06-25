import pytest
from sqlalchemy import select

from app.models.db_models import InventoryAdjustment
from app.services.inventory_service import (
    InventoryLocation,
    InventoryService,
    InventoryUpdate,
)
from app.services.machine_status import MachineStatus


@pytest.fixture
async def inventory_service(db_session_factory, test_settings):
    status = MachineStatus(test_settings)
    service = InventoryService(db_session_factory, status)
    await service.initialize()
    return service


async def test_initialize_seeds_and_hydrates_all_inventory(
    inventory_service,
):
    snapshot = inventory_service.machine_status.snapshot().consumables

    assert len(snapshot.bill_dispenser_counts) == 12
    assert len(snapshot.coin_counts) == 4
    assert len(snapshot.bill_storage_counts) == 8
    assert all(count == 0 for count in snapshot.bill_dispenser_counts.values())


async def test_admin_batch_update_is_persisted_and_audited(
    inventory_service,
    db_session_factory,
):
    await inventory_service.apply_admin_updates(
        updates=[
            InventoryUpdate(
                location=InventoryLocation.BILL_DISPENSER,
                denomination="PHP_100",
                count=80,
            ),
            InventoryUpdate(
                location=InventoryLocation.BILL_STORAGE,
                denomination="USD",
                count=12,
            ),
        ],
        reason="REFILL",
        note="Scheduled loading",
        session_id="session-1",
    )

    restarted_status = MachineStatus(inventory_service.settings)
    restarted = InventoryService(db_session_factory, restarted_status)
    await restarted.initialize()
    snapshot = restarted_status.snapshot().consumables
    assert snapshot.bill_dispenser_counts["PHP_100"] == 80
    assert snapshot.bill_storage_counts["USD"] == 12

    async with db_session_factory() as session:
        rows = (
            await session.execute(
                select(InventoryAdjustment).order_by(InventoryAdjustment.id)
            )
        ).scalars().all()
    assert [(row.old_count, row.new_count, row.delta) for row in rows] == [
        (0, 80, 80),
        (0, 12, 12),
    ]
    assert all(row.source == "ADMIN" for row in rows)
    assert all(row.session_id == "session-1" for row in rows)


async def test_invalid_admin_batch_rolls_back_every_update(
    inventory_service,
):
    with pytest.raises(ValueError, match="Invalid inventory key"):
        await inventory_service.apply_admin_updates(
            updates=[
                InventoryUpdate(
                    location=InventoryLocation.BILL_DISPENSER,
                    denomination="PHP_100",
                    count=30,
                ),
                InventoryUpdate(
                    location=InventoryLocation.BILL_STORAGE,
                    denomination="USD_50",
                    count=4,
                ),
            ],
            reason="PHYSICAL_COUNT",
            session_id="session-1",
        )

    snapshot = inventory_service.machine_status.snapshot().consumables
    assert snapshot.bill_dispenser_counts["PHP_100"] == 0


async def test_reserve_and_reconcile_partial_dispense(
    inventory_service,
):
    await inventory_service.apply_admin_updates(
        [
            InventoryUpdate(
                location=InventoryLocation.BILL_DISPENSER,
                denomination="PHP_100",
                count=10,
            )
        ],
        reason="REFILL",
        session_id="session-1",
    )

    await inventory_service.reserve(
        {("BILL_DISPENSER", "PHP_100"): 4},
        reference_id="tx-1",
    )
    assert (
        inventory_service.machine_status.snapshot()
        .consumables.bill_dispenser_counts["PHP_100"]
        == 6
    )

    await inventory_service.restore(
        {("BILL_DISPENSER", "PHP_100"): 3},
        reference_id="tx-1",
    )
    assert (
        inventory_service.machine_status.snapshot()
        .consumables.bill_dispenser_counts["PHP_100"]
        == 9
    )


async def test_automatic_storage_increment_is_persistent(
    inventory_service,
    db_session_factory,
):
    await inventory_service.adjust(
        InventoryLocation.BILL_STORAGE,
        "EUR",
        1,
        reason="BILL_ACCEPTED",
        reference_id="tx-2",
    )

    restarted_status = MachineStatus(inventory_service.settings)
    restarted = InventoryService(db_session_factory, restarted_status)
    await restarted.initialize()
    assert restarted_status.snapshot().consumables.bill_storage_counts["EUR"] == 1
