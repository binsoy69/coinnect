"""Integration tests for the transaction API endpoints.

Uses httpx.AsyncClient with ASGITransport to test real FastAPI endpoints
against a test-specific app instance (bypassing the lifespan handler that
starts real serial connections).
"""

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
from app.models.db_models import Base
from app.services.bill_acceptor import BillAcceptor
from app.services.dispense_orchestrator import DispenseOrchestrator
from app.services.machine_status import MachineStatus
from app.services.transaction_orchestrator import TransactionOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_app():
    """Create a test FastAPI app with mocked hardware dependencies.

    Builds the full dependency graph manually (SerialManager, controllers,
    services) so we never open real serial ports or GPIO pins.  Uses an
    in-memory SQLite database for transaction persistence.
    """
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
        led_stabilization_delay=0.0,
        bill_position_timeout=0.5,
        bill_store_duration=0.0,
        bill_eject_duration=0.0,
        bill_acceptance_timeout=1,
    )

    # Database ----------------------------------------------------------
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # WebSocket manager (no real clients in tests) ----------------------
    ws_manager = ConnectionManager()
    # Patch broadcast to accept raw JSON strings (callers pass strings,
    # but the original method tries to call .model_dump_json() on the arg).
    ws_manager.broadcast = AsyncMock()

    # Machine status with pre-populated inventory -----------------------
    machine_status = MachineStatus(settings)
    machine_status.set_dispenser_counts(
        {"PHP_100": 50, "PHP_50": 50, "PHP_20": 50}
    )
    machine_status.set_coin_counts(
        {"PHP_10": 50, "PHP_5": 50, "PHP_1": 50}
    )

    # Mock hardware controllers -----------------------------------------
    gpio = MockGPIOController()
    gpio.set_bill_at_entry(True)
    gpio.set_bill_in_position(True)

    camera = MockCameraController()
    camera._initialized = True

    authenticator = MockBillAuthenticator()

    # Serial manager + typed controllers --------------------------------
    serial_manager = SerialManager(settings)
    await serial_manager.startup()

    bill_controller = BillController(serial_manager)
    coin_controller = CoinSecurityController(serial_manager)

    # Mock serial-dependent methods so tests don't need real serial I/O.
    # sort() is called during bill acceptance (BillAcceptor.accept_bill).
    bill_controller.sort = AsyncMock()
    # dispense() is called during confirm (DispenseOrchestrator).
    # Return an object with a .dispensed attribute matching the requested count.
    bill_controller.dispense = AsyncMock(
        side_effect=lambda denom, count: MagicMock(dispensed=count)
    )
    # coin_dispense() is called when the dispense plan includes coins.
    coin_controller.coin_dispense = AsyncMock(
        side_effect=lambda denom, count: MagicMock(dispensed=count)
    )

    # Service layer -----------------------------------------------------
    bill_acceptor = BillAcceptor(
        gpio, camera, authenticator, bill_controller,
        machine_status, ws_manager, settings,
    )
    dispense_orchestrator = DispenseOrchestrator(
        bill_controller, coin_controller, machine_status, ws_manager,
    )
    transaction_orchestrator = TransactionOrchestrator(
        bill_acceptor, dispense_orchestrator, machine_status,
        ws_manager, session_factory,
    )

    # Attach everything to app.state ------------------------------------
    app.state.settings = settings
    app.state.ws_manager = ws_manager
    app.state.machine_status = machine_status
    app.state.bill_acceptor = bill_acceptor
    app.state.dispense_orchestrator = dispense_orchestrator
    app.state.transaction_orchestrator = transaction_orchestrator

    yield app

    # Cleanup -----------------------------------------------------------
    await serial_manager.shutdown()
    await engine.dispose()


