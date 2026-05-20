"""Paperang P1 healthcheck support."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType

from PIL import Image, ImageDraw, ImageFont

from app.core.config import Settings

PAPERANG_WIDTH = 384
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class PaperangDiagnosticError(RuntimeError):
    """Raised when the Paperang diagnostic cannot run."""


def resolve_paperang_repo_path(settings: Settings) -> Path:
    configured_path = Path(settings.paperang_repo_path)
    if configured_path.is_absolute():
        return configured_path
    return PROJECT_ROOT / configured_path


def paperang_snapshot(settings: Settings) -> dict:
    repo_path = resolve_paperang_repo_path(settings)
    return {
        "mac_configured": bool(settings.paperang_mac_address),
        "mac_address": settings.paperang_mac_address or None,
        "repo_path": str(repo_path),
        "repo_present": repo_path.exists(),
        "hardware_module_present": (repo_path / "hardware.py").exists(),
    }


def render_sample_receipt_image(now: datetime | None = None) -> Image.Image:
    timestamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    image = Image.new("1", (PAPERANG_WIDTH, 320), 1)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    def center_text(y: int, text: str) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        draw.text(((PAPERANG_WIDTH - width) // 2, y), text, font=font, fill=0)

    center_text(16, "COINNECT")
    center_text(36, "HEALTHCHECK SAMPLE RECEIPT")
    draw.line((24, 62, PAPERANG_WIDTH - 24, 62), fill=0)

    rows = [
        ("Printer", "Paperang P1"),
        ("Mode", "Healthcheck"),
        ("Result", "Sample print"),
        ("Time", timestamp),
    ]
    y = 86
    for label, value in rows:
        draw.text((32, y), f"{label}:", font=font, fill=0)
        draw.text((144, y), value, font=font, fill=0)
        y += 24

    draw.line((24, 202, PAPERANG_WIDTH - 24, 202), fill=0)
    center_text(228, "No transaction occurred.")
    center_text(250, "Use this page only for printer checks.")
    center_text(286, "-- END TEST PRINT --")
    return image


def pack_monochrome_image_bits(image: Image.Image) -> bytes:
    monochrome = image.convert("1")
    width, height = monochrome.size
    if width != PAPERANG_WIDTH:
        raise ValueError(f"Paperang image width must be {PAPERANG_WIDTH}px")
    if width % 8 != 0:
        raise ValueError("Paperang image width must be divisible by 8")

    pixels = monochrome.load()
    packed = bytearray()
    for y in range(height):
        for x in range(0, width, 8):
            byte = 0
            for offset in range(8):
                byte <<= 1
                if pixels[x + offset, y] == 0:
                    byte |= 1
            packed.append(byte)
    return bytes(packed)


class PaperangHealthcheckPrinter:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def print_sample_receipt(self) -> dict:
        image = render_sample_receipt_image()
        payload = pack_monochrome_image_bits(image)
        if self._settings.use_mock_hardware:
            return {
                "printed": False,
                "mock": True,
                "width": image.width,
                "height": image.height,
                "payload_bytes": len(payload),
                "message": "Mock Paperang sample receipt generated.",
            }

        return await asyncio.wait_for(
            asyncio.to_thread(self._print_blocking, payload, image.height),
            timeout=self._settings.paperang_print_timeout_seconds,
        )

    def _print_blocking(self, payload: bytes, image_height: int) -> dict:
        repo_path = resolve_paperang_repo_path(self._settings)
        hardware_module = repo_path / "hardware.py"
        if not hardware_module.exists():
            raise PaperangDiagnosticError(
                f"Paperang support module not found: {hardware_module}"
            )

        module = self._load_vendor_hardware(hardware_module, repo_path)
        printer = None
        try:
            mac_address = self._settings.paperang_mac_address or None
            printer = module.Paperang(mac_address)
            if not getattr(printer, "connected", False):
                raise PaperangDiagnosticError("Paperang P1 did not connect")

            if self._settings.paperang_density is not None:
                printer.sendDensityToBt(int(self._settings.paperang_density))
            printer.sendImageToBt(payload)
            if self._settings.paperang_feed_lines > 0:
                printer.sendFeedLineToBt(int(self._settings.paperang_feed_lines))

            return {
                "printed": True,
                "mock": False,
                "mac_address": mac_address,
                "width": PAPERANG_WIDTH,
                "height": image_height,
                "payload_bytes": len(payload),
                "density": self._settings.paperang_density,
                "feed_lines": self._settings.paperang_feed_lines,
            }
        finally:
            if printer is not None:
                printer.disconnect()

    @staticmethod
    def _load_vendor_hardware(hardware_module: Path, repo_path: Path) -> ModuleType:
        if str(repo_path) not in sys.path:
            sys.path.insert(0, str(repo_path))
        spec = importlib.util.spec_from_file_location(
            "coinnect_vendor_paperang_hardware",
            hardware_module,
        )
        if spec is None or spec.loader is None:
            raise PaperangDiagnosticError(
                f"Unable to load Paperang module: {hardware_module}"
            )
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise PaperangDiagnosticError(
                f"Unable to import Paperang module: {exc}"
            ) from exc
        if not hasattr(module, "Paperang"):
            raise PaperangDiagnosticError("Paperang module does not expose Paperang")
        return module
