from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.services.paymongo_client import DisbursementResult, QRPaymentResult
from healthcheck_api.ewallet_sandbox import (
    CallbackAuditRecord,
    EWalletSandboxConfig,
    EWalletSandboxService,
    SandboxSessionRecord,
    SandboxState,
    create_sandbox_database,
)
from healthcheck_api.models import EWalletSandboxSessionCreate


@pytest.fixture
async def sandbox_dependencies(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'sandbox.db'}"
    engine, factory = await create_sandbox_database(database_url)
    settings = Settings(
        paymongo_secret_key="sk_test_secret",
        paymongo_public_key="pk_test_public",
        paymongo_webhook_secret="whsec_test",
        paymongo_sandbox=True,
        paymongo_source_account_number="source-001",
        paymongo_source_account_name="Coinnect",
        paymongo_source_account_bic="PAEYPHM2XXX",
        _env_file=None,
    )
    gateway = AsyncMock()
    gateway.create_qr_payment.return_value = QRPaymentResult(
        payment_intent_id="pi_test_1",
        status="awaiting_next_action",
        qr_image_url="https://sandbox.example/qr.png",
        test_url="https://sandbox.example/pay",
    )
    gateway.create_disbursement.return_value = DisbursementResult(
        batch_transfer_id="batch_tr_test_1",
        transfer_id="tr_test_1",
        status="pending",
    )
    config = EWalletSandboxConfig(
        database_url=database_url,
        public_base_url="https://healthcheck.example.com",
        timeout_seconds=600,
        retention_limit=100,
    )
    service = EWalletSandboxService(settings, gateway, factory, config)
    yield service, gateway, factory
    await engine.dispose()


def cash_out_request(**overrides):
    payload = {
        "provider": "gcash",
        "direction": "cash-out",
        "amount": 100,
    }
    payload.update(overrides)
    return EWalletSandboxSessionCreate(**payload)


def cash_in_request(**overrides):
    payload = {
        "provider": "maya",
        "direction": "cash-in",
        "amount": 100,
        "mobile_number": "09181234567",
        "account_name": "Sandbox User",
    }
    payload.update(overrides)
    return EWalletSandboxSessionCreate(**payload)


def paid_intent(session_id: str, intent_id: str, amount: int = 100):
    return {
        "id": intent_id,
        "attributes": {
            "amount": amount * 100,
            "currency": "PHP",
            "status": "succeeded",
            "metadata": {"coinnect_transaction_id": session_id},
            "payments": [
                {
                    "id": "pay_test_1",
                    "attributes": {
                        "amount": amount * 100,
                        "currency": "PHP",
                        "status": "paid",
                        "source": {"type": "qrph"},
                    },
                }
            ],
        },
    }


@pytest.mark.parametrize(
    ("config", "missing"),
    [
        (
            EWalletSandboxConfig(
                public_base_url="http://healthcheck.example.com",
                database_url="sqlite+aiosqlite:///:memory:",
            ),
            "HEALTHCHECK_PUBLIC_BASE_URL must use HTTPS",
        ),
        (
            EWalletSandboxConfig(
                public_base_url="",
                database_url="sqlite+aiosqlite:///:memory:",
            ),
            "HEALTHCHECK_PUBLIC_BASE_URL",
        ),
    ],
)
def test_config_reports_public_url_problems(config, missing):
    settings = Settings(
        paymongo_secret_key="sk_test_secret",
        paymongo_public_key="pk_test_public",
        paymongo_webhook_secret="whsec_test",
        paymongo_source_account_number="source-001",
        _env_file=None,
    )

    readiness = config.readiness(settings)

    assert readiness["ready"] is False
    assert missing in readiness["missing"]


