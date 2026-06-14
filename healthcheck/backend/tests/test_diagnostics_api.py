async def test_component_registry_contains_expected_groups(authed_client):
    _app, client = authed_client

    resp = await client.get("/api/v1/components")

    assert resp.status_code == 200
    groups = resp.json()
    group_ids = {group["id"] for group in groups}
    assert {
        "connectivity",
        "rpi_bill_acceptor",
        "paperang_printer",
        "bill_ml_models",
        "bill_image_recognition",
        "bill_acceptor_full_flow",
        "bill_controller",
        "coin_security",
    }.issubset(group_ids)
    rpi_group = next(group for group in groups if group["id"] == "rpi_bill_acceptor")
    rpi_test_ids = {test["id"] for test in rpi_group["tests"]}
    assert "rpi_ir_entry" in rpi_test_ids
    assert "rpi_ir_position" not in rpi_test_ids
    coin_group = next(group for group in groups if group["id"] == "coin_security")
    coin_test_ids = {test["id"] for test in coin_group["tests"]}
    assert {
        "coin_status",
        "coin_acceptor_enable_on",
        "coin_acceptor_enable_off",
        "coin_sorter_center",
        "coin_sorter_left",
        "coin_sorter_right",
    }.issubset(coin_test_ids)
    ml_group = next(group for group in groups if group["id"] == "bill_ml_models")
    ml_test_ids = {test["id"] for test in ml_group["tests"]}
    assert {
        "bill_ml_models_php",
        "bill_ml_models_usd",
        "bill_ml_models_eur",
    }.issubset(ml_test_ids)
    assert {test["kind"] for test in ml_group["tests"]} == {"ml"}

    image_group = next(
        group for group in groups if group["id"] == "bill_image_recognition"
    )
    image_test_ids = {test["id"] for test in image_group["tests"]}
    assert {
        "bill_image_auth_php",
        "bill_image_auth_usd",
        "bill_image_auth_eur",
        "bill_image_denom_php",
        "bill_image_denom_usd",
        "bill_image_denom_eur",
    }.issubset(image_test_ids)

    flow_group = next(
        group for group in groups if group["id"] == "bill_acceptor_full_flow"
    )
    flow_test_ids = {test["id"] for test in flow_group["tests"]}
    assert {
        "bill_acceptor_flow_php",
        "bill_acceptor_flow_usd",
        "bill_acceptor_flow_eur",
    }.issubset(flow_test_ids)


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


async def test_mock_serial_coin_sorter_and_acceptor_commands_pass(authed_client):
    _app, client = authed_client

    status_resp = await client.post("/api/v1/tests/coin_status/run")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "passed"
    assert status_resp.json()["response"]["sorter_position"] == "CENTER"

    enable_resp = await client.post("/api/v1/tests/coin_acceptor_enable_on/run")
    assert enable_resp.status_code == 200
    assert enable_resp.json()["status"] == "passed"
    assert enable_resp.json()["response"]["enabled"] is True

    right_resp = await client.post("/api/v1/tests/coin_sorter_right/run")
    assert right_resp.status_code == 200
    assert right_resp.json()["status"] == "passed"
    assert right_resp.json()["response"]["sorter_angle"] == 120

    disable_resp = await client.post("/api/v1/tests/coin_acceptor_enable_off/run")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["status"] == "passed"
    assert disable_resp.json()["response"]["enabled"] is False


async def test_mock_paperang_sample_receipt_passes_without_bluetooth(authed_client):
    _app, client = authed_client

    resp = await client.post("/api/v1/tests/paperang_sample_receipt/run")

    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "passed"
    assert result["response"]["mock"] is True
    assert result["response"]["printed"] is False
    assert result["response"]["width"] == 384


async def test_mock_live_bill_auth_test_returns_result(authed_client):
    _app, client = authed_client

    resp = await client.post("/api/v1/tests/bill_image_auth_php/run")

    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "passed"
    assert result["response"]["currency"] == "PHP"
    assert result["response"]["raw_label"] == "genuine"
