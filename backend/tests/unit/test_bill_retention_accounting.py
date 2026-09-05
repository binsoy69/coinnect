"""Unit tests for two-phase bill retention accounting, retry loop, and intake fault handling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.ws import ConnectionManager
from app.core.config import Settings
from app.core.constants import BillDenom
from app.core.errors import TransactionError
from app.drivers.bill_controller import BillController
from app.drivers.coin_security_controller import CoinSecurityController
from app.drivers.mock_camera_controller import MockCameraController
from app.drivers.mock_gpio_controller import MockGPIOController
from app.drivers.serial_manager import SerialManager
from app.ml.mock_authenticator import MockBillAuthenticator
from app.models.db_models import (
    Base,
    ConverterIntakeOperation,
    InventoryAdjustment,
    TransactionRecord,
    TransactionState,
    ClaimRecord,
)
from app.services.bill_acceptor import BillAcceptor
from app.services.dispense_orchestrator import DispenseOrchestrator
from app.services.inventory_service import InventoryLocation, InventoryService
from app.services.machine_status import MachineStatus
from app.services.transaction_orchestrator import TransactionOrchestrator
from app.services.claim_service import ClaimService


@pytest.fixture
async def setup_env():
    """Setup in-memory DB and test environment."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    settings = Settings(
        use_mock_serial=True,
        use_mock_hardware=True,
        mock_delay=0.0,
        serial_port_bill="MOCK_BILL",
        serial_port_coin="MOCK_COIN",
        environment="test",
        log_level="DEBUG",
        db_url="sqlite+aiosqlite:///:memory:",
        fee_bill_to_coin=0,
        fee_bill_to_bill=0,
        fee_coin_to_bill=0,
        bill_acceptance_timeout=1,
    )

    machine_status = MachineStatus(settings)
    inventory_service = InventoryService(session_factory, machine_status)
    await inventory_service.initialize()
    machine_status.set_coin_counts({
        "PHP_1": 50,
        "PHP_5": 50,
        "PHP_10": 50,
        "PHP_20": 50,
    })
    machine_status.set_dispenser_counts({
        "PHP_20": 20,
        "PHP_50": 20,
        "PHP_100": 20,
        "PHP_200": 20,
        "PHP_500": 20,
        "PHP_1000": 20,
    })

    ws_manager = ConnectionManager()
    ws_manager.broadcast = AsyncMock()

    gpio = MockGPIOController()
    gpio.set_bill_at_entry(True)

    camera = MockCameraController()
    camera._initialized = True

    authenticator = MockBillAuthenticator()
    authenticator.set_next_denomination(BillDenom.PHP_100)

    serial_manager = SerialManager(settings)
    await serial_manager.startup()

    bill_controller = BillController(serial_manager)
    coin_controller = CoinSecurityController(serial_manager)
    bill_controller.sort = AsyncMock()

    bill_acceptor = BillAcceptor(
        gpio, camera, authenticator, bill_controller,
        machine_status, ws_manager, settings,
        inventory_service=inventory_service,
    )

    dispense_orchestrator = DispenseOrchestrator(
        bill_controller=bill_controller,
        coin_controller=coin_controller,
        machine_status=machine_status,
        ws_manager=ws_manager,
        inventory_service=inventory_service,
        db_session_factory=session_factory,
    )

    claim_service = ClaimService(session_factory, ws_manager)

    orchestrator = TransactionOrchestrator(
        bill_acceptor=bill_acceptor,
        dispense_orchestrator=dispense_orchestrator,
        coin_controller=coin_controller,
        machine_status=machine_status,
        ws_manager=ws_manager,
        db_session_factory=session_factory,
        claim_service=claim_service,
        inventory_service=inventory_service,
    )

    return {
        "engine": engine,
        "session_factory": session_factory,
        "orchestrator": orchestrator,
        "bill_acceptor": bill_acceptor,
        "bill_controller": bill_controller,
        "gpio": gpio,
        "inventory_service": inventory_service,
        "claim_service": claim_service,
        "machine_status": machine_status,
    }


