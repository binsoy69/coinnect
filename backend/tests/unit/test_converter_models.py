import pytest
from app.models.converter import (
    AcceptancePhase,
    ConverterIntakeState,
    CoinSessionState,
    ConverterErrorCode,
    PayoutItem,
    ConverterQuotePayload,
    ConverterClaimSnapshot,
    ConverterMetadata,
    ConverterSnapshot,
)


def test_converter_error_codes():
    assert ConverterErrorCode.QUOTE_CHANGED == "QUOTE_CHANGED"
    assert ConverterErrorCode.PAYOUT_REAPPROVAL_REQUIRED == "PAYOUT_REAPPROVAL_REQUIRED"
    assert ConverterErrorCode.ACCOUNTING_FAULT == "ACCOUNTING_FAULT"
    assert ConverterErrorCode.CASH_ALREADY_ACCEPTED == "CASH_ALREADY_ACCEPTED"
    assert ConverterErrorCode.EXCESS_REFUND_UNAVAILABLE == "EXCESS_REFUND_UNAVAILABLE"


def test_converter_enums():
    assert AcceptancePhase.OPEN == "OPEN"
    assert AcceptancePhase.CLOSING == "CLOSING"
    assert AcceptancePhase.CLOSED == "CLOSED"

    assert ConverterIntakeState.PREPARED == "PREPARED"
    assert ConverterIntakeState.RETAINED == "RETAINED"
    assert ConverterIntakeState.RETURNED == "RETURNED"
    assert ConverterIntakeState.UNCERTAIN == "UNCERTAIN"

    assert CoinSessionState.ACTIVE == "ACTIVE"
    assert CoinSessionState.CLOSING == "CLOSING"
    assert CoinSessionState.CLOSED == "CLOSED"
    assert CoinSessionState.UNCERTAIN == "UNCERTAIN"


def test_converter_quote_payload():
    item = PayoutItem(denom="PHP_50", denom_type="bill", count=1, value=50)
    assert item.denom == "PHP_50"
    assert item.value == 50

    quote = ConverterQuotePayload(
        id="q-1",
        service_type="bill-to-bill",
        input_amount=100,
        fee=5,
        total_due=100,
        payout_amount=95,
        items=[item],
        requested_counts={"50": 1},
        is_substitution=False,
        created_at="2026-09-05T12:00:00Z",
        expires_at="2026-09-05T12:02:00Z",
    )
    dumped = quote.model_dump()
    assert dumped["id"] == "q-1"
    assert dumped["payout_amount"] == 95
    assert len(dumped["items"]) == 1
    assert dumped["items"][0]["denom"] == "PHP_50"


def test_converter_snapshot_schema():
    snapshot = ConverterSnapshot(
        transaction_id="tx-999",
        type="bill-to-bill",
        state="WAITING_FOR_BILL",
        target_amount=100,
        fee=5,
        total_due=100,
        payout_amount=95,
        inserted_amount=0,
        dispensed_amount=0,
        revision=1,
        server_time="2026-09-05T12:00:00Z",
        can_continue=False,
        can_confirm=False,
        can_request_claim=True,
    )
    assert snapshot.transaction_id == "tx-999"
    assert snapshot.revision == 1
    assert snapshot.acceptance_phase == "OPEN"
    assert snapshot.can_request_claim is True

    # Test metadata schema
    meta = ConverterMetadata(
        revision=2,
        approved_quote_id="q-1",
        acceptance_phase=AcceptancePhase.CLOSING.value,
        coin_session_id=42,
    )
    assert meta.revision == 2
    assert meta.coin_session_id == 42
