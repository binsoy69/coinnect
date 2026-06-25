from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.admin import router as admin_router
from app.api.inventory import router as inventory_router
from app.services.admin_session import AdminSessionService
from app.services.inventory_service import InventoryService
from app.services.machine_status import MachineStatus
from app.services.operation_mode import OperationModeManager


@pytest.fixture
async def admin_app(db_session_factory, test_settings):
    test_settings.admin_pin = "2468"
    status = MachineStatus(test_settings)
    inventory = InventoryService(db_session_factory, status)
    await inventory.initialize()
    mode = OperationModeManager()
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(inventory_router, prefix="/api/v1")
    app.state.machine_status = status
    app.state.inventory_service = inventory
    app.state.admin_sessions = AdminSessionService(test_settings, mode)
    return app


async def _login(client):
    response = await client.post(
        "/api/v1/admin/session", json={"pin": "2468"}
    )
    assert response.status_code == 200
    return response.json()["token"]


async def test_admin_inventory_update_requires_bearer_token(admin_app):
    transport = ASGITransport(app=admin_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/v1/inventory/",
            json={
                "updates": [
                    {
                        "location": "BILL_DISPENSER",
                        "denomination": "PHP_100",
                        "count": 10,
                    }
                ],
                "reason": "REFILL",
            },
        )
    assert response.status_code == 401


async def test_admin_can_update_inventory_and_read_audit(admin_app):
    transport = ASGITransport(app=admin_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        update = await client.put(
            "/api/v1/inventory/",
            headers=headers,
            json={
                "updates": [
                    {
                        "location": "COIN_DISPENSER",
                        "denomination": "PHP_10",
                        "count": 25,
                    }
                ],
                "reason": "PHYSICAL_COUNT",
                "note": "Counted during opening",
            },
        )
        history = await client.get(
            "/api/v1/inventory/adjustments?source=ADMIN&limit=50",
            headers=headers,
        )

    assert update.status_code == 200
    assert update.json()["coin_counts"]["PHP_10"] == 25
    assert history.status_code == 200
    assert history.json()["adjustments"][0]["delta"] == 25


async def test_logout_invalidates_session(admin_app):
    transport = ASGITransport(app=admin_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        logout = await client.delete(
            "/api/v1/admin/session", headers=headers
        )
        validate = await client.get(
            "/api/v1/admin/session", headers=headers
        )

    assert logout.status_code == 204
    assert validate.status_code == 401
