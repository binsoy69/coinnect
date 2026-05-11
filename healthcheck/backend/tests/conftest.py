import os
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["HEALTHCHECK_PIN"] = "123456"
os.environ["USE_MOCK_SERIAL"] = "true"
os.environ["USE_MOCK_HARDWARE"] = "true"
os.environ["MOCK_DELAY"] = "0"
os.environ["SERIAL_PORT_BILL"] = "MOCK_BILL"
os.environ["SERIAL_PORT_COIN"] = "MOCK_COIN"
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "DEBUG"


@asynccontextmanager
async def app_lifespan(app):
    async with app.router.lifespan_context(app):
        yield


@pytest.fixture
async def app_client():
    from healthcheck_api.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with app_lifespan(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield app, client


@pytest.fixture
async def authed_client(app_client):
    app, client = app_client
    resp = await client.post("/api/v1/auth/login", json={"pin": "123456"})
    assert resp.status_code == 200
    token = resp.json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return app, client
