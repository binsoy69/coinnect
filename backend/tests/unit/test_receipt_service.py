import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from PIL import Image
from app.core.config import Settings
from app.services.receipt_service import ReceiptService, PAPERANG_WIDTH


class MockTransactionRecord:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.mark.parametrize("value", [
    datetime(2026, 9, 8, 20, 30),
    datetime(2026, 9, 8, 20, 30, tzinfo=timezone.utc),
    "2026-09-08T20:30:00",
    "2026-09-08T20:30:00Z",
    "2026-09-09T04:30:00+08:00",
    "2026-09-08T15:30:00-05:00",
])
def test_receipt_datetime_converts_to_philippine_time(value):
    service = ReceiptService(Settings(paperang_enabled=False))
    assert service._format_datetime(value) == "2026-09-09 04:30:00 UTC+08:00"


def test_receipt_datetime_fallback_uses_utc_clock():
    service = ReceiptService(Settings(paperang_enabled=False))

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is timezone.utc
            return cls(2026, 9, 8, 20, 30, tzinfo=tz)

    with patch("app.services.receipt_service.datetime", FrozenDatetime):
        assert service._format_datetime(None) == "2026-09-09 04:30:00 UTC+08:00"


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["print_receipt", "print_claim_ticket"])
async def test_printed_date_uses_philippine_time(method):
    service = ReceiptService(Settings(paperang_enabled=False))
    record = MockTransactionRecord(
        id="timezone-test", created_at=datetime(2026, 9, 8, 20, 30),
    )
    with patch.object(service, "_render_text_lines", wraps=service._render_text_lines) as render:
        await getattr(service, method)(record)
    assert "Date : 2026-09-09 04:30:00 UTC+08:00" in render.call_args.args[0]


def test_resolve_paperang_repo_path():
    settings = Settings(
        paperang_repo_path="test_vendor/paperang",
        paperang_enabled=False
    )
    service = ReceiptService(settings)
    path = service._resolve_paperang_repo_path()
    assert "test_vendor" in str(path)


def test_pack_monochrome_image_bits():
    settings = Settings(paperang_enabled=False)
    service = ReceiptService(settings)
    
    # Create a 384x16 monochrome image (all white)
    image = Image.new("1", (PAPERANG_WIDTH, 16), 1)
    payload = service._pack_monochrome_image_bits(image)
    
    # Width is 384, which is 48 bytes per row. 16 rows * 48 bytes = 768 bytes.
    # All pixels are white (value 1), so packed bits should be all 0.
    assert len(payload) == 768
    assert all(b == 0 for b in payload)


def test_render_text_lines():
    settings = Settings(paperang_enabled=False)
    service = ReceiptService(settings)
    
    lines = [
        "[CENTER]COINNECT",
        "------------------------",
        "Key : Value",
        "Left aligned text"
    ]
    image = service._render_text_lines(lines)
    assert image.width == PAPERANG_WIDTH
    # 4 lines * 20px + 40px padding = 120px
    assert image.height == 120


@pytest.mark.anyio
async def test_print_receipt_success():
    settings = Settings(
        paperang_enabled=True,
        use_mock_hardware=True
    )
    service = ReceiptService(settings)
    
    record = MockTransactionRecord(
        id="test-tx-123",
        type="bill-to-coin",
        created_at=datetime(2026, 6, 25, 12, 0, 0),
        inserted_amount=100,
        dispensed_amount=100,
        fee=0,
        provider=None,
        from_currency=None,
        to_currency=None
    )
    
    # Should run without throwing errors in mock mode
    await service.print_receipt(record)


@pytest.mark.anyio
async def test_print_claim_ticket():
    settings = Settings(
        paperang_enabled=True,
        use_mock_hardware=True
    )
    service = ReceiptService(settings)
    
    record = MockTransactionRecord(
        id="test-tx-456",
        created_at=datetime(2026, 6, 25, 12, 0, 0),
        amount=100,
        dispensed_amount=80,
        claim_ticket_code="CLAIM123",
        error_message="Coin jam"
    )
    
    # Should run without throwing errors in mock mode
    await service.print_claim_ticket(record)


@pytest.mark.anyio
async def test_print_receipt_forex_currency():
    settings = Settings(
        paperang_enabled=True,
        use_mock_hardware=True
    )
    service = ReceiptService(settings)
    
    record = MockTransactionRecord(
        id="test-tx-forex-1",
        type="forex-usd-to-php",
        created_at=datetime(2026, 6, 25, 12, 0, 0),
        inserted_amount=10,
        dispensed_amount=550,
        fee=30,
        provider=None,
        from_currency="USD",
        to_currency="PHP",
        exchange_rate=58.0,
        converted_amount=580
    )
    
    rendered_lines = []
    def mock_render(lines):
        rendered_lines.extend(lines)
        return Image.new("1", (PAPERANG_WIDTH, 16), 1)
        
    service._render_text_lines = mock_render
    await service.print_receipt(record)
    
    assert "Inserted : USD 10" in rendered_lines
    assert "Dispensed : PHP 550" in rendered_lines
    assert "Fee : PHP 30" in rendered_lines
    assert "Conversion : USD -> PHP" in rendered_lines


@pytest.mark.anyio
async def test_print_claim_ticket_forex_currency():
    settings = Settings(
        paperang_enabled=True,
        use_mock_hardware=True
    )
    service = ReceiptService(settings)
    
    record = MockTransactionRecord(
        id="test-tx-forex-2",
        type="forex-php-to-usd",
        created_at=datetime(2026, 6, 25, 12, 0, 0),
        inserted_amount=600,
        dispensed_amount=0,
        claim_ticket_code="CLAIM789",
        error_message="Dispenser empty",
        to_currency="USD"
    )
    
    rendered_lines = []
    def mock_render(lines):
        rendered_lines.extend(lines)
        return Image.new("1", (PAPERANG_WIDTH, 16), 1)
        
    service._render_text_lines = mock_render
    await service.print_claim_ticket(record, shortfall=10)
    
    assert "Shortfall : USD 10" in rendered_lines


@pytest.mark.asyncio
async def test_wallet_receipts_omit_names_and_private_error_details():
    from unittest.mock import AsyncMock
    service = ReceiptService(Settings(paperang_enabled=True, use_mock_hardware=True))
    service._queue_print_job = AsyncMock()
    lines = []
    def render(captured):
        lines.extend(captured)
        return Image.new("1", (PAPERANG_WIDTH, 16), 1)
    service._render_text_lines = render
    record = {"transaction_id": "test-receipt", "provider": "gcash", "direction": "cash-in",
              "account_name": "coinnect", "mobile_number": "09171234567", "amount": 100,
              "inserted_amount": 100, "error_message": "Traceback: private failure", "error_code": "UNKNOWN"}
    await service.print_receipt(record)
    await service.print_claim_ticket(record)
    text = "\n".join(lines)
    assert "coinnect" not in text
    assert "Traceback" not in text
    assert "09171234567" not in text
    assert "Provider : GCASH" in text