@pytest.fixture
async def client(test_app):
    """httpx.AsyncClient wired to the test FastAPI application."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

START_PAYLOAD = {
    "type": "bill-to-bill",
    "amount": 200,
    "fee": 0,
    "selected_dispense_denoms": [100, 50],
}


async def _start_transaction(client: AsyncClient, payload: dict = None):
    """POST /api/v1/transaction/ and return the JSON body."""
    resp = await client.post(
        "/api/v1/transaction/", json=payload or START_PAYLOAD,
    )
    return resp


async def _simulate_bill_insert(
    client: AsyncClient, transaction_id: str, denom: int = 100,
):
    """POST /api/v1/transaction/{id}/simulate-insert for a bill."""
    return await client.post(
        f"/api/v1/transaction/{transaction_id}/simulate-insert",
        json={"denom": denom, "insert_type": "bill"},
    )


# ---------------------------------------------------------------------------
# Tests: POST /api/v1/transaction/ (start)
# ---------------------------------------------------------------------------


class TestStartTransaction:
    """Tests for the transaction creation endpoint."""

    async def test_start_returns_200_with_transaction_id(self, client):
        resp = await _start_transaction(client)
        assert resp.status_code == 200
        body = resp.json()
        assert "transaction_id" in body
        assert body["transaction_id"]  # non-empty
        assert body["type"] == "bill-to-bill"
        assert body["target_amount"] == 200
        assert body["fee"] == 0
        assert body["total_due"] == 200

    async def test_start_sets_state_to_waiting_for_bill(self, client):
        resp = await _start_transaction(client)
        body = resp.json()
        assert body["state"] == "WAITING_FOR_BILL"

    async def test_start_initial_amounts_are_zero(self, client):
        resp = await _start_transaction(client)
        body = resp.json()
        assert body["inserted_amount"] == 0
        assert body["dispensed_amount"] == 0
        assert body["inserted_denominations"] == {}

    async def test_start_returns_selected_dispense_denoms(self, client):
        resp = await _start_transaction(client)
        body = resp.json()
        assert body["selected_dispense_denoms"] == [100, 50]

    async def test_start_duplicate_returns_409(self, client):
        """Starting a second transaction while one is active yields 409."""
        first = await _start_transaction(client)
        assert first.status_code == 200

        second = await _start_transaction(client)
        assert second.status_code == 409

    async def test_start_returns_timestamps(self, client):
        resp = await _start_transaction(client)
        body = resp.json()
        assert body["created_at"] is not None
        assert body["updated_at"] is not None


# ---------------------------------------------------------------------------
# Tests: GET /api/v1/transaction/{id} (read)
# ---------------------------------------------------------------------------


class TestGetTransaction:
    """Tests for the transaction read endpoint."""

    async def test_get_returns_current_state(self, client):
        start = (await _start_transaction(client)).json()
        tx_id = start["transaction_id"]

        resp = await client.get(f"/api/v1/transaction/{tx_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["transaction_id"] == tx_id
        assert body["state"] == "WAITING_FOR_BILL"
        assert body["type"] == "bill-to-bill"

    async def test_get_nonexistent_returns_404(self, client):
        resp = await client.get("/api/v1/transaction/nonexistent-id")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: DELETE /api/v1/transaction/{id} (cancel)
# ---------------------------------------------------------------------------


class TestCancelTransaction:
    """Tests for the transaction cancellation endpoint."""

    async def test_cancel_active_transaction(self, client):
        start = (await _start_transaction(client)).json()
        tx_id = start["transaction_id"]

        resp = await client.delete(f"/api/v1/transaction/{tx_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "CANCELLED"
        assert body["transaction_id"] == tx_id

    async def test_cancel_wrong_id_returns_404(self, client):
        await _start_transaction(client)
        resp = await client.delete("/api/v1/transaction/wrong-id")
        assert resp.status_code == 404

    async def test_cancel_allows_new_transaction(self, client):
        """After cancellation a new transaction can be started."""
        start = (await _start_transaction(client)).json()
        tx_id = start["transaction_id"]

        cancel = await client.delete(f"/api/v1/transaction/{tx_id}")
        assert cancel.status_code == 200

        second = await _start_transaction(client)
        assert second.status_code == 200
        assert second.json()["transaction_id"] != tx_id


# ---------------------------------------------------------------------------
# Tests: POST /api/v1/transaction/{id}/simulate-insert
# ---------------------------------------------------------------------------


class TestSimulateInsert:
    """Tests for the simulated bill/coin insertion endpoint."""

    async def test_simulate_bill_insert_updates_amount(self, client):
        start = (await _start_transaction(client)).json()
        tx_id = start["transaction_id"]

        resp = await _simulate_bill_insert(client, tx_id, denom=100)
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted_amount"] == 100

    async def test_simulate_insert_wrong_id_returns_404(self, client):
        await _start_transaction(client)
        resp = await _simulate_bill_insert(client, "wrong-id", denom=100)
        assert resp.status_code == 404

    async def test_simulate_coin_insert_updates_amount(self, client):
        start = (await _start_transaction(client)).json()
        tx_id = start["transaction_id"]

        resp = await client.post(
            f"/api/v1/transaction/{tx_id}/simulate-insert",
            json={"denom": 10, "insert_type": "coin"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted_amount"] == 10

    async def test_simulate_multiple_inserts_accumulate(self, client):
        start = (await _start_transaction(client)).json()
        tx_id = start["transaction_id"]

        await _simulate_bill_insert(client, tx_id, denom=100)
        resp = await _simulate_bill_insert(client, tx_id, denom=50)
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted_amount"] == 150

    async def test_simulate_insert_transitions_to_waiting_for_confirmation(
        self, client
    ):
        """When enough money is inserted, state moves to WAITING_FOR_CONFIRMATION."""
        start = (await _start_transaction(client)).json()
        tx_id = start["transaction_id"]

        # Target is 200; insert exactly 200 via two PHP_100 bills
        await _simulate_bill_insert(client, tx_id, denom=100)
        resp = await _simulate_bill_insert(client, tx_id, denom=100)
        body = resp.json()
        assert body["inserted_amount"] == 200
        assert body["state"] == "WAITING_FOR_CONFIRMATION"


# ---------------------------------------------------------------------------
# Tests: POST /api/v1/transaction/{id}/confirm
# ---------------------------------------------------------------------------


class TestConfirmTransaction:
    """Tests for the transaction confirmation (dispense) endpoint."""

    async def test_confirm_without_enough_inserted_returns_400(self, client):
        """Confirming before inserting enough money should fail."""
        start = (await _start_transaction(client)).json()
        tx_id = start["transaction_id"]

        # Insert only 100 of required 200
        await _simulate_bill_insert(client, tx_id, denom=100)

        resp = await client.post(f"/api/v1/transaction/{tx_id}/confirm")
        assert resp.status_code == 400

    async def test_confirm_wrong_id_returns_404(self, client):
        start = (await _start_transaction(client)).json()
        tx_id = start["transaction_id"]
        await _simulate_bill_insert(client, tx_id, denom=100)
        await _simulate_bill_insert(client, tx_id, denom=100)

        resp = await client.post("/api/v1/transaction/wrong-id/confirm")
        assert resp.status_code == 404

    async def test_confirm_dispenses_and_completes(self, client):
        """Full confirm: insert enough, then confirm triggers dispense."""
        start = (await _start_transaction(client)).json()
        tx_id = start["transaction_id"]

        await _simulate_bill_insert(client, tx_id, denom=100)
        await _simulate_bill_insert(client, tx_id, denom=100)

        resp = await client.post(f"/api/v1/transaction/{tx_id}/confirm")
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "COMPLETE"
        assert body["dispensed_amount"] == 200
        assert body["dispense_plan"] is not None
        assert body["dispense_result"] is not None

    async def test_confirm_sets_completed_at(self, client):
        start = (await _start_transaction(client)).json()
        tx_id = start["transaction_id"]

        await _simulate_bill_insert(client, tx_id, denom=100)
        await _simulate_bill_insert(client, tx_id, denom=100)

        resp = await client.post(f"/api/v1/transaction/{tx_id}/confirm")
        body = resp.json()
        assert body["completed_at"] is not None


# ---------------------------------------------------------------------------
# Tests: Full lifecycle
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """End-to-end lifecycle: start -> insert(s) -> confirm."""

    async def test_full_bill_to_bill_lifecycle(self, client):
        """Complete happy-path lifecycle for a bill-to-bill transaction."""
        # 1. Start transaction
        start_resp = await _start_transaction(client)
        assert start_resp.status_code == 200
        tx = start_resp.json()
        tx_id = tx["transaction_id"]
        assert tx["state"] == "WAITING_FOR_BILL"
        assert tx["inserted_amount"] == 0

        # 2. Insert first bill (PHP 100)
        ins1 = (await _simulate_bill_insert(client, tx_id, denom=100)).json()
        assert ins1["inserted_amount"] == 100
        assert ins1["state"] == "WAITING_FOR_BILL"  # still need more

        # 3. Insert second bill (PHP 100) -- should reach target
        ins2 = (await _simulate_bill_insert(client, tx_id, denom=100)).json()
        assert ins2["inserted_amount"] == 200
        assert ins2["state"] == "WAITING_FOR_CONFIRMATION"

        # 4. Verify GET reflects the same state
        get_resp = await client.get(f"/api/v1/transaction/{tx_id}")
        assert get_resp.status_code == 200
        get_body = get_resp.json()
        assert get_body["state"] == "WAITING_FOR_CONFIRMATION"
        assert get_body["inserted_amount"] == 200

        # 5. Confirm -> dispense -> complete
        confirm_resp = await client.post(
            f"/api/v1/transaction/{tx_id}/confirm",
        )
        assert confirm_resp.status_code == 200
        final = confirm_resp.json()
        assert final["state"] == "COMPLETE"
        assert final["dispensed_amount"] == 200
        assert final["completed_at"] is not None

    async def test_lifecycle_with_overpayment(self, client):
        """Insert more than target_amount; confirm still dispenses target."""
        payload = {
            "type": "bill-to-bill",
            "amount": 100,
            "fee": 0,
            "selected_dispense_denoms": [50, 20],
        }
        start = (await _start_transaction(client, payload)).json()
        tx_id = start["transaction_id"]

        # Insert PHP 100 + PHP 50 = 150 (target is 100)
        await _simulate_bill_insert(client, tx_id, denom=100)
        # After 100, target met, state should be WAITING_FOR_CONFIRMATION
        get_resp = await client.get(f"/api/v1/transaction/{tx_id}")
        assert get_resp.json()["state"] == "WAITING_FOR_CONFIRMATION"

        # Confirm
        confirm = await client.post(f"/api/v1/transaction/{tx_id}/confirm")
        assert confirm.status_code == 200
        body = confirm.json()
        assert body["state"] == "COMPLETE"
        # Dispensed amount should equal the target_amount, not inserted_amount
        assert body["dispensed_amount"] == 100

    async def test_lifecycle_start_cancel_restart(self, client):
        """Start, insert some bills, cancel, then start a fresh transaction."""
        # Start first transaction
        start1 = (await _start_transaction(client)).json()
        tx_id1 = start1["transaction_id"]

        # Insert one bill
        await _simulate_bill_insert(client, tx_id1, denom=100)

        # Cancel
        cancel = await client.delete(f"/api/v1/transaction/{tx_id1}")
        assert cancel.status_code == 200
        assert cancel.json()["state"] == "CANCELLED"

        # Start a new transaction
        start2 = await _start_transaction(client)
        assert start2.status_code == 200
        tx_id2 = start2.json()["transaction_id"]
        assert tx_id2 != tx_id1
        assert start2.json()["inserted_amount"] == 0

    async def test_lifecycle_with_fee(self, client):
        """Transaction with a fee requires inserted_amount >= target_amount + fee."""
        payload = {
            "type": "bill-to-bill",
            "amount": 100,
            "fee": 50,
            "selected_dispense_denoms": [100, 50],
        }
        start = (await _start_transaction(client, payload)).json()
        tx_id = start["transaction_id"]
        assert start["total_due"] == 150  # amount + fee

        # Insert 100 -- not enough (need 150)
        ins1 = (await _simulate_bill_insert(client, tx_id, denom=100)).json()
        assert ins1["state"] == "WAITING_FOR_BILL"
        assert ins1["inserted_amount"] == 100

        # Insert another 50 -- now total is 150, meets total_due
        ins2 = (await _simulate_bill_insert(client, tx_id, denom=50)).json()
        assert ins2["state"] == "WAITING_FOR_CONFIRMATION"
        assert ins2["inserted_amount"] == 150

        # Confirm -- dispenses the target_amount (100), not total_due
        confirm = await client.post(f"/api/v1/transaction/{tx_id}/confirm")
        assert confirm.status_code == 200
        body = confirm.json()
        assert body["state"] == "COMPLETE"
        assert body["dispensed_amount"] == 100

    async def test_lifecycle_coin_inserts(self, client):
        """Transaction using coin inserts instead of bills."""
        payload = {
            "type": "coin-to-bill",
            "amount": 100,
            "fee": 0,
            "selected_dispense_denoms": [100],
        }
        start = (await _start_transaction(client, payload)).json()
        tx_id = start["transaction_id"]

        # Insert coins: 10 x 10 = 100
        for _ in range(9):
            resp = await client.post(
                f"/api/v1/transaction/{tx_id}/simulate-insert",
                json={"denom": 10, "insert_type": "coin"},
            )
            assert resp.status_code == 200
            assert resp.json()["state"] == "WAITING_FOR_BILL"

        # 10th coin brings total to 100
        resp = await client.post(
            f"/api/v1/transaction/{tx_id}/simulate-insert",
            json={"denom": 10, "insert_type": "coin"},
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "WAITING_FOR_CONFIRMATION"
        assert resp.json()["inserted_amount"] == 100

        # Confirm
        confirm = await client.post(f"/api/v1/transaction/{tx_id}/confirm")
        assert confirm.status_code == 200
        assert confirm.json()["state"] == "COMPLETE"
        assert confirm.json()["dispensed_amount"] == 100
