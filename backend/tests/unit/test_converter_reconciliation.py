from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.api.admin import IntakeResolutionRequest, reconcile_converter_bill
from app.models.db_models import ConverterIntakeOperation, TransactionRecord, ClaimRecord
from tests.unit.test_uno_coin_session import setup_env


@pytest.mark.asyncio
@pytest.mark.parametrize("retained, expected_credit", [(True, 100), (False, 0)])
async def test_intake_resolution_is_idempotent_and_updates_claim(setup_env, retained, expected_credit):
    env = setup_env
    factory = env["session_factory"]
    async with factory() as session:
        session.add(TransactionRecord(id="reconcile-tx", type="bill-to-coin", state="CLAIM_REQUIRED",
            target_amount=100, fee=5, total_due=100, inserted_amount=0, converter_metadata={"revision": 1}))
        session.add(ConverterIntakeOperation(id="uncertain-bill", transaction_id="reconcile-tx",
            denomination="PHP_100", value=100, state="UNCERTAIN"))
        session.add(ClaimRecord(id="claim", transaction_id="reconcile-tx", source_kind="STANDARD",
            claim_ticket_code="TEST-CLAIM", claim_kind="INPUT_REFUND", status="PROVISIONAL",
            amount=100, currency="PHP", reason_code="INTAKE_UNCERTAIN", ambiguous_amount=100))
        await session.commit()
    request = MagicMock()
    request.app.state = SimpleNamespace(
        admin_sessions=MagicMock(), transaction_orchestrator=env["orchestrator"],
        db_session_factory=factory, inventory_service=env["inventory_service"],
    )
    body = IntakeResolutionRequest(retained=retained, notes="Technician inspected the cash path")
    for _ in range(2):
        await reconcile_converter_bill("uncertain-bill", body, request, "Bearer technician")
    async with factory() as session:
        record = await session.get(TransactionRecord, "reconcile-tx")
        operation = await session.get(ConverterIntakeOperation, "uncertain-bill")
        claim = await session.get(ClaimRecord, "claim")
        assert record.inserted_amount == expected_credit
        assert operation.state == ("RETAINED" if retained else "RETURNED")
        assert claim.amount == expected_credit
        assert claim.ambiguous_amount == 0
        assert claim.status == ("OPEN" if retained else "RESOLVED")
