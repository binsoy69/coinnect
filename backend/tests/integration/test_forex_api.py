"""Integration tests for forex API endpoints.

Tests the forex REST API using FastAPI TestClient with mock hardware.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.models.forex import ExchangeRateCache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_forex_rate_service():
    """Mock forex rate service with valid cache."""
    service = MagicMock()
    now = datetime.utcnow()
    service._cache = ExchangeRateCache(
        rates={"USD": 58.7656, "EUR": 61.7246},
        fetched_at=now,
        expires_at=now + timedelta(hours=24),
    )
    service.is_online = True
    service.rates_valid = True
    service.current_rates = {"USD": 58.7656, "EUR": 61.7246}
    service.get_fee_percentage = MagicMock(return_value=5.0)

    from app.models.forex import ForexQuote
    service.get_quote = MagicMock(return_value=ForexQuote(
        from_currency="USD",
        to_currency="PHP",
        rate=58.7656,
        input_amount=100,
        converted_amount=5877,
        fee_percentage=5.0,
        fee_amount=294,
        output_amount=5583,
        locked_at=now,
    ))

    service.check_forex_available = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_forex_orchestrator():
    """Mock forex transaction orchestrator."""
    orch = MagicMock()
    orch.has_active_transaction = False
    orch.active_transaction_id = None
    orch.start_transaction = AsyncMock(return_value={
        "transaction_id": "test-forex-tx-1",
        "type": "forex-usd-to-php",
        "state": "waiting_for_bill",
        "target_amount": 5583,
        "fee": 294,
        "total_due": 100,
        "inserted_amount": 0,
        "dispensed_amount": 0,
        "inserted_denominations": {},
        "dispense_plan": None,
        "dispense_result": None,
        "selected_dispense_denoms": [],
        "error_code": None,
        "error_message": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "from_currency": "USD",
        "to_currency": "PHP",
        "exchange_rate": 58.7656,
        "rate_locked_at": datetime.utcnow().isoformat(),
        "forex_fee_percentage": 5.0,
        "converted_amount": 5877,
    })
    orch.cancel_transaction = AsyncMock(return_value={
        "transaction_id": "test-forex-tx-1",
        "type": "forex-usd-to-php",
        "state": "cancelled",
        "target_amount": 5583,
        "fee": 294,
        "total_due": 100,
        "inserted_amount": 0,
        "dispensed_amount": 0,
        "inserted_denominations": {},
        "dispense_plan": None,
        "dispense_result": None,
        "selected_dispense_denoms": [],
        "error_code": None,
        "error_message": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "from_currency": "USD",
        "to_currency": "PHP",
        "exchange_rate": 58.7656,
        "rate_locked_at": None,
        "forex_fee_percentage": 5.0,
        "converted_amount": 5877,
    })
    return orch


@pytest.fixture
def app(mock_forex_rate_service, mock_forex_orchestrator):
    """FastAPI app with mocked forex services."""
    from fastapi import FastAPI
    from app.api.forex import router as forex_router

    test_app = FastAPI()
    test_app.include_router(forex_router, prefix="/api/v1")
    test_app.state.forex_rate_service = mock_forex_rate_service
    test_app.state.forex_transaction_orchestrator = mock_forex_orchestrator
    test_app.state.settings = MagicMock(use_mock_hardware=True)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. GET /forex/rates
# ---------------------------------------------------------------------------


class TestGetRates:
    def test_returns_rates(self, client):
        resp = client.get("/api/v1/forex/rates")
        assert resp.status_code == 200
        data = resp.json()
        assert "rates" in data
        assert data["rates"]["USD"] == 58.7656
        assert data["rates"]["EUR"] == 61.7246
        assert data["online"] is True
        assert data["valid"] is True

    def test_returns_fees(self, client):
        resp = client.get("/api/v1/forex/rates")
        data = resp.json()
        assert "fees" in data
        assert "usd-to-php" in data["fees"]


# ---------------------------------------------------------------------------
# 2. GET /forex/quote
# ---------------------------------------------------------------------------


class TestGetQuote:
    def test_get_quote(self, client):
        resp = client.get("/api/v1/forex/quote/usd-to-php?amount=100")
        assert resp.status_code == 200
        data = resp.json()
        assert data["from_currency"] == "USD"
        assert data["to_currency"] == "PHP"
        assert data["rate"] == 58.7656
        assert data["output_amount"] == 5583


# ---------------------------------------------------------------------------
# 3. POST /forex/transaction
# ---------------------------------------------------------------------------


class TestStartTransaction:
    def test_start_transaction(self, client, mock_forex_orchestrator):
        resp = client.post("/api/v1/forex/transaction", json={
            "service_type": "usd-to-php",
            "selected_amount": 100,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["transaction_id"] == "test-forex-tx-1"
        assert data["from_currency"] == "USD"
        assert data["to_currency"] == "PHP"
        mock_forex_orchestrator.start_transaction.assert_called_once()


# ---------------------------------------------------------------------------
# 4. DELETE /forex/transaction/{id}
# ---------------------------------------------------------------------------


class TestCancelTransaction:
    def test_cancel_active(self, client, mock_forex_orchestrator):
        mock_forex_orchestrator.active_transaction_id = "test-forex-tx-1"
        resp = client.delete("/api/v1/forex/transaction/test-forex-tx-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "cancelled"

    def test_cancel_wrong_id(self, client, mock_forex_orchestrator):
        mock_forex_orchestrator.active_transaction_id = "other-id"
        resp = client.delete("/api/v1/forex/transaction/test-forex-tx-1")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. GET /forex/connectivity
# ---------------------------------------------------------------------------


class TestConnectivity:
    def test_check_connectivity(self, client):
        resp = client.get("/api/v1/forex/connectivity")
        assert resp.status_code == 200
        data = resp.json()
        assert "online" in data
        assert "forex_available" in data
