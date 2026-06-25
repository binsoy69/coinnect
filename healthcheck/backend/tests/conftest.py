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
async def app_client(tmp_path, monkeypatch):
    from healthcheck_api.main import create_app

    monkeypatch.setenv(
        "HEALTHCHECK_EWALLET_DB_URL",
        f"sqlite+aiosqlite:///{tmp_path / 'healthcheck_ewallet.db'}",
    )
    monkeypatch.setenv(
        "HEALTHCHECK_PUBLIC_BASE_URL",
        "https://healthcheck.example.com",
    )
    monkeypatch.setenv("PAYMONGO_SANDBOX", "true")
    monkeypatch.setenv("PAYMONGO_SECRET_KEY", "sk_test_healthcheck")
    monkeypatch.setenv("PAYMONGO_PUBLIC_KEY", "pk_test_healthcheck")
    monkeypatch.setenv("PAYMONGO_WEBHOOK_SECRET", "whsec_healthcheck")
    monkeypatch.setenv("PAYMONGO_SOURCE_ACCOUNT_NUMBER", "source-001")
    monkeypatch.setenv("PAYMONGO_SOURCE_ACCOUNT_NAME", "Coinnect")
    monkeypatch.setenv("PAYMONGO_SOURCE_ACCOUNT_BIC", "PAEYPHM2XXX")
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
