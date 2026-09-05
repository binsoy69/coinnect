"""Unit and lifecycle tests for converter quotes, reapproval, and claims."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.router import api_router
from app.api.ws import ConnectionManager
from app.core.config import Settings
from app.drivers.bill_controller import BillController
from app.drivers.coin_security_controller import CoinSecurityController
from app.drivers.mock_camera_controller import MockCameraController
from app.drivers.mock_gpio_controller import MockGPIOController
from app.drivers.serial_manager import SerialManager
from app.ml.mock_authenticator import MockBillAuthenticator
from app.models.db_models import Base, ConverterQuote, ClaimRecord
from app.services.bill_acceptor import BillAcceptor
from app.services.dispense_orchestrator import DispenseOrchestrator
from app.services.machine_status import MachineStatus
from app.services.transaction_orchestrator import TransactionOrchestrator
from app.services.inventory_service import InventoryService
from app.services.claim_service import ClaimService


@pytest.fixture
async def lifecycle_app(monkeypatch):
    """Create test FastAPI application with all subsystems wired."""
    app = FastAPI()
    app.include_router(api_router)

    settings = Settings(
        use_mock_serial=True,
        use_mock_hardware=True,
        mock_delay=0.0,
        serial_port_bill="MOCK_BILL",
        serial_port_coin="MOCK_COIN",
        environment="test",
        log_level="DEBUG",
        db_url="sqlite+aiosqlite:///:memory:",
        fee_bill_to_bill=5,
        fee_bill_to_coin=5,
        fee_coin_to_bill=5,
        bill_acceptance_timeout=1,
    )
    monkeypatch.setattr(
        "app.services.transaction_orchestrator.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.api.transaction.get_settings",
        lambda: settings,
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    ws_manager = ConnectionManager()
    ws_manager.broadcast = AsyncMock()

    machine_status = MachineStatus(settings)
    machine_status.set_dispenser_counts({
        "PHP_20": 10,
        "PHP_50": 10,
        "PHP_100": 10,
        "PHP_200": 0,
        "PHP_500": 0,
        "PHP_1000": 0,
    })
    machine_status.set_coin_counts({
        "PHP_1": 50,
        "PHP_5": 50,
        "PHP_10": 50,
        "PHP_20": 50,
    })

    gpio = MockGPIOController()
    gpio.set_bill_at_entry(True)

    camera = MockCameraController()
    camera._initialized = True

    authenticator = MockBillAuthenticator()

    serial_manager = SerialManager(settings)
    await serial_manager.startup()

    bill_controller = BillController(serial_manager)
    coin_controller = CoinSecurityController(serial_manager)
    bill_controller.sort = AsyncMock()
    bill_controller.dispense = AsyncMock(
        side_effect=lambda denom, count, **kwargs: MagicMock(dispensed=count)
    )
    coin_controller.coin_dispense = AsyncMock(
        side_effect=lambda denom, count, **kwargs: MagicMock(dispensed=count)
    )
    coin_controller.set_coin_acceptor_enabled = AsyncMock()

    bill_acceptor = BillAcceptor(
        gpio, camera, authenticator, bill_controller,
        machine_status, ws_manager, settings,
    )
    dispense_orchestrator = DispenseOrchestrator(
        bill_controller=bill_controller,
        coin_controller=coin_controller,
        machine_status=machine_status,
        ws_manager=ws_manager,
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
    )

    app.state.settings = settings
    app.state.db_session_factory = session_factory
    app.state.machine_status = machine_status
    app.state.ws_manager = ws_manager
    app.state.bill_acceptor = bill_acceptor
    app.state.transaction_orchestrator = orchestrator
    app.state.claim_service = claim_service

    return app


@pytest.mark.asyncio
async def test_valid_quote_start_attaches_approved_quote(lifecycle_app):
    """Starting with a valid quote attaches approved terms and initial snapshot state."""
    transport = ASGITransport(app=lifecycle_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        quote_resp = await client.post(
            "/api/v1/transaction/quote",
            json={"type": "bill-to-coin", "amount": 100},
        )
        assert quote_resp.status_code == 200
        quote_data = quote_resp.json()
        quote_id = quote_data["id"]

        start_resp = await client.post(
            "/api/v1/transaction/",
            json={"type": "bill-to-coin", "amount": 100, "quote_id": quote_id},
        )
        assert start_resp.status_code == 200, start_resp.json()
        tx_data = start_resp.json()
        assert tx_data["revision"] == 2
        assert tx_data["approved_quote"]["id"] == quote_id
        assert tx_data["pending_quote"] is None
        assert tx_data["acceptance_phase"] == "OPEN"
        assert tx_data["can_continue"] is True
        assert tx_data["can_confirm"] is False


@pytest.mark.asyncio
async def test_stale_quote_start_rejected_with_409(lifecycle_app):
    """Starting with a stale quote is rejected with 409 QUOTE_CHANGED."""
    transport = ASGITransport(app=lifecycle_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        quote_resp = await client.post(
            "/api/v1/transaction/quote",
            json={
                "type": "bill-to-coin",
                "amount": 100,
                "requested_counts": {"PHP_20": 4, "PHP_10": 1, "PHP_5": 1},
            },
        )
        assert quote_resp.status_code == 200
        quote_data = quote_resp.json()
        quote_id = quote_data["id"]

        ms = lifecycle_app.state.machine_status
        ms.set_coin_counts({"PHP_1": 50, "PHP_5": 50, "PHP_10": 50, "PHP_20": 0})

        start_resp = await client.post(
            "/api/v1/transaction/",
            json={"type": "bill-to-coin", "amount": 100, "quote_id": quote_id},
        )
        assert start_resp.status_code == 409
        detail = start_resp.json()["detail"]
        assert detail["code"] == "QUOTE_CHANGED"
        assert detail["quote"] is not None
        new_items = {item["denom"]: item["count"] for item in detail["quote"]["items"]}
        assert new_items.get("PHP_20", 0) == 0


@pytest.mark.asyncio
async def test_pre_dispense_stock_drop_requires_reapproval(lifecycle_app):
    """If stock drops between quote approval and confirmation, confirm raises 409 PAYOUT_REAPPROVAL_REQUIRED."""
    transport = ASGITransport(app=lifecycle_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        quote_resp = await client.post(
            "/api/v1/transaction/quote",
            json={
                "type": "bill-to-coin",
                "amount": 100,
                "requested_counts": {"PHP_20": 4, "PHP_10": 1, "PHP_5": 1},
            },
        )
        assert quote_resp.status_code == 200
        quote_id = quote_resp.json()["id"]

        start_resp = await client.post(
            "/api/v1/transaction/",
            json={"type": "bill-to-coin", "amount": 100, "quote_id": quote_id},
        )
        assert start_resp.status_code == 200
        tx_id = start_resp.json()["transaction_id"]

        sim_resp = await client.post(
            f"/api/v1/transaction/{tx_id}/simulate-insert",
            json={"denom": 100, "insert_type": "bill"},
        )
        assert sim_resp.status_code == 200
        assert sim_resp.json()["state"] == "WAITING_FOR_CONFIRMATION"

        ms = lifecycle_app.state.machine_status
        ms.set_coin_counts({"PHP_1": 50, "PHP_5": 50, "PHP_10": 50, "PHP_20": 0})

        confirm_resp = await client.post(f"/api/v1/transaction/{tx_id}/confirm")
        assert confirm_resp.status_code == 409
        detail = confirm_resp.json()["detail"]
        assert detail["code"] == "PAYOUT_REAPPROVAL_REQUIRED"
        assert detail["pending_quote"] is not None
        pending_quote = detail["pending_quote"]

        tx_get = await client.get(f"/api/v1/transaction/{tx_id}")
        assert tx_get.status_code == 200
        snapshot = tx_get.json()
        assert snapshot["acceptance_phase"] == "CLOSED"
        assert snapshot["revision"] >= 3
        assert snapshot["pending_quote"]["id"] == pending_quote["id"]

        approve_resp = await client.post(
            f"/api/v1/transaction/{tx_id}/approve-quote",
            json={"quote_id": pending_quote["id"]},
        )
        assert approve_resp.status_code == 200
        approved_snap = approve_resp.json()
        assert approved_snap["revision"] > snapshot["revision"]
        assert approved_snap["approved_quote"]["id"] == pending_quote["id"]
        assert approved_snap["pending_quote"] is None
        assert approved_snap["acceptance_phase"] == "CLOSED"

        confirm_success = await client.post(f"/api/v1/transaction/{tx_id}/confirm")
        assert confirm_success.status_code == 200
        final_state = confirm_success.json()
        assert final_state["state"] == "COMPLETE"
        assert final_state["dispensed_amount"] == 95


@pytest.mark.asyncio
async def test_request_claim_refunds_full_cash_and_fee(lifecycle_app):
    """Customer can abort session with cash inserted; creates claim ticket with full fee refund."""
    transport = ASGITransport(app=lifecycle_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        quote_resp = await client.post(
            "/api/v1/transaction/quote",
            json={"type": "coin-to-bill", "amount": 100},
        )
        assert quote_resp.status_code == 200
        quote_id = quote_resp.json()["id"]

        start_resp = await client.post(
            "/api/v1/transaction/",
            json={"type": "coin-to-bill", "amount": 100, "quote_id": quote_id},
        )
        assert start_resp.status_code == 200
        tx_id = start_resp.json()["transaction_id"]

        for _ in range(3):
            await client.post(
                f"/api/v1/transaction/{tx_id}/simulate-insert",
                json={"denom": 20, "insert_type": "coin"},
            )

        claim_resp = await client.post(f"/api/v1/transaction/{tx_id}/claim")
        assert claim_resp.status_code == 200
        state = claim_resp.json()
        assert state["state"] == "CLAIM_REQUIRED"
        assert state["claim_ticket_code"] is not None
        assert state["claim"]["amount"] == 60
        assert state["claim"]["reason_code"] == "CUSTOMER_ABORT"
        assert state["acceptance_phase"] == "CLOSED"


@pytest.mark.asyncio
async def test_pre_dispense_stock_exhausted_creates_claim(lifecycle_app):
    """When stock drops and no valid payout is possible, confirm transitions directly to claim."""
    transport = ASGITransport(app=lifecycle_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        quote = (await client.post("/api/v1/transaction/quote", json={"type": "bill-to-coin", "amount": 100})).json()
        start_resp = await client.post("/api/v1/transaction/", json={"quote_id": quote["id"]})
        assert start_resp.status_code == 200
        tx_id = start_resp.json()["transaction_id"]

        await client.post(
            f"/api/v1/transaction/{tx_id}/simulate-insert",
            json={"denom": 100, "insert_type": "bill"},
        )

        ms = lifecycle_app.state.machine_status
        ms.set_coin_counts({"PHP_1": 0, "PHP_5": 0, "PHP_10": 0, "PHP_20": 0})

        confirm_resp = await client.post(f"/api/v1/transaction/{tx_id}/confirm")
        assert confirm_resp.status_code == 200
        state = confirm_resp.json()
        assert state["state"] == "CLAIM_REQUIRED"
        assert state["claim_ticket_code"] is not None
        assert state["claim"]["amount"] == 100


@pytest.mark.asyncio
async def test_quote_only_start_and_unrelated_reapproval_rejected(lifecycle_app):
    async with AsyncClient(transport=ASGITransport(app=lifecycle_app), base_url="http://test") as client:
        quote = (await client.post("/api/v1/transaction/quote", json={"type": "bill-to-coin", "amount": 20})).json()
        started = await client.post("/api/v1/transaction/", json={"quote_id": quote["id"]})
        assert started.status_code == 200
        tid = started.json()["transaction_id"]
        await client.post(f"/api/v1/transaction/{tid}/simulate-insert", json={"denom": 20, "insert_type": "bill"})
        other = (await client.post("/api/v1/transaction/quote", json={"type": "bill-to-coin", "amount": 200})).json()
        rejected = await client.post(f"/api/v1/transaction/{tid}/approve-quote", json={"quote_id": other["id"]})
        assert rejected.status_code == 422
        current = (await client.get(f"/api/v1/transaction/{tid}")).json()
        assert current["approved_quote"]["id"] == quote["id"]
        assert current["payout_amount"] == 15


@pytest.mark.asyncio
async def test_claim_cannot_interrupt_confirmed_payout(lifecycle_app):
    import asyncio
    orchestrator = lifecycle_app.state.transaction_orchestrator
    entered, release = asyncio.Event(), asyncio.Event()
    execute = orchestrator._dispenser.execute_dispense
    async def slow(*args, **kwargs):
        entered.set()
        await release.wait()
        return await execute(*args, **kwargs)
    orchestrator._dispenser.execute_dispense = slow
    async with AsyncClient(transport=ASGITransport(app=lifecycle_app), base_url="http://test") as client:
        quote = (await client.post("/api/v1/transaction/quote", json={"type": "bill-to-coin", "amount": 100})).json()
        tid = (await client.post("/api/v1/transaction/", json={"quote_id": quote["id"]})).json()["transaction_id"]
        await client.post(f"/api/v1/transaction/{tid}/simulate-insert", json={"denom": 100, "insert_type": "bill"})
        payout = asyncio.create_task(client.post(f"/api/v1/transaction/{tid}/confirm"))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            claim = await client.post(f"/api/v1/transaction/{tid}/claim")
            assert claim.status_code == 422
        finally:
            release.set()
        result = await payout
        assert result.status_code == 200
        assert result.json()["state"] == "COMPLETE"
        assert result.json()["claim"] is None
