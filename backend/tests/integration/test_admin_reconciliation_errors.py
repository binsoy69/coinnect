from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.admin import router
from app.core.errors import EWalletTransactionError, HardwareError
from app.models.db_models import DispenseExecution, PhysicalOperation


@pytest.fixture
def reconciliation_app(db_session_factory):
    app = FastAPI()
    app.include_router(router)
    app.state.admin_sessions = SimpleNamespace(
        validate=lambda token: SimpleNamespace(session_id="technician")
    )
    app.state.db_session_factory = db_session_factory
    return app


async def test_missing_wallet_transaction_returns_conflict(reconciliation_app):
    orchestrator = AsyncMock()
    orchestrator._record.side_effect = EWalletTransactionError("Transaction not found")
    reconciliation_app.state.ewallet_orchestrator = orchestrator
    async with AsyncClient(transport=ASGITransport(app=reconciliation_app), base_url="http://test") as client:
        response = await client.post("/admin/ewallet/converter-id/reconcile", headers={"Authorization": "Bearer admin"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Transaction not found"
    orchestrator._verify_and_dispense_cash_out.assert_not_awaited()


@pytest.mark.parametrize("error_code, expected_status", [("NOT_FOUND", 200), ("BUSY", 503)])
async def test_ack_error_preserves_verified_counts(reconciliation_app, db_session_factory, error_code, expected_status):
    async with db_session_factory() as session:
        session.add(DispenseExecution(id="execution", source_kind="STANDARD", transaction_id="tx", requested_amount=20))
        session.add(PhysicalOperation(id="operation", execution_id="execution", transaction_id="tx",
            sequence=0, controller="COIN", denomination="PHP_10", denomination_value=10,
            requested_count=2, state="AMBIGUOUS"))
        await session.commit()
    inventory = AsyncMock()
    reconciliation_app.state.inventory_service = inventory
    controller = AsyncMock()
    controller.acknowledge_operation.side_effect = HardwareError(error_code)
    reconciliation_app.state.coin_controller = controller
    async with AsyncClient(transport=ASGITransport(app=reconciliation_app), base_url="http://test") as client:
        response = await client.post("/admin/physical-operations/operation/reconcile",
            headers={"Authorization": "Bearer admin"},
            json={"actual_dispensed_count": 1, "resolution_notes": "Verified one coin"})
        assert response.status_code == expected_status
        repeated = await client.post("/admin/physical-operations/operation/reconcile",
            headers={"Authorization": "Bearer admin"},
            json={"actual_dispensed_count": 1, "resolution_notes": "Verified one coin"})
        assert repeated.status_code == 409
    async with db_session_factory() as session:
        operation = await session.get(PhysicalOperation, "operation")
        assert operation.state == "RECONCILED"
        assert operation.confirmed_count == 1
        assert operation.inventory_reconciled
    inventory.restore_in_session.assert_awaited_once()
    assert inventory.restore_in_session.call_args.args[1] == {("COIN_DISPENSER", "PHP_10"): 1}
    controller.acknowledge_operation.assert_awaited_once_with("operation")
