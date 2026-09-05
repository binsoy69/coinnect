"""Integration tests for the converter options and quote endpoints."""

import pytest
from unittest.mock import AsyncMock
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.router import api_router
from app.api.ws import ConnectionManager
from app.core.config import Settings
from app.models.db_models import Base, ConverterQuote
from app.services.machine_status import MachineStatus


@pytest.fixture
async def quote_test_app():
    app = FastAPI()
    app.include_router(api_router)

    settings = Settings(
        use_mock_serial=True,
        use_mock_hardware=True,
        fee_bill_to_bill=5,
        fee_bill_to_coin=5,
        fee_coin_to_bill=5,
        environment="test",
        db_url="sqlite+aiosqlite:///:memory:",
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    machine_status = MachineStatus(settings)
    # Available stock: 20s, 50s, 100s
    machine_status.set_dispenser_counts({
        "PHP_20": 10,
        "PHP_50": 10,
        "PHP_100": 10,
        "PHP_200": 0,
        "PHP_500": 0,
        "PHP_1000": 0,
    })
    machine_status.set_coin_counts({
        "PHP_1": 50,
        "PHP_5": 50,
        "PHP_10": 50,
        "PHP_20": 50,
    })

    ws_manager = ConnectionManager()
    ws_manager.broadcast = AsyncMock()

    app.state.settings = settings
    app.state.db_session_factory = session_factory
    app.state.machine_status = machine_status
    app.state.ws_manager = ws_manager

    return app


@pytest.mark.asyncio
async def test_get_transaction_options_disables_20_bill_to_bill(quote_test_app):
    """Default ₱20 bill-to-bill is disabled because ₱20 - ₱5 = ₱15 cannot be made of bills."""
    transport = ASGITransport(app=quote_test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/transaction/options?type=bill-to-bill")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service_type"] == "bill-to-bill"
        assert data["fee"] == 5

        options = {opt["amount"]: opt for opt in data["options"]}
        assert 20 in options
        assert options[20]["enabled"] is False
        assert options[20]["reason_code"] == "NO_EXACT_COMBINATION"
        assert "₱15" in options[20]["reason"]

        # 100 should be enabled (100 - 5 = 95 -> e.g. 50 + 20*2 = 90? wait, 95 needs 5 which is not in bills!
        # Wait! Can 95 be made of bills? Bills are 20, 50, 100, 200, 500, 1000!
        # Can any sum of {20, 50, 100, ...} equal 95? No! Because 95 is odd and ends in 5, but bills ending in 5
        # is only 50 (which leaves 45, which cannot be formed by 20)!
        # So 95 cannot be made of bills!
        # What about 50? 50 - 5 = 45 -> cannot be made of bills.
        # What about coin-to-bill for 100? Payout is 100! 100 can be made of bills (1x 100)!
        # Let's test coin-to-bill for 100:
        resp_c2b = await client.get("/api/v1/transaction/options?type=coin-to-bill")
        assert resp_c2b.status_code == 200
        data_c2b = resp_c2b.json()
        options_c2b = {opt["amount"]: opt for opt in data_c2b["options"]}
        assert options_c2b[100]["enabled"] is True
        assert options_c2b[100]["reason_code"] is None


@pytest.mark.asyncio
async def test_create_quote_success_and_db_persistence(quote_test_app):
    """POST /transaction/quote creates a proposal and persists in converter_quotes."""
    transport = ASGITransport(app=quote_test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # coin-to-bill with amount=100 -> payout=100, fee=5, total_due=105
        resp = await client.post(
            "/api/v1/transaction/quote",
            json={
                "type": "coin-to-bill",
                "amount": 100,
                "requested_counts": {"PHP_50": 2},
            },
        )
        assert resp.status_code == 200
        quote = resp.json()
        assert quote["service_type"] == "coin-to-bill"
        assert quote["input_amount"] == 100
        assert quote["fee"] == 5
        assert quote["total_due"] == 105
        assert quote["payout_amount"] == 100
        assert quote["is_substitution"] is False
        assert len(quote["items"]) == 1
        assert quote["items"][0]["denom"] == "PHP_50"
        assert quote["items"][0]["count"] == 2

        # Verify quote is stored in database
        session_factory = quote_test_app.state.db_session_factory
        async with session_factory() as session:
            record = await session.get(ConverterQuote, quote["id"])
            assert record is not None
            assert record.payout_amount == 100
            assert record.total_due == 105


@pytest.mark.asyncio
async def test_create_quote_substitution_flag(quote_test_app):
    """POST /transaction/quote flags substitution if requested count cannot be met."""
    # Set 50s to 0 so requested 2x 50 cannot be met, only 100 is available
    quote_test_app.state.machine_status.set_dispenser_counts({
        "PHP_20": 10,
        "PHP_50": 0,
        "PHP_100": 10,
    })
    transport = ASGITransport(app=quote_test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/transaction/quote",
            json={
                "type": "coin-to-bill",
                "amount": 100,
                "requested_counts": {"PHP_50": 2},
            },
        )
        assert resp.status_code == 200
        quote = resp.json()
        assert quote["is_substitution"] is True
        assert quote["substitution_notice"] is not None
        assert quote["items"][0]["denom"] == "PHP_100"
        assert quote["items"][0]["count"] == 1
