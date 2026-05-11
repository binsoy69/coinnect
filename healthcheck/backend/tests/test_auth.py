import pytest


async def test_missing_healthcheck_pin_fails_closed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HEALTHCHECK_PIN", raising=False)
    monkeypatch.setenv("HEALTHCHECK_ENV_FILE", str(tmp_path / "missing.env"))

    from healthcheck_api.main import create_app

    app = create_app()
    with pytest.raises(RuntimeError, match="HEALTHCHECK_PIN"):
        async with app.router.lifespan_context(app):
            pass


async def test_invalid_pin_rejected(app_client):
    _app, client = app_client

    resp = await client.post("/api/v1/auth/login", json={"pin": "bad"})

    assert resp.status_code == 401


async def test_valid_pin_returns_token(app_client):
    _app, client = app_client

    resp = await client.post("/api/v1/auth/login", json={"pin": "123456"})

    assert resp.status_code == 200
    assert resp.json()["token"]


async def test_auth_required_for_components(app_client):
    _app, client = app_client

    resp = await client.get("/api/v1/components")

    assert resp.status_code == 401
