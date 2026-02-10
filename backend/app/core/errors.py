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
