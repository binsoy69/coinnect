import asyncio
import importlib.util
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw, ImageFont

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Constants
PAPERANG_WIDTH = 384
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class PaperangPrintInterfaceError(RuntimeError):
    """Raised when printer operations fail."""
    pass


class ReceiptService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._width = PAPERANG_WIDTH
        self._paperang_module = None

    def _resolve_paperang_repo_path(self) -> Path:
        configured_path = Path(self._settings.paperang_repo_path)
        if configured_path.is_absolute():
            return configured_path
        return PROJECT_ROOT / configured_path

    def _load_vendor_hardware(self, hardware_module: Path, repo_path: Path) -> Any:
        if self._paperang_module is not None:
            return self._paperang_module

        if str(repo_path) not in sys.path:
            sys.path.insert(0, str(repo_path))
        spec = importlib.util.spec_from_file_location(
            "coinnect_vendor_paperang_hardware",
            hardware_module,
        )
        if spec is None or spec.loader is None:
            raise PaperangPrintInterfaceError(
                f"Unable to load Paperang module: {hardware_module}"
            )
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise PaperangPrintInterfaceError(
                f"Unable to import Paperang module: {exc}"
            ) from exc
        if not hasattr(module, "Paperang"):
            raise PaperangPrintInterfaceError("Paperang module does not expose Paperang class")
        
        self._paperang_module = module
        return module

    def _pack_monochrome_image_bits(self, image: Image.Image) -> bytes:
        monochrome = image.convert("1")
        width, height = monochrome.size
        if width != self._width:
            raise ValueError(f"Paperang image width must be {self._width}px")
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

    def _render_text_lines(self, lines: list[str]) -> Image.Image:
        font = ImageFont.load_default()
        line_height = 20
        padding = 20
        height = len(lines) * line_height + padding * 2
        
        image = Image.new("1", (self._width, height), 1)
        draw = ImageDraw.Draw(image)
        
        y = padding
        for line in lines:
            if line == "------------------------":
                # Draw a nice clean horizontal line
                draw.line((15, y + 8, self._width - 15, y + 8), fill=0)
            elif line.startswith("[CENTER]"):
                text = line.removeprefix("[CENTER]")
                bbox = draw.textbbox((0, 0), text, font=font)
                w = bbox[2] - bbox[0]
                draw.text(((self._width - w) // 2, y), text, font=font, fill=0)
            elif " : " in line:
                # Left/Right aligned text
                parts = line.split(" : ", 1)
                key, val = parts[0], parts[1]
                draw.text((15, y), key, font=font, fill=0)
                bbox_val = draw.textbbox((0, 0), val, font=font)
                w_val = bbox_val[2] - bbox_val[0]
                draw.text((self._width - 15 - w_val, y), val, font=font, fill=0)
            else:
                draw.text((15, y), line, font=font, fill=0)
            y += line_height
            
        return image

    def _get_field(self, record: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(record, dict):
            return record.get(field_name, default)
        return getattr(record, field_name, default)

    def _format_datetime(self, dt: Any) -> str:
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(dt, str):
            try:
                # Try parsing ISO format
                parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                return parsed.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return dt
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _mask_mobile_number(self, num: str | None) -> str:
        if not num:
            return "N/A"
        if len(num) >= 7:
            return num[:4] + "****" + num[-3:]
        return num

    def _print_blocking(self, image: Image.Image) -> None:
        """Executed inside asyncio.to_thread to keep print requests non-blocking."""
        payload = self._pack_monochrome_image_bits(image)
        repo_path = self._resolve_paperang_repo_path()
        hardware_module = repo_path / "hardware.py"
        
        if not hardware_module.exists():
            raise PaperangPrintInterfaceError(
                f"Paperang support module not found: {hardware_module}"
            )

        module = self._load_vendor_hardware(hardware_module, repo_path)
        printer = None
        import socket
        old_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(10.0)
            mac_address = self._settings.paperang_mac_address or None
            logger.info(f"Connecting to Paperang P1 via Bluetooth (MAC={mac_address})...")
            printer = module.Paperang(mac_address)
            
            if not getattr(printer, "connected", False):
                raise PaperangPrintInterfaceError("Paperang P1 Bluetooth connection failed")
        except Exception as exc:
            if isinstance(exc, PaperangPrintInterfaceError):
                raise
            raise PaperangPrintInterfaceError(f"Bluetooth connection failed: {exc}") from exc
        finally:
            socket.setdefaulttimeout(old_timeout)

        try:
            if self._settings.paperang_density is not None:
                printer.sendDensityToBt(int(self._settings.paperang_density))
            
            logger.info("Sending receipt payload to Bluetooth printer...")
            printer.sendImageToBt(payload)
            
            if self._settings.paperang_feed_lines > 0:
                printer.sendFeedLineToBt(int(self._settings.paperang_feed_lines))
                
            logger.info("Print job completed successfully")
        finally:
            if printer is not None:
                try:
                    printer.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting printer: {e}")

    async def _queue_print_job(self, image: Image.Image) -> None:
        """Trigger printing in a threadpool so it does not block the async event loop."""
        if not self._settings.paperang_enabled:
            logger.info("Paperang printing is disabled in configuration. Skipping print.")
            return

        if self._settings.use_mock_hardware:
            logger.info("[MOCK PRINTER] Printing receipt. Height: %dpx", image.height)
            return

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._print_blocking, image),
                timeout=self._settings.paperang_print_timeout_seconds,
            )
        except Exception as exc:
            logger.error(f"Paperang printing failed: {exc}. Continuing transaction without interruption.")

    async def print_receipt(self, record: Any) -> None:
        """Prints a successful transaction receipt."""
        try:
            tx_id = self._get_field(record, "id") or self._get_field(record, "transaction_id") or "UNKNOWN"
            tx_type = self._get_field(record, "type", "transaction")
            created_at = self._get_field(record, "created_at") or self._get_field(record, "completed_at")
            date_str = self._format_datetime(created_at)
            
            inserted = self._get_field(record, "inserted_amount", 0)
            dispensed = self._get_field(record, "dispensed_amount", 0)
            fee = self._get_field(record, "fee", 0)
            
            lines = [
                "[CENTER]COINNECT",
                "[CENTER]TRANSACTION RECEIPT",
                "------------------------",
                f"Transaction : {tx_id}",
                f"Date : {date_str}",
                f"Type : {tx_type}",
            ]
            
            # Provider / E-Wallet info if e-wallet
            provider = self._get_field(record, "provider")
            if provider:
                mobile = self._get_field(record, "mobile_number")
                lines.append(f"Provider : {provider.upper()}")
                lines.append(f"Account : {self._mask_mobile_number(mobile)}")
            
            # Forex-specific fields
            from_curr = self._get_field(record, "from_currency")
            to_curr = self._get_field(record, "to_currency")
            if from_curr and to_curr:
                rate = self._get_field(record, "exchange_rate", 1.0)
                converted = self._get_field(record, "converted_amount", 0)
                lines.append(f"Conversion : {from_curr} -> {to_curr}")
                lines.append(f"Rate : {rate:.4f}")
                lines.append(f"Converted : {to_curr} {converted}")

            inserted_currency = from_curr if from_curr else "PHP"
            dispensed_currency = to_curr if to_curr else "PHP"
            fee_currency = to_curr if to_curr else "PHP"

            lines.extend([
                "------------------------",
                f"Inserted : {inserted_currency} {inserted}",
                f"Dispensed : {dispensed_currency} {dispensed}",
                f"Fee : {fee_currency} {fee}",
                "------------------------",
                "[CENTER]Thank you for using Coinnect!",
                "[CENTER]Self-Service Financial Kiosk",
            ])
            
            image = self._render_text_lines(lines)
            await self._queue_print_job(image)
        except Exception as e:
            logger.error(f"Error preparing receipt: {e}")

    async def print_claim_ticket(
        self, record: Any, claim_code: str | None = None, shortfall: int | None = None, error_reason: str | None = None
    ) -> None:
        """Prints a claim ticket for partial dispense or failed online transfers."""
        try:
            tx_id = self._get_field(record, "id") or self._get_field(record, "transaction_id") or "UNKNOWN"
            created_at = self._get_field(record, "created_at") or self._get_field(record, "updated_at")
            date_str = self._format_datetime(created_at)
            
            # Extract shortfall from record or parameter
            if shortfall is None:
                inserted = self._get_field(record, "inserted_amount", 0)
                dispensed = self._get_field(record, "dispensed_amount", 0)
                shortfall = max(0, inserted - dispensed)
                
            ticket_code = claim_code or self._get_field(record, "claim_ticket_code", "N/A")
            reason = error_reason or self._get_field(record, "error_message") or self._get_field(record, "error_code") or "PARTIAL_DISPENSE"
            
            to_curr = self._get_field(record, "to_currency")
            shortfall_currency = to_curr if to_curr else "PHP"

            lines = [
                "[CENTER]COINNECT",
                "[CENTER]*** CLAIM TICKET ***",
                "------------------------",
                f"Transaction : {tx_id}",
                f"Date : {date_str}",
                "Status : PARTIAL DISPENSE",
                f"Shortfall : {shortfall_currency} {shortfall}",
                f"Reason : {reason}",
                "------------------------",
                f"[CENTER]TICKET CODE: {ticket_code}",
                "------------------------",
                "[CENTER]Please present this code to",
                "[CENTER]the merchant or customer service",
                "[CENTER]to claim your refund.",
                "------------------------",
                "[CENTER]Keep this ticket safe!",
            ]
            
            image = self._render_text_lines(lines)
            await self._queue_print_job(image)
        except Exception as e:
            logger.error(f"Error preparing claim ticket: {e}")
