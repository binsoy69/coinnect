import pytest

from app.core.config import Settings
from healthcheck_api.hardware import HardwareContext, PartialSerialManager
from healthcheck_api.paperang import (
    PAPERANG_WIDTH,
    pack_monochrome_image_bits,
    render_sample_receipt_image,
)
from healthcheck_api.runner import DiagnosticsRunner


def test_sample_receipt_bitmap_is_paperang_width():
    image = render_sample_receipt_image()
    payload = pack_monochrome_image_bits(image)

    assert image.width == PAPERANG_WIDTH
    assert len(payload) == image.height * (PAPERANG_WIDTH // 8)


def test_pack_rejects_wrong_width():
    image = render_sample_receipt_image().crop((0, 0, PAPERANG_WIDTH - 1, 10))

    with pytest.raises(ValueError, match="width"):
        pack_monochrome_image_bits(image)


async def test_paperang_missing_vendor_path_maps_to_printer_error(tmp_path):
    settings = Settings(
        use_mock_serial=True,
        use_mock_hardware=False,
        paperang_repo_path=str(tmp_path / "missing-paperang"),
        _env_file=None,
    )
    serial = PartialSerialManager(settings)
    hardware = HardwareContext(
        settings=settings,
        serial_manager=serial,
        bill_controller=object(),
        coin_controller=object(),
        machine_status=object(),
        gpio=object(),
        camera=object(),
    )
    runner = DiagnosticsRunner(hardware)

    result = await runner.run("paperang_sample_receipt")

    assert result.status == "failed"
    assert result.error_code == "PRINTER_ERROR"
    assert "Paperang support module not found" in result.error


async def test_paperang_vendor_import_failure_maps_to_printer_error(tmp_path):
    repo_path = tmp_path / "python-paperang"
    repo_path.mkdir()
    (repo_path / "hardware.py").write_text(
        "raise RuntimeError('import failed')\n",
        encoding="utf-8",
    )
    settings = Settings(
        use_mock_serial=True,
        use_mock_hardware=False,
        paperang_repo_path=str(repo_path),
        _env_file=None,
    )
    serial = PartialSerialManager(settings)
    hardware = HardwareContext(
        settings=settings,
        serial_manager=serial,
        bill_controller=object(),
        coin_controller=object(),
        machine_status=object(),
        gpio=object(),
        camera=object(),
    )
    runner = DiagnosticsRunner(hardware)

    result = await runner.run("paperang_sample_receipt")

    assert result.status == "failed"
    assert result.error_code == "PRINTER_ERROR"
    assert "Unable to import Paperang module" in result.error
