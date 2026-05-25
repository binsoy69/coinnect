async def test_private_lan_frontend_origin_allowed(app_client):
    _app, client = app_client

    resp = await client.options(
        "/api/v1/status",
        headers={
            "Origin": "http://192.168.1.50:5174",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://192.168.1.50:5174"


async def test_public_frontend_origin_rejected(app_client):
    _app, client = app_client

    resp = await client.options(
        "/api/v1/status",
        headers={
            "Origin": "http://example.com:5174",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert "access-control-allow-origin" not in resp.headers
