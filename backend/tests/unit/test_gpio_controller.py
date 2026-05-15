import builtins

import pytest

from app.drivers.gpio_controller import RPiGPIOController


def test_missing_rpi_gpio_has_actionable_error(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "RPi.GPIO":
            raise ModuleNotFoundError("No module named 'RPi'", name="RPi")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="pip install -r requirements.txt"):
        RPiGPIOController()._setup_pins()
