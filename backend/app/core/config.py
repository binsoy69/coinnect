from functools import lru_cache

from pydantic import AliasChoices, BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class EWalletFeeTier(BaseModel):
    min: int = Field(ge=1)
    max: int | None = Field(default=None, ge=1)
    fee: int = Field(ge=0)



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
    serial_homing_timeout: float = 45.0
    serial_sorting_timeout: float = 20.0
    coin_dispense_timeout_factor: float = 0.8
    coin_dispense_timeout_base: float = 5.0

    # Consumables thresholds
    low_bill_threshold: int = 10
    low_coin_threshold: int = 50

    # Session
    session_timeout: int = 180

    # Maintenance admin access
    admin_session_minutes: int = 15
    admin_lockout_minutes: int = 5
    admin_max_attempts: int = 5

    # Mock hardware (GPIO, camera, ML)
    use_mock_hardware: bool = False

    # Paperang P1 receipt printer
    paperang_enabled: bool = False
    paperang_mac_address: str = ""
    paperang_repo_path: str = "vendor/python-paperang"
    paperang_density: int | None = None

    @field_validator("paperang_density", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v
    paperang_feed_lines: int = 120
    paperang_print_timeout_seconds: int = 60

    # RFID card configuration
    admin_rfid_uids: str = ""

    # Camera
    camera_device: int = Field(
        default=0,
        validation_alias=AliasChoices("camera_device", "camera_index"),
    )

    # YOLO ML models
    yolo_auth_model_path: str = Field(
        default="models/auth.pt",
        validation_alias=AliasChoices("yolo_auth_model_path", "yolo_model_path"),
    )
    yolo_denom_model_path: str = "models/denom.pt"
    yolo_confidence_threshold: float = Field(
        default=0.7,
        validation_alias=AliasChoices(
            "yolo_confidence_threshold",
            "ml_confidence_threshold",
        ),
    )

    # Bill acceptor motor speeds (PWM duty cycle %)
    bill_pull_speed: int = 60
    bill_eject_speed: int = 80
    bill_store_speed: int = 70

    # White LED brightness (PWM duty cycle %)
    white_led_brightness: int = 100

    # Bill acceptor timing (seconds)
    led_stabilization_delay: float = 0.2
    bill_pull_duration: float = 1.5
    bill_store_duration: float = 2.0
    bill_eject_duration: float = 1.5
    bill_positioning_timeout: float = 3.0
    bill_at_position_delay: float = 0.05
    bill_position_poll_interval: float = 0.005
    bill_brake_duration: float = 0.15


    # Storage slot capacity
    storage_slot_capacity: int = 100

    # Stepper slot positions
    slot_1_position: int = 0
    slot_2_position: int = 30000
    slot_3_position: int = 60000
    slot_4_position: int = 90000
    slot_5_position: int = 122500
    slot_6_position: int = 153500
    slot_7_position: int = 187500
    slot_8_position: int = 219500

    # Database
    db_url: str = "sqlite+aiosqlite:///./coinnect.db"

    # Forex
    forex_api_key: str = ""
    forex_api_url: str = "https://api.frankfurter.dev/v1/latest"
    forex_cache_ttl_seconds: int = 86400  # 24 hours
    forex_rate_refresh_interval: int = 3600  # Auto-refresh every 1 hour

    # Forex fees (percentage per currency pair)
    forex_fee_usd_to_php: float = 5.0
    forex_fee_php_to_usd: float = 5.0
    forex_fee_eur_to_php: float = 5.0
    forex_fee_php_to_eur: float = 5.0

    # Forex connectivity
    forex_connectivity_check_url: str = "https://api.frankfurter.dev"
    forex_connectivity_timeout: int = 5

    # PayMongo e-wallet integration
    paymongo_api_url: str = "https://api.paymongo.com"
    paymongo_secret_key: str = ""
    paymongo_public_key: str = ""
    paymongo_webhook_secret: str = ""
    paymongo_sandbox: bool = True
    paymongo_timeout_seconds: int = 15
    paymongo_max_retries: int = 3

    paymongo_source_account_number: str = ""
    paymongo_source_account_name: str = "Coinnect"
    paymongo_source_account_bic: str = "PAEYPHM2XXX"
    paymongo_webhook_tolerance_seconds: int = 300
    ewallet_fee_tiers: list[EWalletFeeTier] = Field(
        default_factory=lambda: [
            EWalletFeeTier(min=1, max=500, fee=15),
            EWalletFeeTier(min=501, max=None, fee=25),
        ]
    )

    # ML models per currency
    yolo_auth_model_path_usd: str = "models/auth_usd.pt"
    yolo_denom_model_path_usd: str = "models/denom_usd.pt"
    yolo_auth_model_path_eur: str = "models/auth_eur.pt"
    yolo_denom_model_path_eur: str = "models/denom_eur.pt"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
