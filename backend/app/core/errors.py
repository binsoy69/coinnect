from typing import Optional


class CoinnectError(Exception):
    """Base exception for Coinnect backend."""


class SerialError(CoinnectError):
    """Communication error with serial port."""

    def __init__(self, message: str, port: Optional[str] = None):
        self.port = port
        super().__init__(message)


class HardwareError(CoinnectError):
    """Error response received from Arduino hardware."""

    def __init__(self, code: str, message: Optional[str] = None, dispensed: Optional[int] = None):
        self.code = code
        self.dispensed = dispensed
        super().__init__(message or f"Hardware error: {code}")


class TimeoutError(CoinnectError):
    """Operation timed out waiting for hardware response."""

    def __init__(self, command: str, timeout: float):
        self.command = command
        self.timeout = timeout
        super().__init__(f"Timeout after {timeout}s waiting for response to {command}")


class InvalidTransitionError(CoinnectError):
    """Invalid state transition attempted."""

    def __init__(self, current_state: str, target_state: str):
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(
            f"Invalid transition from {current_state} to {target_state}"
        )


class TransactionError(CoinnectError):
    """Error during transaction processing."""

    def __init__(self, transaction_id: str, message: str):
        self.transaction_id = transaction_id
        super().__init__(f"Transaction {transaction_id}: {message}")


class InsufficientInventoryError(CoinnectError):
    """Not enough bills/coins in inventory to fulfill dispense."""

    def __init__(self, requested: int, available: int, shortfall: int):
        self.requested = requested
        self.available = available
        self.shortfall = shortfall
        super().__init__(
            f"Insufficient inventory: need {requested}, have {available}, short {shortfall}"
        )


class StorageFullError(CoinnectError):
    """Storage slot is full for the given denomination."""

    def __init__(self, denom: str):
        self.denom = denom
        super().__init__(f"Storage full for denomination {denom}")
