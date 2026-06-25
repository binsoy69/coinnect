import pytest
from datetime import datetime
from PIL import Image
from app.core.config import Settings
from app.services.receipt_service import ReceiptService, PAPERANG_WIDTH


class MockTransactionRecord:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


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
