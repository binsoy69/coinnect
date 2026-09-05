"""Unit tests for Arduino Uno coin intake session management, pulse cursors, and drain reconciliation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.ws import ConnectionManager
from app.core.config import Settings
from app.drivers.bill_controller import BillController
from app.drivers.coin_security_controller import CoinSecurityController
from app.drivers.mock_camera_controller import MockCameraController
from app.drivers.mock_gpio_controller import MockGPIOController
from app.drivers.serial_manager import SerialManager
from app.ml.mock_authenticator import MockBillAuthenticator
from app.models.db_models import (
    Base,
    ConverterCoinSession,
    InventoryBalance,
    TransactionRecord,
    TransactionState,
)
from app.models.serial_messages import CoinSessionStatusResponse
from app.services.bill_acceptor import BillAcceptor
from app.services.claim_service import ClaimService
from app.services.dispense_orchestrator import DispenseOrchestrator, DispenseResult
from app.services.event_dispatcher import EventDispatcher
from app.services.inventory_service import InventoryLocation, InventoryService
from app.services.machine_status import MachineStatus
from app.services.transaction_orchestrator import TransactionOrchestrator


@pytest.fixture
async def setup_env():
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

    # Seed coin inventory and bill dispenser in DB
    async with session_factory() as session:
        for denom, count in [("PHP_20", 50), ("PHP_50", 50), ("PHP_100", 50), ("PHP_200", 50), ("PHP_500", 50), ("PHP_1000", 50)]:
            row = (await session.execute(
                select(InventoryBalance).where(
                    InventoryBalance.location == InventoryLocation.BILL_DISPENSER.value,
                    InventoryBalance.denomination == denom,
                )
            )).scalar_one_or_none()
            if row:
                row.count = count
        for denom, count in [("PHP_1", 100), ("PHP_5", 100), ("PHP_10", 100), ("PHP_20", 100)]:
            row = (await session.execute(
                select(InventoryBalance).where(
                    InventoryBalance.location == InventoryLocation.COIN_DISPENSER.value,
                    InventoryBalance.denomination == denom,
                )
            )).scalar_one_or_none()
            if row:
                row.count = count
        await session.commit()
    await inventory_service.refresh_runtime()

    serial_manager = SerialManager(settings)
    bill_controller = BillController(serial_manager)
    coin_controller = AsyncMock(spec=CoinSecurityController)
    coin_controller.set_coin_acceptor_enabled = AsyncMock()
    coin_controller.coin_session_start = AsyncMock()
    coin_controller.coin_session_stop = AsyncMock()
    coin_controller.coin_session_status = AsyncMock()

    ws_manager = AsyncMock(spec=ConnectionManager)
    ws_manager.broadcast = AsyncMock()

    gpio_controller = MockGPIOController()
    camera_controller = MockCameraController()
    authenticator = MockBillAuthenticator()

    bill_acceptor = BillAcceptor(
        gpio_controller,
        camera_controller,
        authenticator,
        bill_controller,
        machine_status,
        ws_manager,
        settings,
        inventory_service=inventory_service,
    )

    claim_service = ClaimService(session_factory, ws_manager)
    dispense_orchestrator = AsyncMock()
    dispense_orchestrator.execute_dispense = AsyncMock(
        side_effect=lambda plan, **kwargs: DispenseResult(
            success=True,
            total_dispensed=plan.total_amount,
            shortfall=0,
        )
    )

    orchestrator = TransactionOrchestrator(
        bill_acceptor=bill_acceptor,
        dispense_orchestrator=dispense_orchestrator,
        coin_controller=coin_controller,
        machine_status=machine_status,
        ws_manager=ws_manager,
        db_session_factory=session_factory,
        claim_service=claim_service,
        inventory_service=inventory_service,
        settings=settings,
    )

    yield {
        "orchestrator": orchestrator,
        "session_factory": session_factory,
        "coin_controller": coin_controller,
        "ws_manager": ws_manager,
        "inventory_service": inventory_service,
        "machine_status": machine_status,
    }

    await engine.dispose()


@pytest.mark.asyncio
async def test_coin_session_start_allocates_session_and_enables_acceptor(setup_env):
    """Starting coin-to-bill creates ConverterCoinSession and calls coin_session_start."""
    env = setup_env
    orchestrator = env["orchestrator"]
    coin_controller = env["coin_controller"]
    session_factory = env["session_factory"]

    state = await orchestrator.start_transaction(
        transaction_type="coin-to-bill",
        target_amount=100,
        fee=0,
        selected_dispense_denoms=[100],
    )

    tx_id = state["transaction_id"]
    coin_controller.coin_session_start.assert_awaited_once_with(1)
    coin_controller.set_coin_acceptor_enabled.assert_not_awaited()

    async with session_factory() as session:
        res = await session.execute(
            select(ConverterCoinSession).where(ConverterCoinSession.transaction_id == tx_id)
        )
        coin_session = res.scalar_one_or_none()
        assert coin_session is not None
        assert coin_session.session_id == 1
        assert coin_session.state == "ACTIVE"
        assert coin_session.cursor_php_1 == 0
        assert coin_session.cursor_php_10 == 0


@pytest.mark.asyncio
async def test_coin_session_pulse_credits_amount_and_updates_cursor(setup_env):
    """COIN_SESSION_PULSE events credit transaction and update monotonic cursor."""
    env = setup_env
    orchestrator = env["orchestrator"]
    session_factory = env["session_factory"]

    state = await orchestrator.start_transaction(
        transaction_type="coin-to-bill",
        target_amount=100,
        fee=0,
        selected_dispense_denoms=[100],
    )
    tx_id = state["transaction_id"]

    # First pulse: 1x 10-peso coin
    res1 = await orchestrator.handle_coin_session_pulse(sid=1, seq=1, denom=10, count=1)
    assert res1["inserted_amount"] == 10
    assert res1["inserted_denominations"] == {"10": 1}

    # Second pulse: 2x 10-peso coins (cumulative count=2)
    res2 = await orchestrator.handle_coin_session_pulse(sid=1, seq=2, denom=10, count=2)
    assert res2["inserted_amount"] == 20
    assert res2["inserted_denominations"] == {"10": 2}

    # Pulse on different denomination: 1x 20-peso coin
    res3 = await orchestrator.handle_coin_session_pulse(sid=1, seq=3, denom=20, count=1)
    assert res3["inserted_amount"] == 40
    assert res3["inserted_denominations"] == {"10": 2, "20": 1}

    async with session_factory() as session:
        q = await session.execute(
            select(ConverterCoinSession).where(ConverterCoinSession.transaction_id == tx_id)
        )
        cs = q.scalar_one()
        assert cs.cursor_php_10 == 2
        assert cs.cursor_php_20 == 1


@pytest.mark.asyncio
async def test_coin_session_pulse_idempotency_ignores_duplicate_and_out_of_order(setup_env):
    """Monotonic cursors prevent duplicate credit from retransmitted or out-of-order pulses."""
    env = setup_env
    orchestrator = env["orchestrator"]

    await orchestrator.start_transaction(
        transaction_type="coin-to-bill",
        target_amount=100,
        fee=0,
        selected_dispense_denoms=[100],
    )

    # First delivery: count=3 (delta=3) -> +30 pesos
    res1 = await orchestrator.handle_coin_session_pulse(sid=1, seq=3, denom=10, count=3)
    assert res1["inserted_amount"] == 30

    # Duplicate delivery of count=3: delta=0 -> ignored
    res2 = await orchestrator.handle_coin_session_pulse(sid=1, seq=3, denom=10, count=3)
    assert res2["inserted_amount"] == 30

    # Out-of-order delivery of previous count=2: delta=-1 -> ignored
    res3 = await orchestrator.handle_coin_session_pulse(sid=1, seq=2, denom=10, count=2)
    assert res3["inserted_amount"] == 30


@pytest.mark.asyncio
async def test_coin_session_drain_and_reconciliation_on_confirm(setup_env):
    """Drain window polls controller until CLOSED and reconciles in-flight unpulsed coins."""
    env = setup_env
    orchestrator = env["orchestrator"]
    coin_controller = env["coin_controller"]
    session_factory = env["session_factory"]

    state = await orchestrator.start_transaction(
        transaction_type="coin-to-bill",
        target_amount=100,
        fee=0,
        selected_dispense_denoms=[100],
    )
    tx_id = state["transaction_id"]

    # Insert 9x 10-peso coins -> 90 pesos inserted
    await orchestrator.handle_coin_session_pulse(sid=1, seq=9, denom=10, count=9)

    # Insert 1x 10-peso coin -> 100 pesos inserted (meets total_due)
    state = await orchestrator.handle_coin_session_pulse(sid=1, seq=10, denom=10, count=10)
    assert state["state"] == TransactionState.WAITING_FOR_CONFIRMATION.value

    # Simulate that during the closing drain, 1 more coin (5-peso) dropped in physically
    # that wasn't pulsed before stop was issued
    coin_controller.coin_session_status.return_value = CoinSessionStatusResponse(
        status="OK",
        sid=1,
        session_state="CLOSED",
        count_1=0,
        count_5=1,  # 1 unpulsed coin of 5 pesos
        count_10=10,
        count_20=0,
        total_amount=105,
    )

    # User confirms transaction
    final_state = await orchestrator.confirm_transaction()
    assert final_state["state"] == TransactionState.COMPLETE.value

    # Verify coin_session_stop was awaited
    coin_controller.coin_session_stop.assert_awaited_with(1)

    # Verify session is marked CLOSED in database
    async with session_factory() as session:
        q = await session.execute(
            select(ConverterCoinSession).where(ConverterCoinSession.transaction_id == tx_id)
        )
        cs = q.scalar_one()
        assert cs.state == "CLOSED"
        assert cs.final_count_php_5 == 1
        assert cs.final_count_php_10 == 10

        tx_rec = await session.get(TransactionRecord, tx_id)
        # 100 pesos planned + 5 pesos overpayment was credited
        assert tx_rec.inserted_amount == 105


@pytest.mark.asyncio
async def test_event_dispatcher_routes_coin_session_pulse(setup_env):
    """EventDispatcher handles COIN_SESSION_PULSE by invoking orchestrator."""
    env = setup_env
    orchestrator = env["orchestrator"]
    machine_status = env["machine_status"]
    ws_manager = env["ws_manager"]

    orchestrator.handle_coin_session_pulse = AsyncMock()
    orchestrator._active_tx = MagicMock()

    dispatcher = EventDispatcher(
        event_queue=asyncio.Queue(),
        machine_status=machine_status,
        ws_manager=ws_manager,
        transaction_orchestrator=orchestrator,
    )

    event_data = {
        "event": "COIN_SESSION_PULSE",
        "sid": 1,
        "seq": 5,
        "denom": 10,
        "count": 5,
        "_controller": "COIN_SECURITY",
    }
    await dispatcher._handle_event(event_data)

    orchestrator.handle_coin_session_pulse.assert_awaited_once_with(
        sid=1,
        seq=5,
        denom=10,
        count=5,
    )


@pytest.mark.asyncio
async def test_concurrent_duplicate_counts_credit_once(setup_env):
    o = setup_env["orchestrator"]
    state = await o.start_transaction("coin-to-bill", 100, [100])
    await asyncio.gather(*[o.handle_coin_session_pulse(1, 1, 10, 1) for _ in range(5)])
    result = await o.get_transaction_state(state["transaction_id"])
    assert result["inserted_amount"] == 10
    assert result["inserted_denominations"] == {"10": 1}


@pytest.mark.asyncio
async def test_inventory_failure_does_not_advance_credit_or_cursor(setup_env):
    o = setup_env["orchestrator"]
    state = await o.start_transaction("coin-to-bill", 100, [100])
    inventory = setup_env["inventory_service"]
    original = inventory.adjust_in_session
    inventory.adjust_in_session = AsyncMock(side_effect=RuntimeError("database failure"))
    with pytest.raises(RuntimeError):
        await o.handle_coin_session_pulse(1, 1, 10, 1)
    async with setup_env["session_factory"]() as session:
        row = (await session.execute(select(ConverterCoinSession))).scalar_one()
        record = await session.get(TransactionRecord, state["transaction_id"])
        assert row.cursor_php_10 == 0
        assert record.inserted_amount == 0
    inventory.adjust_in_session = original
    await o.handle_coin_session_pulse(1, 1, 10, 1)
    result = await o.get_transaction_state(state["transaction_id"])
    assert result["inserted_amount"] == 10
