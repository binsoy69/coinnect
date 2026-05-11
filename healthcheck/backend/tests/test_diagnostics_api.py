async def test_component_registry_contains_expected_groups(authed_client):
    _app, client = authed_client

    resp = await client.get("/api/v1/components")

    assert resp.status_code == 200
    groups = resp.json()
    group_ids = {group["id"] for group in groups}
    assert {
        "connectivity",
        "rpi_bill_acceptor",
        "bill_controller",
        "coin_security",
    }.issubset(group_ids)


async def test_login_run_and_recent_results_flow(authed_client):
    _app, client = authed_client

    run_resp = await client.post("/api/v1/tests/connectivity_bill_ping/run")
    assert run_resp.status_code == 200
    result = run_resp.json()
    assert result["status"] == "passed"
    assert result["response"]["message"] == "PONG"

    recent_resp = await client.get("/api/v1/runs/recent")
    assert recent_resp.status_code == 200
    recent = recent_resp.json()
    assert recent[0]["test_id"] == "connectivity_bill_ping"


async def test_unknown_test_returns_404(authed_client):
    _app, client = authed_client

    resp = await client.post("/api/v1/tests/not_a_test/run")

    assert resp.status_code == 404


async def test_busy_lock_returns_409(authed_client):
    app, client = authed_client
    runner = app.state.diagnostics_runner

    await runner._lock.acquire()
    try:
        resp = await client.post("/api/v1/tests/connectivity_bill_ping/run")
    finally:
        runner._lock.release()

    assert resp.status_code == 409


async def test_mock_serial_dispense_and_security_commands_pass(authed_client):
    _app, client = authed_client

    bill_resp = await client.post("/api/v1/tests/bill_dispense_PHP_20/run")
    assert bill_resp.status_code == 200
    assert bill_resp.json()["status"] == "passed"
    assert bill_resp.json()["response"]["dispensed"] == 1

    security_resp = await client.post("/api/v1/tests/coin_security_status/run")
    assert security_resp.status_code == 200
    assert security_resp.json()["status"] == "passed"
    assert "locked" in security_resp.json()["response"]
