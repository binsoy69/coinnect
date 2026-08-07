from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.errors import SerialError
from app.main import _recover_physical_operations_for_startup


@pytest.mark.asyncio
async def test_failed_physical_recovery_keeps_maintenance_api_available():
    app = SimpleNamespace(state=SimpleNamespace())
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
    orchestrator.recover_started_operations.assert_awaited_once_with(claim_service)


@pytest.mark.asyncio
async def test_successful_physical_recovery_clears_startup_error():
    app = SimpleNamespace(state=SimpleNamespace(startup_recovery_error="old error"))
    orchestrator = AsyncMock()

    await _recover_physical_operations_for_startup(app, orchestrator, object())

    assert app.state.startup_recovery_error is None
