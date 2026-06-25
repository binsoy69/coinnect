from datetime import datetime, timedelta

import pytest

from app.services.admin_session import AdminAuthError, AdminSessionService
from app.services.operation_mode import OperationModeError, OperationModeManager


class Clock:
    def __init__(self):
        self.now = datetime(2026, 1, 1, 12, 0, 0)

    def __call__(self):
        return self.now


def test_successful_login_enters_maintenance_and_logout_releases_it(
    test_settings,
):
    test_settings.admin_pin = "2468"
    clock = Clock()
    mode = OperationModeManager()
    service = AdminSessionService(test_settings, mode, clock=clock)

    session = service.login("2468")

    assert mode.is_maintenance
    assert service.validate(session.token).session_id == session.session_id
    service.logout(session.token)
    assert not mode.is_maintenance


def test_login_is_rejected_while_transaction_is_active(test_settings):
    test_settings.admin_pin = "2468"
    mode = OperationModeManager()
    mode.begin_transaction("money-changer")
    service = AdminSessionService(test_settings, mode)

    with pytest.raises(OperationModeError, match="transaction"):
        service.login("2468")


def test_five_bad_pins_lock_login_for_five_minutes(test_settings):
    test_settings.admin_pin = "2468"
    clock = Clock()
    service = AdminSessionService(
        test_settings, OperationModeManager(), clock=clock
    )

    for _ in range(5):
        with pytest.raises(AdminAuthError, match="Invalid"):
            service.login("0000")

    with pytest.raises(AdminAuthError, match="locked"):
        service.login("2468")

    clock.now += timedelta(minutes=5, seconds=1)
    assert service.login("2468").token


def test_session_expires_after_inactivity(test_settings):
    test_settings.admin_pin = "2468"
    clock = Clock()
    mode = OperationModeManager()
    service = AdminSessionService(test_settings, mode, clock=clock)
    session = service.login("2468")

    clock.now += timedelta(minutes=16)

    with pytest.raises(AdminAuthError, match="expired"):
        service.validate(session.token)
    assert not mode.is_maintenance


def test_maintenance_blocks_customer_transactions():
    mode = OperationModeManager()
    mode.begin_maintenance("admin-1")

    with pytest.raises(OperationModeError, match="maintenance"):
        mode.begin_transaction("forex")
