import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import Settings
from app.core.constants import ControllerType
from app.drivers.serial_manager import SerialConnection, SerialManager
from app.drivers.bill_controller import BillController
from app.drivers.coin_security_controller import CoinSecurityController
from app.services.event_dispatcher import EventDispatcher
from app.services.machine_status import MachineStatus
from app.models.db_models import TransactionState, PhysicalOperation


@pytest.fixture
def settings():
    return Settings(
        use_mock_serial=True,
        serial_port_bill="MOCK_BILL",
        serial_port_coin="MOCK_COIN",
    )


@pytest.fixture
def machine_status(settings):
    return MachineStatus(settings)


@pytest.fixture
def ws_manager():
    manager = AsyncMock()
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture
def event_queue():
    return asyncio.Queue()


class TestEmergencyStopSerial:
    @pytest.mark.asyncio
    async def test_priority_command_bypasses_normal_command_lock(self, event_queue):
        conn = SerialConnection(
            port="MOCK_BILL",
            baud_rate=115200,
            controller_type=ControllerType.BILL,
            event_queue=event_queue,
            use_mock=True,
        )
        await conn.connect()

        # Simulate holding the normal command lock
        await conn._normal_command_lock.acquire()

        try:
            # A priority command should still execute because it bypasses _normal_command_lock
            resp = await conn.send_command({"cmd": "EMERGENCY_STOP"}, priority=True)
            assert resp.get("status") == "OK"
            assert resp.get("stopped") is True
        finally:
            conn._normal_command_lock.release()
            await conn.disconnect()

    @pytest.mark.asyncio
    async def test_emergency_stop_all_dispatches_to_both(self, settings):
        mgr = SerialManager(settings)
        await mgr.startup()

        results = await mgr.emergency_stop_all()
        assert "bill" in results
        assert "coin" in results
        assert results["bill"].get("status") == "OK"
        assert results["bill"].get("stopped") is True
        assert results["coin"].get("status") == "OK"
        assert results["coin"].get("stopped") is True

        await mgr.shutdown()


class TestTamperHandling:
    @pytest.mark.asyncio
    async def test_tamper_triggers_emergency_stop_and_safe_shutdown(
        self, event_queue, machine_status, ws_manager
    ):
        mock_serial = AsyncMock()
        mock_serial.emergency_stop_all = AsyncMock(return_value={"bill": {"status": "OK"}, "coin": {"status": "OK"}})

        mock_bill_acceptor = AsyncMock()
        mock_bill_acceptor.stop_all = AsyncMock()

        dispatcher = EventDispatcher(
            event_queue=event_queue,
            machine_status=machine_status,
            ws_manager=ws_manager,
            serial_manager=mock_serial,
            bill_acceptor=mock_bill_acceptor,
        )

        event_data = {
            "event": "TAMPER",
            "sensor": "SW-420_CHASSIS",
            "_controller": "COIN_SECURITY",
        }
        await dispatcher._handle_event(event_data)

        # 1. Tamper active in machine status
        assert machine_status.snapshot().security.tamper_active is True

        # 2. Emergency stop sent to controllers
        mock_serial.emergency_stop_all.assert_awaited_once()

        # 3. Bill acceptor stopped
        mock_bill_acceptor.stop_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tamper_active_transaction_creates_claim_if_cash_inserted(
        self, event_queue, machine_status, ws_manager
    ):
        mock_serial = AsyncMock()
        mock_serial.emergency_stop_all = AsyncMock()

        mock_tx_orch = AsyncMock()
        mock_tx_orch.has_active_transaction = True
        mock_tx_orch.handle_tamper = AsyncMock()

        dispatcher = EventDispatcher(
            event_queue=event_queue,
            machine_status=machine_status,
            ws_manager=ws_manager,
            serial_manager=mock_serial,
            transaction_orchestrator=mock_tx_orch,
        )

        event_data = {
            "event": "TAMPER",
            "sensor": "SHOCK_A",
            "_controller": "COIN_SECURITY",
        }
        await dispatcher._handle_event(event_data)

        mock_tx_orch.handle_tamper.assert_awaited_once_with("SHOCK_A")


class TestAdminTamperRecovery:
    @pytest.mark.asyncio
    async def test_tamper_recovery_blocks_if_unresolved_operations(self):
        from app.api.admin import tamper_recovery
        from fastapi import HTTPException

        request = MagicMock()
        request.app.state.admin_sessions.validate.return_value = MagicMock(session_id="admin1")
        session_factory = MagicMock()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_op = MagicMock(state="AMBIGUOUS")
        mock_result.scalars.return_value.all.return_value = [mock_op]
        mock_session.execute = AsyncMock(return_value=mock_result)
        session_factory.return_value.__aenter__.return_value = mock_session
        request.app.state.db_session_factory = session_factory

        with pytest.raises(HTTPException) as exc_info:
            await tamper_recovery(request, authorization="Bearer valid_token")
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_tamper_recovery_rearms_and_homes_when_clean(self):
        from app.api.admin import tamper_recovery

        request = MagicMock()
        request.app.state.admin_sessions.validate.return_value = MagicMock(session_id="admin1")
        session_factory = MagicMock()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        session_factory.return_value.__aenter__.return_value = mock_session
        request.app.state.db_session_factory = session_factory

        mock_machine_status = MagicMock()
        request.app.state.machine_status = mock_machine_status

        mock_coin = AsyncMock()
        mock_bill = AsyncMock()
        request.app.state.coin_controller = mock_coin
        request.app.state.bill_controller = mock_bill

        resp = await tamper_recovery(request, authorization="Bearer valid_token")
        assert resp["status"] == "success"

        # Tamper cleared
        mock_machine_status.update_security.assert_called_once_with(tamper_active=False)

        # Coin security rearmed
        mock_coin.security_lock.assert_awaited_once()

        # Bill sorter re-homed
        mock_bill.home.assert_awaited_once()
