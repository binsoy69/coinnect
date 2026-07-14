import pytest

from app.core.config import Settings


class TestSettings:
    def test_defaults(self):
        s = Settings(
            use_mock_serial=True,
            serial_port_bill="MOCK",
            serial_port_coin="MOCK",
        )
        assert s.baud_rate == 115200
        assert s.port == 8000
        assert s.host == "0.0.0.0"
        assert s.serial_timeout == 5
        assert s.low_bill_threshold == 10
        assert s.low_coin_threshold == 50
        assert s.session_timeout == 180

    def test_mock_serial_flag(self):
        s = Settings(
            use_mock_serial=True,
            serial_port_bill="MOCK",
            serial_port_coin="MOCK",
        )
        assert s.use_mock_serial is True

    def test_cors_origins_parsing(self):
        s = Settings(
            use_mock_serial=True,
            serial_port_bill="MOCK",
            serial_port_coin="MOCK",
            cors_origins="http://a.com,http://b.com",
        )
        origins = s.cors_origins.split(",")
        assert len(origins) == 2
        assert "http://a.com" in origins

    def test_hardware_timeouts(self):
        s = Settings(
            use_mock_serial=True,
            serial_port_bill="MOCK",
            serial_port_coin="MOCK",
        )
        assert s.bill_acceptance_timeout == 10
        assert s.sorting_move_timeout == 8
        assert s.dispense_timeout == 5
        assert s.coin_dispense_timeout == 3

    def test_legacy_env_names_are_supported(self):
        s = Settings(
            use_mock_serial=True,
            serial_port_bill="MOCK",
            serial_port_coin="MOCK",
            camera_index=2,
            yolo_model_path="models/legacy-auth.pt",
            ml_confidence_threshold=0.85,
        )

        assert s.camera_device == 2
        assert s.yolo_auth_model_path == "models/legacy-auth.pt"
        assert s.yolo_confidence_threshold == 0.85

    def test_unknown_env_names_are_ignored(self):
        s = Settings(
            use_mock_serial=True,
            serial_port_bill="MOCK",
            serial_port_coin="MOCK",
            unused_legacy_setting="ignored",
        )

        assert s.serial_port_bill == "MOCK"

    def test_paperang_density_empty_string(self):
        s = Settings(
            use_mock_serial=True,
            serial_port_bill="MOCK",
            serial_port_coin="MOCK",
            paperang_density="",
        )
        assert s.paperang_density is None

