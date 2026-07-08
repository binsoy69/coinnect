"""Unit tests for ForexTransactionOrchestrator."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.errors import ConnectivityError, ForexError, TransactionError
from app.models.forex import ExchangeRateCache, ForexQuote
from app.services.forex_rate_service import ForexRateService
from app.services.forex_transaction_orchestrator import ForexTransactionOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_settings():
    from app.core.config import Settings
    return Settings(
        use_mock_serial=True,
        use_mock_hardware=True,
        mock_delay=0.0,
        serial_port_bill="MOCK_BILL",
        serial_port_coin="MOCK_COIN",
        environment="test",
        db_url="sqlite+aiosqlite:///:memory:",
        forex_api_key="test_key",
        forex_fee_usd_to_php=5.0,
        forex_fee_php_to_usd=5.0,
        forex_fee_eur_to_php=4.0,
        forex_fee_php_to_eur=4.0,
    )


@pytest.fixture
def mock_ws():
    ws = AsyncMock()
    ws.broadcast = AsyncMock()
    return ws


@pytest.fixture
def mock_forex_rate_service(test_settings, mock_ws):
    """ForexRateService with valid cache."""
    service = ForexRateService(test_settings, mock_ws)
    now = datetime.utcnow()
    service._cache = ExchangeRateCache(
        rates={"USD": 58.7656, "EUR": 61.7246},
        fetched_at=now,
        expires_at=now + timedelta(hours=24),
    )
    service._is_online = True
    # Mock the connectivity check
    service.check_forex_available = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_forex_rate_service_offline(test_settings, mock_ws):
    """ForexRateService that is offline."""
    service = ForexRateService(test_settings, mock_ws)
    service._is_online = False
    service.check_forex_available = AsyncMock(return_value=False)
    return service


@pytest.fixture
def mock_bill_acceptor():
    acceptor = AsyncMock()
    acceptor.set_expected_currency = MagicMock()
    return acceptor


@pytest.fixture
def mock_dispense_orchestrator():
    disp = AsyncMock()
    result = MagicMock()
    result.success = True
    result.total_dispensed = 5583
    result.error = None
    result.shortfall = 0
    result.claim_ticket_code = None
    result.model_dump = MagicMock(return_value={
        "success": True,
        "total_dispensed": 5583,
    })
    disp.execute_dispense = AsyncMock(return_value=result)
    return disp


@pytest.fixture
def mock_machine_status():
    status = MagicMock()
    snapshot = MagicMock()
    snapshot.security.tamper_active = False
    snapshot.consumables.bill_dispenser_counts = {
        "PHP_1000": 50, "PHP_500": 50, "PHP_200": 50,
        "PHP_100": 100, "PHP_50": 100, "PHP_20": 200,
        "USD_50": 20, "USD_10": 50,
        "EUR_10": 30, "EUR_5": 50,
    }
    snapshot.consumables.coin_counts = {
        "PHP_20": 200, "PHP_10": 200, "PHP_5": 200, "PHP_1": 500,
    }
    status.snapshot = MagicMock(return_value=snapshot)
    return status


@pytest.fixture
def mock_machine_status_tampered():
    status = MagicMock()
    snapshot = MagicMock()
    snapshot.security.tamper_active = True
    status.snapshot = MagicMock(return_value=snapshot)
    return status


@pytest.fixture
async def db_session_factory():
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from app.models.db_models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    yield factory
    await engine.dispose()


@pytest.fixture
def forex_orchestrator(
    mock_bill_acceptor,
    mock_dispense_orchestrator,
    mock_machine_status,
    mock_ws,
    mock_forex_rate_service,
    db_session_factory,
):
    return ForexTransactionOrchestrator(
        bill_acceptor=mock_bill_acceptor,
        dispense_orchestrator=mock_dispense_orchestrator,
        machine_status=mock_machine_status,
        ws_manager=mock_ws,
        forex_rate_service=mock_forex_rate_service,
        db_session_factory=db_session_factory,
    )


# ---------------------------------------------------------------------------
# 1. Start transaction tests
# ---------------------------------------------------------------------------


class TestStartTransaction:
    @pytest.mark.asyncio
    async def test_start_success(self, forex_orchestrator):
        """Should create transaction with locked rate."""
        state = await forex_orchestrator.start_transaction(
            service_type="usd-to-php",
            selected_amount=100,
        )
        assert state["transaction_id"] is not None
        assert state["from_currency"] == "USD"
        assert state["to_currency"] == "PHP"
        assert state["exchange_rate"] == 58.7656
        assert forex_orchestrator.has_active_transaction

    @pytest.mark.asyncio
    async def test_start_offline_raises(
        self,
        mock_bill_acceptor,
        mock_dispense_orchestrator,
        mock_machine_status,
        mock_ws,
        mock_forex_rate_service_offline,
        db_session_factory,
    ):
        """Should raise ConnectivityError when offline."""
        orch = ForexTransactionOrchestrator(
            bill_acceptor=mock_bill_acceptor,
            dispense_orchestrator=mock_dispense_orchestrator,
            machine_status=mock_machine_status,
            ws_manager=mock_ws,
            forex_rate_service=mock_forex_rate_service_offline,
            db_session_factory=db_session_factory,
        )
        with pytest.raises(ConnectivityError):
            await orch.start_transaction("usd-to-php", 100)

    @pytest.mark.asyncio
    async def test_start_tampered_raises(
        self,
        mock_bill_acceptor,
        mock_dispense_orchestrator,
        mock_machine_status_tampered,
        mock_ws,
        mock_forex_rate_service,
        db_session_factory,
    ):
        """Should raise TransactionError when machine is tampered."""
        orch = ForexTransactionOrchestrator(
            bill_acceptor=mock_bill_acceptor,
            dispense_orchestrator=mock_dispense_orchestrator,
            machine_status=mock_machine_status_tampered,
            ws_manager=mock_ws,
            forex_rate_service=mock_forex_rate_service,
            db_session_factory=db_session_factory,
        )
        with pytest.raises(TransactionError):
            await orch.start_transaction("usd-to-php", 100)

    @pytest.mark.asyncio
    async def test_start_already_active_raises(self, forex_orchestrator):
        """Should raise TransactionError when another transaction is active."""
        await forex_orchestrator.start_transaction("usd-to-php", 100)
        with pytest.raises(TransactionError, match="already in progress"):
            await forex_orchestrator.start_transaction("eur-to-php", 50)

    @pytest.mark.asyncio
    async def test_start_sets_bill_acceptor_currency(
        self, forex_orchestrator, mock_bill_acceptor
    ):
        """Should configure bill acceptor for expected input currency."""
        await forex_orchestrator.start_transaction("usd-to-php", 100)
        mock_bill_acceptor.set_expected_currency.assert_called_with("USD")

    @pytest.mark.asyncio
    async def test_start_php_to_usd_sets_php_currency(
        self, forex_orchestrator, mock_bill_acceptor
    ):
        """For PHP->USD, bill acceptor expects PHP."""
        await forex_orchestrator.start_transaction("php-to-usd", 50)
        mock_bill_acceptor.set_expected_currency.assert_called_with("PHP")


# ---------------------------------------------------------------------------
# 2. Cancel transaction tests
# ---------------------------------------------------------------------------


class TestCancelTransaction:
    @pytest.mark.asyncio
    async def test_cancel_success(self, forex_orchestrator):
        """Should cancel and clean up."""
        await forex_orchestrator.start_transaction("usd-to-php", 100)
        state = await forex_orchestrator.cancel_transaction()
        assert state["state"] in ("cancelled", "CANCELLED")
        assert not forex_orchestrator.has_active_transaction

    @pytest.mark.asyncio
    async def test_cancel_no_active_raises(self, forex_orchestrator):
        """Should raise when no transaction is active."""
        with pytest.raises(TransactionError, match="No active"):
            await forex_orchestrator.cancel_transaction()

    @pytest.mark.asyncio
    async def test_cancel_resets_bill_acceptor_to_php(
        self, forex_orchestrator, mock_bill_acceptor
    ):
        """After cancel, bill acceptor should be reset to PHP."""
        await forex_orchestrator.start_transaction("usd-to-php", 100)
        mock_bill_acceptor.set_expected_currency.reset_mock()
        await forex_orchestrator.cancel_transaction()
        mock_bill_acceptor.set_expected_currency.assert_called_with("PHP")


# ---------------------------------------------------------------------------
# 3. Get transaction state tests
# ---------------------------------------------------------------------------


class TestGetTransactionState:
    @pytest.mark.asyncio
    async def test_get_state_returns_forex_fields(self, forex_orchestrator):
        """State should include forex-specific fields."""
        state = await forex_orchestrator.start_transaction("usd-to-php", 100)
        assert "from_currency" in state
        assert "to_currency" in state
        assert "exchange_rate" in state
        assert "forex_fee_percentage" in state
        assert "converted_amount" in state

    @pytest.mark.asyncio
    async def test_get_state_nonexistent_raises(self, forex_orchestrator):
        """Should raise for unknown transaction ID."""
        with pytest.raises(TransactionError, match="not found"):
            await forex_orchestrator.get_transaction_state("nonexistent-id")


class TestRecoverPendingTransactions:
    @pytest.mark.asyncio
    async def test_no_pending_forex_entries_is_noop(self, forex_orchestrator):
        """When there are no pending forex WAL entries, recovery does nothing."""
        await forex_orchestrator.recover_pending_transactions()

    @pytest.mark.asyncio
    async def test_recovers_pending_forex_wal_entries(
        self, forex_orchestrator, db_session_factory
    ):
        """Pending forex WAL entries are recovered to ERROR with CRASH_RECOVERY."""
        import uuid
        from app.models.db_models import TransactionRecord, WALEntry, WALStatus, TransactionState
        
        tx_id = str(uuid.uuid4())

        async with db_session_factory() as session:
            record = TransactionRecord(
                id=tx_id,
                type="forex-usd-to-php",
                state=TransactionState.DISPENSING.value,
                target_amount=500,
                fee=0,
                total_due=500,
            )
            session.add(record)

            wal = WALEntry(
                transaction_id=tx_id,
                action="FOREX_RATE_LOCKED",
                data={},
                status=WALStatus.PENDING.value,
            )
            session.add(wal)
            await session.commit()
            wal_id = wal.id

        await forex_orchestrator.recover_pending_transactions()

        async with db_session_factory() as session:
            record = await session.get(TransactionRecord, tx_id)
            assert record.state == TransactionState.ERROR.value
            assert record.error_code == "CRASH_RECOVERY"
            assert "FOREX_RATE_LOCKED" in record.error_message

            wal = await session.get(WALEntry, wal_id)
            assert wal.status == WALStatus.ROLLED_BACK.value

    @pytest.mark.asyncio
    async def test_recovery_ignores_non_forex_transactions(
        self, forex_orchestrator, db_session_factory
    ):
        """Forex recovery ignores standard money-changer transactions (type not starting with 'forex-')."""
        import uuid
        from app.models.db_models import TransactionRecord, WALEntry, WALStatus, TransactionState
        
        tx_id = str(uuid.uuid4())

        async with db_session_factory() as session:
            record = TransactionRecord(
                id=tx_id,
                type="bill-to-bill",
                state=TransactionState.DISPENSING.value,
                target_amount=500,
                fee=0,
                total_due=500,
            )
            session.add(record)

            wal = WALEntry(
                transaction_id=tx_id,
                action="DISPENSE_START",
                data={},
                status=WALStatus.PENDING.value,
            )
            session.add(wal)
            await session.commit()
            wal_id = wal.id

        await forex_orchestrator.recover_pending_transactions()

        async with db_session_factory() as session:
            record = await session.get(TransactionRecord, tx_id)
            assert record.state == TransactionState.DISPENSING.value

            wal = await session.get(WALEntry, wal_id)
            assert wal.status == WALStatus.PENDING.value

