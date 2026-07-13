import pytest
from datetime import datetime
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.admin import router as admin_router
from app.services.admin_session import AdminSessionService
from app.services.operation_mode import OperationModeManager
from app.models.db_models import TransactionRecord, EWalletTransactionRecord, TransactionState


@pytest.fixture
async def claims_app(db_session_factory, test_settings):
    test_settings.admin_rfid_uids = "A1B2C3D4"
    app = FastAPI()
    app.include_router(admin_router, prefix="/api/v1")
    app.state.db_session_factory = db_session_factory
    mode = OperationModeManager()
    app.state.admin_sessions = AdminSessionService(test_settings, mode)
    return app


def _login(app):
    session = app.state.admin_sessions.login_rfid("A1B2C3D4")
    return session.token


async def test_claims_endpoints_require_admin(claims_app):
    transport = ASGITransport(app=claims_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET requires auth
        get_res = await client.get("/api/v1/admin/claims")
        assert get_res.status_code == 401
        
        # POST requires auth
        post_res = await client.post(
            "/api/v1/admin/claims/CLAIM123/resolve",
            json={"resolution_notes": "Resolved offline"}
        )
        assert post_res.status_code == 401


async def test_resolve_standard_and_ewallet_claims(claims_app, db_session_factory):
    # Seed data
    async with db_session_factory() as session:
        # 1. Standard transaction in ERROR state with a claim code
        tx_std = TransactionRecord(
            id="tx-std-1",
            type="bill-to-bill",
            state=TransactionState.ERROR.value,
            target_amount=500,
            fee=0,
            total_due=500,
            inserted_amount=500,
            dispensed_amount=0,
            claim_ticket_code="CLAIMSTD",
            error_code="PARTIAL_DISPENSE",
            error_message="Dispenser jam",
            created_at=datetime.utcnow()
        )
        
        # 2. E-wallet transaction in CLAIM_REQUIRED state
        tx_ew = EWalletTransactionRecord(
            id="tx-ew-1",
            provider="gcash",
            direction="cash-in",
            state="CLAIM_REQUIRED",
            amount=1000,
            fee=15,
            transfer_amount=985,
            total_due=1000,
            inserted_amount=1000,
            dispensed_amount=0,
            claim_ticket_code="CLAMEW",
            error_code="DISBURSEMENT_FAILED",
            error_message="Gateway timeout",
            created_at=datetime.utcnow()
        )
        
        session.add(tx_std)
        session.add(tx_ew)
        await session.commit()

    transport = ASGITransport(app=claims_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = _login(claims_app)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Verify GET retrieves both claims
        get_res = await client.get("/api/v1/admin/claims", headers=headers)
        assert get_res.status_code == 200
        data = get_res.json()
        assert len(data["claims"]) == 2
        
        # Check standard claim fields
        claim_std = next(c for c in data["claims"] if c["claim_ticket_code"] == "CLAIMSTD")
        assert claim_std["transaction_id"] == "tx-std-1"
        assert claim_std["shortfall"] == 500
        assert claim_std["error_code"] == "PARTIAL_DISPENSE"
        
        # Check ewallet claim fields
        claim_ew = next(c for c in data["claims"] if c["claim_ticket_code"] == "CLAMEW")
        assert claim_ew["transaction_id"] == "tx-ew-1"
        assert claim_ew["shortfall"] == 1000
        assert claim_ew["error_code"] == "DISBURSEMENT_FAILED"
        
        # Resolve standard claim
        res_std = await client.post(
            "/api/v1/admin/claims/CLAIMSTD/resolve",
            headers=headers,
            json={"resolution_notes": "Dispensed cash manually to user."}
        )
        assert res_std.status_code == 200
        assert res_std.json()["status"] == "success"
        
        # Verify resolved claim is no longer returned in active list
        get_res_2 = await client.get("/api/v1/admin/claims", headers=headers)
        assert len(get_res_2.json()["claims"]) == 1
        
        # Resolve ewallet claim
        res_ew = await client.post(
            "/api/v1/admin/claims/CLAMEW/resolve",
            headers=headers,
            json={"resolution_notes": "Triggered manual Gcash payout."}
        )
        assert res_ew.status_code == 200
        
        # Verify no claims left
        get_res_3 = await client.get("/api/v1/admin/claims", headers=headers)
        assert len(get_res_3.json()["claims"]) == 0

    # Assert in Database directly
    async with db_session_factory() as session:
        from sqlalchemy import select
        # Standard
        tx_std_db = await session.get(TransactionRecord, "tx-std-1")
        assert tx_std_db.state == "RESOLVED"
        assert tx_std_db.resolution_notes == "Dispensed cash manually to user."
        assert tx_std_db.resolved_at is not None
        assert tx_std_db.resolved_by is not None
        
        # EWallet
        tx_ew_db = await session.get(EWalletTransactionRecord, "tx-ew-1")
        assert tx_ew_db.state == "RESOLVED"
        assert tx_ew_db.resolution_notes == "Triggered manual Gcash payout."
        assert tx_ew_db.resolved_at is not None
        assert tx_ew_db.resolved_by is not None