def test_config_rejects_live_or_non_test_credentials():
    config = EWalletSandboxConfig(
        public_base_url="https://healthcheck.example.com",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    settings = Settings(
        paymongo_sandbox=False,
        paymongo_secret_key="sk_live_secret",
        paymongo_public_key="pk_live_public",
        paymongo_webhook_secret="whsec_live",
        paymongo_source_account_number="source-001",
        _env_file=None,
    )

    readiness = config.readiness(settings)

    assert readiness["ready"] is False
    assert "PAYMONGO_SANDBOX must be true" in readiness["missing"]
    assert "PAYMONGO_SECRET_KEY must be a test key" in readiness["missing"]
    assert "PAYMONGO_PUBLIC_KEY must be a test key" in readiness["missing"]


async def test_cash_out_creates_qr_without_hardware(sandbox_dependencies):
    service, gateway, _factory = sandbox_dependencies

    session = await service.create_session(cash_out_request())

    assert session["state"] == SandboxState.PENDING_CALLBACK
    assert session["gateway_payment_intent_id"] == "pi_test_1"
    assert session["qr_image_url"].endswith("qr.png")
    gateway.create_qr_payment.assert_awaited_once()


async def test_cash_in_uses_healthcheck_transfer_callback(sandbox_dependencies):
    service, gateway, _factory = sandbox_dependencies

    session = await service.create_session(cash_in_request())

    assert session["state"] == SandboxState.PENDING_CALLBACK
    kwargs = gateway.create_disbursement.await_args.kwargs
    assert kwargs["amount_centavos"] == 10_000
    assert kwargs["callback_url"] == (
        "https://healthcheck.example.com/api/v1/"
        "ewallet-sandbox/callbacks/transfer"
    )


async def test_payment_callback_verifies_gateway_resource(sandbox_dependencies):
    service, gateway, _factory = sandbox_dependencies
    session = await service.create_session(cash_out_request())
    gateway.get_payment_intent.return_value = paid_intent(
        session["transaction_id"],
        session["gateway_payment_intent_id"],
    )

    result = await service.process_payment_event(
        {
            "id": "evt_paid_1",
            "type": "payment.paid",
            "resource_id": session["gateway_payment_intent_id"],
            "payment_id": "pay_test_1",
        }
    )

    assert result["state"] == SandboxState.VERIFIED
    gateway.get_payment_intent.assert_awaited_once_with("pi_test_1")


@pytest.mark.parametrize(
    ("mutate", "expected_error"),
    [
        (
            lambda payload: payload.update(id="pi_wrong"),
            "PAYMENT_INTENT_MISMATCH",
        ),
        (
            lambda payload: payload["attributes"].update(amount=9_900),
            "PAYMENT_AMOUNT_MISMATCH",
        ),
        (
            lambda payload: payload["attributes"].update(currency="USD"),
            "PAYMENT_CURRENCY_MISMATCH",
        ),
        (
            lambda payload: payload["attributes"]["metadata"].update(
                coinnect_transaction_id="wrong"
            ),
            "PAYMENT_REFERENCE_MISMATCH",
        ),
        (
            lambda payload: payload["attributes"]["payments"][0][
                "attributes"
            ]["source"].update(type="card"),
            "PAYMENT_SOURCE_MISMATCH",
        ),
    ],
)
async def test_payment_mismatch_never_verifies(
    sandbox_dependencies, mutate, expected_error
):
    service, gateway, _factory = sandbox_dependencies
    session = await service.create_session(cash_out_request())
    intent = paid_intent(
        session["transaction_id"],
        session["gateway_payment_intent_id"],
    )
    mutate(intent)
    gateway.get_payment_intent.return_value = intent

    result = await service.process_payment_event(
        {
            "id": f"evt_{expected_error}",
            "type": "payment.paid",
            "resource_id": session["gateway_payment_intent_id"],
            "payment_id": "pay_test_1",
        }
    )

    assert result["state"] == SandboxState.FAILED
    assert result["error_code"] == expected_error


async def test_duplicate_payment_callback_is_idempotent(sandbox_dependencies):
    service, gateway, factory = sandbox_dependencies
    session = await service.create_session(cash_out_request())
    gateway.get_payment_intent.return_value = paid_intent(
        session["transaction_id"],
        session["gateway_payment_intent_id"],
    )
    event = {
        "id": "evt_duplicate",
        "type": "payment.paid",
        "resource_id": session["gateway_payment_intent_id"],
        "payment_id": "pay_test_1",
    }

    await service.process_payment_event(event)
    duplicate = await service.process_payment_event(event)

    assert duplicate == {"duplicate": True}
    gateway.get_payment_intent.assert_awaited_once()
    async with factory() as db:
        count = await db.scalar(select(func.count(CallbackAuditRecord.id)))
        assert count == 1


async def test_unknown_callback_is_audited_without_session_change(
    sandbox_dependencies,
):
    service, gateway, factory = sandbox_dependencies

    result = await service.process_payment_event(
        {
            "id": "evt_unknown",
            "type": "payment.paid",
            "resource_id": "pi_unknown",
            "payment_id": "pay_unknown",
        }
    )

    assert result == {"processed": False, "reason": "session_not_found"}
    gateway.get_payment_intent.assert_not_awaited()
    async with factory() as db:
        audit = await db.get(CallbackAuditRecord, "payment:evt_unknown")
        assert audit.outcome == "session_not_found"


async def test_transfer_callback_reconciles_before_verifying(
    sandbox_dependencies,
):
    service, gateway, _factory = sandbox_dependencies
    session = await service.create_session(cash_in_request())
    gateway.get_batch_transfer.return_value = {
        "id": session["gateway_batch_transfer_id"],
        "transfers": [
            {
                "id": session["gateway_transfer_id"],
                "status": "succeeded",
                "reference_number": session["transaction_id"],
            }
        ],
    }

    result = await service.process_transfer_callback(
        session["gateway_batch_transfer_id"]
    )

    assert result["state"] == SandboxState.VERIFIED


async def test_transfer_mismatch_fails_session(sandbox_dependencies):
    service, gateway, _factory = sandbox_dependencies
    session = await service.create_session(cash_in_request())
    gateway.get_batch_transfer.return_value = {
        "id": session["gateway_batch_transfer_id"],
        "transfers": [
            {
                "id": "wrong-transfer",
                "status": "succeeded",
                "reference_number": session["transaction_id"],
            }
        ],
    }

    result = await service.process_transfer_callback(
        session["gateway_batch_transfer_id"]
    )

    assert result["state"] == SandboxState.FAILED
    assert result["error_code"] == "TRANSFER_RECONCILIATION_MISMATCH"


async def test_cancel_and_late_callback_preserve_terminal_state(
    sandbox_dependencies,
):
    service, gateway, _factory = sandbox_dependencies
    session = await service.create_session(cash_out_request())
    cancelled = await service.cancel_session(session["transaction_id"])
    gateway.get_payment_intent.return_value = paid_intent(
        session["transaction_id"],
        session["gateway_payment_intent_id"],
    )

    late = await service.process_payment_event(
        {
            "id": "evt_late",
            "type": "payment.paid",
            "resource_id": session["gateway_payment_intent_id"],
            "payment_id": "pay_test_1",
        }
    )

    assert cancelled["state"] == SandboxState.CANCELLED
    assert late["state"] == SandboxState.CANCELLED
    gateway.get_payment_intent.assert_not_awaited()


async def test_expire_pending_sessions(sandbox_dependencies):
    service, _gateway, factory = sandbox_dependencies
    session = await service.create_session(cash_out_request())
    async with factory() as db:
        record = await db.get(SandboxSessionRecord, session["transaction_id"])
        record.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            seconds=1
        )
        await db.commit()

    expired_count = await service.expire_pending_sessions()
    expired = await service.get_session(session["transaction_id"])

    assert expired_count == 1
    assert expired["state"] == SandboxState.TIMED_OUT


async def test_prune_keeps_pending_and_newest_completed(
    sandbox_dependencies,
):
    service, _gateway, factory = sandbox_dependencies
    service._config.retention_limit = 2
    pending = await service.create_session(cash_out_request())
    for index in range(3):
        async with factory() as db:
            db.add(
                SandboxSessionRecord(
                    id=f"completed-{index}",
                    provider="gcash",
                    direction="cash-out",
                    amount=100,
                    state=SandboxState.VERIFIED,
                    completed_at=datetime(2026, 1, index + 1),
                    expires_at=datetime(2026, 1, index + 1),
                )
            )
            await db.commit()

    await service.prune_completed_sessions()
    sessions = await service.list_sessions()

    assert {item["transaction_id"] for item in sessions} == {
        pending["transaction_id"],
        "completed-1",
        "completed-2",
    }