@pytest.mark.asyncio
async def test_two_phase_bill_intake_success(setup_env):
    """Normal intake atomically writes ConverterIntakeOperation, credits transaction, and updates inventory."""
    env = setup_env
    orchestrator = env["orchestrator"]
    session_factory = env["session_factory"]

    started = await orchestrator.start_transaction(
        transaction_type="bill-to-coin",
        target_amount=100,
        selected_dispense_denoms=[20],
    )
    tx_id = started["transaction_id"]

    state = await orchestrator.handle_bill_inserted()
    assert state["inserted_amount"] == 100
    assert state["state"] == TransactionState.WAITING_FOR_CONFIRMATION.value
    assert state["revision"] > 2

    async with session_factory() as session:
        # Verify ConverterIntakeOperation
        ops = (
            await session.execute(
                select(ConverterIntakeOperation).where(
                    ConverterIntakeOperation.transaction_id == tx_id
                )
            )
        ).scalars().all()
        assert len(ops) == 1
        op = ops[0]
        assert op.state == "RETAINED"
        assert op.denomination == "PHP_100"
        assert op.value == 100
        assert op.inventory_credited is True
        assert op.transaction_credited is True

        # Verify InventoryAdjustment
        adj = (
            await session.execute(
                select(InventoryAdjustment).where(
                    InventoryAdjustment.reference_id == op.id
                )
            )
        ).scalar_one_or_none()
        assert adj is not None
        assert adj.location == InventoryLocation.BILL_STORAGE.value
        assert adj.denomination == "PHP_100"
        assert adj.delta == 1
        assert adj.reason == "BILL_ACCEPTED"


@pytest.mark.asyncio
async def test_preparation_db_failure_aborts_before_sort(setup_env, monkeypatch):
    """If ConverterIntakeOperation preparation fails, abort and eject bill without moving sorter."""
    env = setup_env
    orchestrator = env["orchestrator"]
    bill_acceptor = env["bill_acceptor"]
    bill_controller = env["bill_controller"]
    gpio = env["gpio"]

    started = await orchestrator.start_transaction(
        transaction_type="bill-to-coin",
        target_amount=100,
        selected_dispense_denoms=[20],
    )
    tx_id = started["transaction_id"]

    # Monkeypatch session factory to fail during preparation write
    original_factory = env["session_factory"]

    class FailingSessionFactory:
        def __call__(self):
            session = original_factory()
            original_commit = session.commit

            async def fail_commit():
                raise RuntimeError("Disk I/O failure during intake preparation")

            session.commit = fail_commit
            return session

    orchestrator._db_factory = FailingSessionFactory()

    # handle_bill_inserted should catch rejection and return state without advancing to WAITING_FOR_CONFIRMATION
    state = await orchestrator.handle_bill_inserted()
    assert state["inserted_amount"] == 0
    assert state["state"] == TransactionState.WAITING_FOR_BILL.value

    # Verify sorter was NEVER commanded to move
    assert bill_controller.sort.call_count == 0


