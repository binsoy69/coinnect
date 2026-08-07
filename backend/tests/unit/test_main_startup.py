from types import SimpleNamespace
from unittest.mock import AsyncMock
import logging

import pytest

from app.core.errors import SerialError
from app.core.config import Settings
from app.main import _recover_physical_operations_for_startup
from app.services.machine_status import MachineStatus


@pytest.mark.asyncio
async def test_failed_physical_recovery_is_warning_in_record_only_mode(caplog):
    machine_status = MachineStatus(Settings())
    machine_status.set_inventory_consistent(False)
    app = SimpleNamespace(state=SimpleNamespace(machine_status=machine_status))
    orchestrator = AsyncMock()
    orchestrator.recover_started_operations.side_effect = SerialError(
        "controller acknowledgement timed out"
    )
    claim_service = object()

    await _recover_physical_operations_for_startup(
        app, orchestrator, claim_service
    )

    assert app.state.startup_recovery_error == (
        "controller acknowledgement timed out"
    )
    assert "dispensing remains enabled by reconciliation policy" in caplog.text
    assert any(record.levelno == logging.WARNING for record in caplog.records)
    orchestrator.recover_started_operations.assert_awaited_once_with(claim_service)


@pytest.mark.asyncio
async def test_failed_physical_recovery_is_critical_in_strict_mode(caplog):
    machine_status = MachineStatus(
        Settings(block_dispensing_on_inventory_inconsistency=True)
    )
    machine_status.set_inventory_consistent(False)
    app = SimpleNamespace(state=SimpleNamespace(machine_status=machine_status))
    orchestrator = AsyncMock()
    orchestrator.recover_started_operations.side_effect = SerialError(
        "controller acknowledgement timed out"
    )

    await _recover_physical_operations_for_startup(app, orchestrator, object())

    assert "dispensing remains disabled pending operator reconciliation" in caplog.text
    assert any(record.levelno == logging.CRITICAL for record in caplog.records)


@pytest.mark.asyncio
async def test_successful_physical_recovery_clears_startup_error():
    app = SimpleNamespace(
        state=SimpleNamespace(
            startup_recovery_error="old error",
            machine_status=MachineStatus(Settings()),
        )
    )
    orchestrator = AsyncMock()

    await _recover_physical_operations_for_startup(app, orchestrator, object())

    assert app.state.startup_recovery_error is None
