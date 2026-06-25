from pathlib import Path
import sys
import types

import pytest

from app.core.config import Settings
from healthcheck_api.ml_diagnostics import (
    BillModelDiagnosticError,
    validate_bill_model_pair,
)


class FakeYOLO:
    names_by_path = {}

    def __init__(self, path: str):
        self.names = self.names_by_path[str(path)]


def install_fake_yolo(monkeypatch):
    fake_module = types.SimpleNamespace(YOLO=FakeYOLO)
    monkeypatch.setitem(sys.modules, "ultralytics", fake_module)


def settings_for_models(tmp_path: Path) -> Settings:
    paths = {
        "php_auth": tmp_path / "auth.pt",
        "php_denom": tmp_path / "denom.pt",
        "usd_auth": tmp_path / "auth_usd.pt",
        "usd_denom": tmp_path / "denom_usd.pt",
        "eur_auth": tmp_path / "auth_eur.pt",
        "eur_denom": tmp_path / "denom_eur.pt",
    }
    for path in paths.values():
        path.write_bytes(b"model")
    return Settings(
        yolo_auth_model_path=str(paths["php_auth"]),
        yolo_denom_model_path=str(paths["php_denom"]),
        yolo_auth_model_path_usd=str(paths["usd_auth"]),
        yolo_denom_model_path_usd=str(paths["usd_denom"]),
        yolo_auth_model_path_eur=str(paths["eur_auth"]),
        yolo_denom_model_path_eur=str(paths["eur_denom"]),
        _env_file=None,
    )


def test_validate_bill_model_pair_passes_for_expected_php_labels(
    monkeypatch, tmp_path
):
    install_fake_yolo(monkeypatch)
    settings = settings_for_models(tmp_path)
    FakeYOLO.names_by_path = {
        str(tmp_path / "auth.pt"): {0: "genuine", 1: "fake"},
        str(tmp_path / "denom.pt"): {
            0: "PHP_20",
            1: "PHP_50",
            2: "PHP_100",
            3: "PHP_200",
            4: "PHP_500",
            5: "PHP_1000",
        },
    }

    result = validate_bill_model_pair(settings, "PHP")

    assert result["currency"] == "PHP"
    assert result["auth_model"]["loaded"] is True
    assert result["denomination_model"]["expected_labels"] == [
        "PHP_20",
        "PHP_50",
        "PHP_100",
        "PHP_200",
        "PHP_500",
        "PHP_1000",
    ]


def test_validate_bill_model_pair_fails_when_model_file_is_missing(tmp_path):
    settings = settings_for_models(tmp_path)
    Path(settings.yolo_auth_model_path).unlink()

    with pytest.raises(BillModelDiagnosticError, match="does not exist"):
        validate_bill_model_pair(settings, "PHP")


def test_validate_bill_model_pair_fails_for_missing_auth_label(
    monkeypatch, tmp_path
):
    install_fake_yolo(monkeypatch)
    settings = settings_for_models(tmp_path)
    FakeYOLO.names_by_path = {
        str(tmp_path / "auth.pt"): {0: "genuine"},
        str(tmp_path / "denom.pt"): {
            0: "PHP_20",
            1: "PHP_50",
            2: "PHP_100",
            3: "PHP_200",
            4: "PHP_500",
            5: "PHP_1000",
        },
    }

    with pytest.raises(BillModelDiagnosticError, match="missing labels.*fake"):
        validate_bill_model_pair(settings, "PHP")


def test_validate_bill_model_pair_fails_for_wrong_currency_denom_labels(
    monkeypatch, tmp_path
):
    install_fake_yolo(monkeypatch)
    settings = settings_for_models(tmp_path)
    FakeYOLO.names_by_path = {
        str(tmp_path / "auth_usd.pt"): {0: "genuine", 1: "fake"},
        str(tmp_path / "denom_usd.pt"): {
            0: "USD_10",
            1: "EUR_10",
        },
    }

    with pytest.raises(BillModelDiagnosticError, match="missing labels.*USD_50"):
        validate_bill_model_pair(settings, "USD")
