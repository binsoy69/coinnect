"""Mutual exclusion between customer transactions and maintenance."""

import threading


class OperationModeError(RuntimeError):
    pass


class OperationModeManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._transaction_owner: str | None = None
        self._maintenance_owner: str | None = None

    @property
    def is_maintenance(self) -> bool:
        with self._lock:
            return self._maintenance_owner is not None

    @property
    def has_active_transaction(self) -> bool:
        with self._lock:
            return self._transaction_owner is not None

    def begin_transaction(self, owner: str) -> None:
        with self._lock:
            if self._maintenance_owner is not None:
                raise OperationModeError("Machine is in maintenance mode")
            if self._transaction_owner is not None:
                raise OperationModeError("Another transaction is active")
            self._transaction_owner = owner

    def end_transaction(self, owner: str) -> None:
        with self._lock:
            if self._transaction_owner == owner:
                self._transaction_owner = None

    def begin_maintenance(self, owner: str) -> None:
        with self._lock:
            if self._transaction_owner is not None:
                raise OperationModeError(
                    "Cannot enter maintenance while a transaction is active"
                )
            if self._maintenance_owner not in {None, owner}:
                raise OperationModeError("Another admin session is active")
            self._maintenance_owner = owner

    def end_maintenance(self, owner: str) -> None:
        with self._lock:
            if self._maintenance_owner == owner:
                self._maintenance_owner = None
