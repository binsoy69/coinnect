from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Serial ports
    serial_port_bill: str = "/dev/coinnect_bill"
    serial_port_coin: str = "/dev/coinnect_coin"
    baud_rate: int = 115200
    serial_timeout: int = 5

    # Mock serial
    use_mock_serial: bool = False
    mock_delay: float = 1.0

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    environment: str = "development"
    enable_docs: bool = True

    # Logging
    log_level: str = "INFO"

    # Hardware timeouts (seconds)
    bill_acceptance_timeout: int = 10
    sorting_move_timeout: int = 8
    dispense_timeout: int = 5
    coin_dispense_timeout: int = 3

    # Consumables thresholds
    low_bill_threshold: int = 10
    low_coin_threshold: int = 50

    # Session
    session_timeout: int = 180

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
