"""Exercise production exception handlers without starting kiosk hardware."""
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.api.ewallet import StartEWalletRequest
from app.main import create_app


@pytest.mark.asyncio
async def test_validation_does_not_expose_regex_or_submitted_values():
    app = create_app()

    @app.post("/customer-validation-test")
    async def validate(body: StartEWalletRequest):
        return body.model_dump()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/customer-validation-test", json={
            "provider": "gcash", "direction": "cash-in", "amount": 100,
            "mobile_number": "private-invalid-number", "quote_id": "quote",
            "request_key": "validation-request-key",
        })
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR"
    assert detail["errors"] == [{"field": "mobile_number", "message": "Enter an 11-digit mobile number starting with 09."}]
    assert "private-invalid-number" not in response.text
    assert "pattern" not in response.text
    assert "input" not in response.text


@pytest.mark.asyncio
async def test_http_error_preserves_recovery_metadata_without_debug_details():
    app = create_app()

    @app.get("/customer-failure-test")
    async def failure():
        raise HTTPException(409, detail={"code": "QUOTE_CHANGED", "message": "Traceback /private/server.py",
                                         "transaction_id": "test-transaction", "quote": {"quote_id": "new-quote"}})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/customer-failure-test")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "QUOTE_CHANGED"
    assert response.json()["detail"]["transaction_id"] == "test-transaction"
    assert response.json()["detail"]["quote"] == {"quote_id": "new-quote"}
    assert "Traceback" not in response.text
    assert "/private/" not in response.text
