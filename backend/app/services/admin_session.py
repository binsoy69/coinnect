"""In-memory PIN authentication for local maintenance sessions."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
import secrets
import threading
from typing import Callable

from app.core.config import Settings
from app.services.operation_mode import OperationModeManager


class AdminAuthError(RuntimeError):
    pass


@dataclass
class AdminSession:
    token: str
    session_id: str
    expires_at: datetime


class AdminSessionService:
    def __init__(
        self,
        settings: Settings,
        operation_mode: OperationModeManager,
        clock: Callable[[], datetime] = datetime.utcnow,
    ):
        self._settings = settings
        self._mode = operation_mode
        self._clock = clock
        self._lock = threading.RLock()
        self._sessions: dict[str, AdminSession] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._failed_attempts = 0
        self._locked_until: datetime | None = None

    def login(self, pin: str) -> AdminSession:
        now = self._clock()
        if self._locked_until and now < self._locked_until:
            raise AdminAuthError("Admin login is temporarily locked")
        configured_pin = self._settings.admin_pin
        if not re.fullmatch(r"\d{4,8}", configured_pin):
            raise AdminAuthError("Admin PIN is not configured")
        if not secrets.compare_digest(pin, configured_pin):
            self._failed_attempts += 1
            if self._failed_attempts >= self._settings.admin_max_attempts:
                self._locked_until = now + timedelta(
                    minutes=self._settings.admin_lockout_minutes
                )
            raise AdminAuthError("Invalid admin PIN")

        self._failed_attempts = 0
        self._locked_until = None
        session_id = secrets.token_hex(12)
        self._mode.begin_maintenance(session_id)
        session = AdminSession(
            token=secrets.token_urlsafe(32),
            session_id=session_id,
            expires_at=now
            + timedelta(minutes=self._settings.admin_session_minutes),
        )
        with self._lock:
            self._sessions[session.token] = session
            self._schedule_expiry(session)
        return session

    def validate(self, token: str) -> AdminSession:
        with self._lock:
            session = self._sessions.get(token)
            if session is None:
                raise AdminAuthError("Invalid admin session")
            now = self._clock()
            if now >= session.expires_at:
                self._expire(token)
                raise AdminAuthError("Admin session expired")
            session.expires_at = now + timedelta(
                minutes=self._settings.admin_session_minutes
            )
            self._schedule_expiry(session)
            return session

    def logout(self, token: str) -> None:
        self._expire(token)

    def _schedule_expiry(self, session: AdminSession) -> None:
        with self._lock:
            existing = self._timers.pop(session.token, None)
            if existing:
                existing.cancel()
            delay = max(
                0.0, (session.expires_at - self._clock()).total_seconds()
            )
            timer = threading.Timer(delay, self._expire, args=(session.token,))
            timer.daemon = True
            self._timers[session.token] = timer
            timer.start()

    def _expire(self, token: str) -> None:
        with self._lock:
            timer = self._timers.pop(token, None)
            if timer and timer is not threading.current_thread():
                timer.cancel()
            session = self._sessions.pop(token, None)
            if session:
                self._mode.end_maintenance(session.session_id)
