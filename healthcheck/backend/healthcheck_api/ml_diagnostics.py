"""ML diagnostics for bill authentication and denomination models."""

from pathlib import Path
from typing import Iterable

from app.core.config import Settings
from app.core.constants import CURRENCY_BILL_DENOMS, Currency

AUTH_LABELS = {"genuine", "fake"}


class BillModelDiagnosticError(RuntimeError):
    """Raised when a configured bill ML model fails diagnostics."""


def validate_bill_model_pair(settings: Settings, currency: str) -> dict:
    selected_currency = Currency(currency.upper())
    auth_path, denom_path = _model_paths(settings, selected_currency)
    expected_denoms = [
        denom.value for denom in CURRENCY_BILL_DENOMS[selected_currency]
    ]

    auth_model = _load_model(auth_path, "auth", selected_currency.value)
    denom_model = _load_model(denom_path, "denomination", selected_currency.value)
    auth_labels = _labels_from_model(auth_model)
    denom_labels = _labels_from_model(denom_model)

    _require_labels(
        label_set={label.lower() for label in auth_labels},
        expected=AUTH_LABELS,
        model_type="auth",
        currency=selected_currency.value,
        path=auth_path,
    )
    _require_labels(
        label_set=set(denom_labels),
        expected=set(expected_denoms),
        model_type="denomination",
        currency=selected_currency.value,
        path=denom_path,
        forbid_unexpected=True,
    )

    return {
        "currency": selected_currency.value,
        "auth_model": {
            "configured_path": auth_path,
            "resolved_path": str(_resolve_path(auth_path)),
            "loaded": True,
            "labels": auth_labels,
            "expected_labels": sorted(AUTH_LABELS),
        },
        "denomination_model": {
            "configured_path": denom_path,
            "resolved_path": str(_resolve_path(denom_path)),
            "loaded": True,
            "labels": denom_labels,
            "expected_labels": expected_denoms,
        },
    }


def _model_paths(settings: Settings, currency: Currency) -> tuple[str, str]:
    if currency == Currency.PHP:
        return settings.yolo_auth_model_path, settings.yolo_denom_model_path
    if currency == Currency.USD:
        return settings.yolo_auth_model_path_usd, settings.yolo_denom_model_path_usd
    if currency == Currency.EUR:
        return settings.yolo_auth_model_path_eur, settings.yolo_denom_model_path_eur
    raise BillModelDiagnosticError(f"Unsupported currency: {currency.value}")


def _load_model(path: str, model_type: str, currency: str):
    resolved = _resolve_path(path)
    if not resolved.exists():
        raise BillModelDiagnosticError(
            f"{currency} {model_type} model does not exist: "
            f"configured={path}, resolved={resolved}"
        )
    try:
        from ultralytics import YOLO

        return YOLO(str(resolved))
    except Exception as exc:
        raise BillModelDiagnosticError(
            f"{currency} {model_type} model failed to load: "
            f"configured={path}, resolved={resolved}, error={exc}"
        ) from exc


def _resolve_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (Path.cwd() / candidate).resolve()


def _labels_from_model(model) -> list[str]:
    names = getattr(model, "names", {})
    if isinstance(names, dict):
        return [str(names[key]) for key in sorted(names)]
    if isinstance(names, (list, tuple)):
        return [str(label) for label in names]
    raise BillModelDiagnosticError("YOLO model names must be a dict or list")


def _require_labels(
    *,
    label_set: set[str],
    expected: Iterable[str],
    model_type: str,
    currency: str,
    path: str,
    forbid_unexpected: bool = False,
) -> None:
    expected_set = set(expected)
    missing = sorted(expected_set - label_set)
    unexpected = sorted(label_set - expected_set) if forbid_unexpected else []
    if missing or unexpected:
        parts = []
        if missing:
            parts.append(f"missing labels: {', '.join(missing)}")
        if unexpected:
            parts.append(f"unexpected labels: {', '.join(unexpected)}")
        raise BillModelDiagnosticError(
            f"{currency} {model_type} model label mismatch for {path}: "
            + "; ".join(parts)
        )
