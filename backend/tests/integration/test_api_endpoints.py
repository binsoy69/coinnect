from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@asynccontextmanager
async def lifespan(app):
    async with app.router.lifespan_context(app):
        yield


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with lifespan(app):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


class TestHealthEndpoint:
    async def test_health_returns_ok(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "bill_device" in data
        assert "coin_device" in data


class TestStatusEndpoint:
    async def test_status_returns_full_state(self, client):
        resp = await client.get("/api/v1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "bill_device" in data
        assert "coin_device" in data
        assert "sorter" in data
        assert "security" in data
        assert "consumables" in data
        assert "timestamp" in data

    async def test_status_sorter_initial_state(self, client):
        resp = await client.get("/api/v1/status")
        data = resp.json()
        assert data["sorter"]["homed"] is False
        assert data["sorter"]["current_position"] == 0

    async def test_status_security_initial_state(self, client):
        resp = await client.get("/api/v1/status")
        data = resp.json()
        assert data["security"]["locked"] is True
        assert data["security"]["tamper_active"] is False

    async def test_status_consumables_structure(self, client):
        resp = await client.get("/api/v1/status")
        data = resp.json()
        consumables = data["consumables"]
        assert "bill_storage_counts" in consumables
        assert "bill_dispenser_counts" in consumables
        assert "coin_counts" in consumables
        assert "PHP_100" in consumables["bill_storage_counts"]
        assert "PHP_5" in consumables["coin_counts"]