@pytest.mark.asyncio
async def test_retention_commit_failure_activates_accounting_fault_and_retries(setup_env):
    """If DB commit fails after physical retention, ACCOUNTING_FAULT is active, blocks intake, and retries until reconciled."""
    env = setup_env
    orchestrator = env["orchestrator"]
    session_factory = env["session_factory"]

    started = await orchestrator.start_transaction(
        transaction_type="bill-to-coin",
        target_amount=100,
        selected_dispense_denoms=[20],
    )
    tx_id = started["transaction_id"]

    real_commit_retained = orchestrator._commit_retained_bill
    fail_count = 1

    async def mock_commit_retained(*args, **kwargs):
        nonlocal fail_count
        if fail_count > 0:
            fail_count -= 1
            raise RuntimeError("Transient database lock")
        return await real_commit_retained(*args, **kwargs)

    orchestrator._commit_retained_bill = mock_commit_retained

    # Intake cycle: physical storage completes, but initial DB commit fails
    state = await orchestrator.handle_bill_inserted()

    # Fault must be active
    assert orchestrator.has_accounting_fault is True
    assert state["accounting_fault"] is True
    assert state["can_continue"] is False
    assert state["can_confirm"] is False

    # Attempting another intake during fault raises TransactionError with ACCOUNTING_FAULT
    with pytest.raises(TransactionError, match="ACCOUNTING_FAULT"):
        await orchestrator.handle_bill_inserted()

    # Attempting to start another transaction during fault raises TransactionError
    with pytest.raises(TransactionError, match="ACCOUNTING_FAULT"):
        await orchestrator.start_transaction(
            transaction_type="bill-to-coin",
            target_amount=100,
            selected_dispense_denoms=[20],
        )

    # Let retry loop run (it sleeps 2s in background, but we can wait for it)
    deadline = asyncio.get_event_loop().time() + 5.0
    while orchestrator.has_accounting_fault and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.2)

    assert orchestrator.has_accounting_fault is False
    final_state = await orchestrator.get_transaction_state(tx_id)
    assert final_state["inserted_amount"] == 100
    assert final_state["state"] == TransactionState.CLAIM_REQUIRED.value
    assert final_state["can_confirm"] is False
    assert final_state["claim"]["amount"] == 100


@pytest.mark.asyncio
async def test_crash_recovery_reconciles_uncredited_intake(setup_env):
    """Crash recovery credits prepared bills if transaction was interrupted in SORTING or later."""
    env = setup_env
    orchestrator = env["orchestrator"]
    session_factory = env["session_factory"]

    tx_id = "test-crash-tx-1"
    async with session_factory() as session:
        # Create a transaction stuck in SORTING
        tx_rec = TransactionRecord(
            id=tx_id,
            type="bill-to-coin",
            state=TransactionState.SORTING.value,
            target_amount=100,
            fee=0,
            total_due=100,
            inserted_amount=0,
            dispensed_amount=0,
            converter_metadata={"revision": 1},
        )
        session.add(tx_rec)

        # Create uncredited prepared intake operation
        op = ConverterIntakeOperation(
            id="test-op-1",
            transaction_id=tx_id,
            denomination="PHP_100",
            value=100,
            state="PREPARED",
            inventory_credited=False,
            transaction_credited=False,
        )
        session.add(op)
        await session.commit()

    # Run crash recovery
    await orchestrator.recover_pending_transactions()

    async with session_factory() as session:
        rec = await session.get(TransactionRecord, tx_id)
        assert rec.state == TransactionState.CLAIM_REQUIRED.value
        assert rec.inserted_amount == 0

        op_after = await session.get(ConverterIntakeOperation, "test-op-1")
        assert op_after.state == "UNCERTAIN"
        assert op_after.transaction_credited is False

        claim = (
            await session.execute(
                select(ClaimRecord).where(ClaimRecord.transaction_id == tx_id)
            )
        ).scalar_one_or_none()
        assert claim is not None
        assert claim.amount == 100
        assert claim.claim_kind == "INPUT_REFUND"


@pytest.mark.asyncio
async def test_failure_after_retention_commit_creates_claim_without_repeating_motion(setup_env):
    orchestrator = setup_env["orchestrator"]
    started = await orchestrator.start_transaction("bill-to-coin", 100, [20])
    original = orchestrator._active_tx.transition_to
    failed = False
    async def transition(state, data=None):
        nonlocal failed
        if state == TransactionState.WAITING_FOR_BILL and not failed:
            failed = True
            raise RuntimeError("State commit failed after retention")
        return await original(state, data)
    orchestrator._active_tx.transition_to = transition
    with pytest.raises(RuntimeError, match="State commit failed"):
        await orchestrator.handle_bill_inserted()
    assert orchestrator.has_accounting_fault
    await asyncio.wait_for(asyncio.shield(orchestrator._accounting_retry_task), 5)
    result = await orchestrator.get_transaction_state(started["transaction_id"])
    assert result["state"] == "CLAIM_REQUIRED"
    assert result["inserted_amount"] == result["claim"]["amount"] == 100
    assert not orchestrator.has_accounting_fault
    orchestrator._bill_acceptor._bill.sort.assert_awaited_once()
