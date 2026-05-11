"""PIN-based in-memory authentication for the health check app."""

import os
import secrets


class AuthManager:
    """Small token store scoped to one diagnostics backend process."""

    def __init__(self) -> None:
        pin = os.environ.get("HEALTHCHECK_PIN", "")
        if not pin:
            raise RuntimeError("HEALTHCHECK_PIN is required")
        self._pin = pin
        self._tokens: set[str] = set()

    def login(self, pin: str) -> str | None:
        if not secrets.compare_digest(pin, self._pin):
            return None
        token = secrets.token_urlsafe(32)
        self._tokens.add(token)
        return token

    def verify(self, token: str) -> bool:
        return token in self._tokens
