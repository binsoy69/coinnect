"""Regression coverage for hardware-confirmed sorter readiness."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.api.admin import trigger_home_sorter
from app.core.errors import EWalletTransactionError, HardwareError
from app.drivers.bill_controller import BillController
from app.services.event_dispatcher import EventDispatcher
from app.services.ewallet_orchestrator import EWalletOrchestrator
from app.services.machine_status import MachineStatus


@pytest.fixture
def hardware():
    settings = Settings(use_mock_hardware=False)
    status = MachineStatus(settings)
    serial = AsyncMock()
    serial._settings = settings
    serial.send_bill_command.return_value = {"status": "OK", "position": 0}
    return BillController(serial, status), serial, status, settings


async def test_home_clears_cashout_readiness_rejection(hardware):
    controller, _, status, settings = hardware
    status.update_connectivity(internet_connected=True)
    status.update_bill_device(connection="connected")
    status.update_coin_device(connection="connected")
    status.update_startup_checks(performed=True, errors={})
    status.set_inventory_consistent(True)
    orchestrator = EWalletOrchestrator(
        settings, MagicMock(), MagicMock(), MagicMock(), status,
        AsyncMock(), MagicMock(),
    )
    with pytest.raises(EWalletTransactionError, match="Bill sorter is not homed"):
        orchestrator._check_ready("cash-out")
    await controller.home()
    sorter = status.snapshot().sorter
    assert sorter.homed is True
    assert sorter.current_position == 0
    assert sorter.current_slot == 0
    orchestrator._check_ready("cash-out")


async def test_maintenance_home_updates_shared_status(hardware):
    controller, _, status, _ = hardware
    request = MagicMock()
    request.app.state.bill_acceptor._bill = controller
    response = await trigger_home_sorter(request, authorization="Bearer valid-token")
    assert response["status"] == "success"
    assert status.snapshot().sorter.homed is True


@pytest.mark.parametrize("failure", ["error", "timeout", "cancel", "invalid"])
async def test_unsuccessful_home_leaves_sorter_unhomed(hardware, failure):
    controller, serial, status, _ = hardware
    status.update_sorter(homed=True)

    async def fail(*args, **kwargs):
        assert status.snapshot().sorter.homed is False
        if failure == "error":
            return {"status": "ERROR", "code": "TIMEOUT"}
        if failure == "invalid":
            return {"status": "READY"}
        if failure == "cancel":
            raise asyncio.CancelledError()
        raise TimeoutError()

    serial.send_bill_command.side_effect = fail
    expected = {"error": HardwareError, "timeout": TimeoutError,
                "cancel": asyncio.CancelledError, "invalid": ValueError}[failure]
    with pytest.raises(expected):
        await controller.home()
    assert status.snapshot().sorter.homed is False


@pytest.mark.parametrize("homed", [True, False])
async def test_status_query_synchronizes_snapshot(hardware, homed):
    controller, serial, status, _ = hardware
    status.update_sorter(homed=not homed)
    serial.send_bill_command.return_value = {
        "status": "OK", "homed": homed, "position": 14600, "slot": 3,
    }
    await controller.sort_status()
    sorter = status.snapshot().sorter
    assert sorter.homed is homed
    assert sorter.current_position == 14600
    assert sorter.current_slot == 3


@pytest.mark.parametrize("operation", ["home", "sort_status"])
@pytest.mark.parametrize("invalidation", ["reset", "emergency_stop", "disconnect", "ready", "tamper"])
async def test_late_confirmation_cannot_restore_invalidated_homing(
    hardware, operation, invalidation,
):
    controller, serial, status, _ = hardware
    status.update_sorter(homed=True)
    started = asyncio.Event()
    release = asyncio.Event()

    async def respond(command, **kwargs):
        if command["cmd"] in {"HOME", "SORT_STATUS"}:
            started.set()
            await release.wait()
            return {"status": "OK", "position": 0, "slot": 0, "homed": True}
        assert status.snapshot().sorter.homed is False
        raise TimeoutError("Stop/reset acknowledgement lost")

    serial.send_bill_command.side_effect = respond
    task = asyncio.create_task(getattr(controller, operation)())
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        if invalidation in {"reset", "emergency_stop"}:
            with pytest.raises(TimeoutError):
                await getattr(controller, invalidation)()
        elif invalidation == "disconnect":
            status.update_bill_device(connection="disconnected")
        else:
            dispatcher = EventDispatcher(
                asyncio.Queue(), status, AsyncMock(), serial_manager=serial,
            )
            if invalidation == "ready":
                await dispatcher._handle_event({
                    "event": "READY", "controller": "BILL", "version": "2.0.0",
                })
            else:
                await dispatcher._handle_event({"event": "TAMPER", "sensor": "SHOCK_A"})
                serial.emergency_stop_all.assert_awaited_once()
        assert status.snapshot().sorter.homed is False
        release.set()
        await task
        assert status.snapshot().sorter.homed is False
    finally:
        release.set()
        await task

    serial.send_bill_command.side_effect = None
    serial.send_bill_command.return_value = {"status": "OK", "position": 0}
    await controller.home()
    assert status.snapshot().sorter.homed is True
