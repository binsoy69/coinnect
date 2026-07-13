"""PIN-authenticated local maintenance sessions."""

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.services.admin_session import AdminAuthError, AdminSession
from app.services.operation_mode import OperationModeError

router = APIRouter(prefix="/admin", tags=["admin"])



def require_admin_session(
    request: Request, authorization: str | None
) -> AdminSession:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
        )
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return request.app.state.admin_sessions.validate(token)
    except AdminAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc



@router.get("/session")
async def get_admin_session(
    request: Request, authorization: str | None = Header(default=None)
):
    session = require_admin_session(request, authorization)
    return {
        "session_id": session.session_id,
        "expires_at": session.expires_at.isoformat(),
    }


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_session(
    request: Request, authorization: str | None = Header(default=None)
):
    session = require_admin_session(request, authorization)
    token = authorization.removeprefix("Bearer ").strip()
    request.app.state.admin_sessions.logout(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/home-sorter", status_code=status.HTTP_200_OK)
async def trigger_home_sorter(
    request: Request,
    authorization: str | None = Header(default=None)
):
    require_admin_session(request, authorization)
    bill_controller = request.app.state.bill_acceptor._bill
    try:
        await bill_controller.home()
        return {"status": "success", "message": "Sorter homed successfully"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to home sorter: {exc}"
        )


class ResolveClaimRequest(BaseModel):
    resolution_notes: str = Field(min_length=1, max_length=1000)


@router.get("/claims", status_code=status.HTTP_200_OK)
async def get_claims(
    request: Request,
    authorization: str | None = Header(default=None)
):
    require_admin_session(request, authorization)
    session_factory = request.app.state.db_session_factory
    
    from sqlalchemy import select
    from app.models.db_models import TransactionRecord, EWalletTransactionRecord
    
    claims = []
    
    async with session_factory() as session:
        # Query standard transaction claims (unresolved errors with claim tickets)
        stmt_std = select(TransactionRecord).where(
            TransactionRecord.state == "ERROR",
            TransactionRecord.claim_ticket_code.isnot(None),
            TransactionRecord.resolved_at.is_(None)
        )
        res_std = await session.execute(stmt_std)
        for tx in res_std.scalars().all():
            shortfall = tx.total_due - tx.dispensed_amount
            claims.append({
                "claim_ticket_code": tx.claim_ticket_code,
                "transaction_id": tx.id,
                "type": tx.type,
                "amount": tx.total_due,
                "inserted_amount": tx.inserted_amount,
                "dispensed_amount": tx.dispensed_amount,
                "shortfall": shortfall if shortfall > 0 else tx.target_amount,
                "error_code": tx.error_code,
                "error_message": tx.error_message,
                "created_at": tx.created_at.isoformat(),
                "direction": None,
                "provider": None,
                "mobile_number": None,
                "account_name": None,
            })
            
        # Query ewallet transaction claims
        stmt_ew = select(EWalletTransactionRecord).where(
            EWalletTransactionRecord.state == "CLAIM_REQUIRED",
            EWalletTransactionRecord.resolved_at.is_(None)
        )
        res_ew = await session.execute(stmt_ew)
        for tx in res_ew.scalars().all():
            shortfall = tx.amount - tx.dispensed_amount
            claims.append({
                "claim_ticket_code": tx.claim_ticket_code,
                "transaction_id": tx.id,
                "type": f"ewallet-{tx.direction}",
                "amount": tx.amount,
                "inserted_amount": tx.inserted_amount,
                "dispensed_amount": tx.dispensed_amount,
                "shortfall": shortfall if shortfall > 0 else tx.transfer_amount,
                "error_code": tx.error_code,
                "error_message": tx.error_message,
                "created_at": tx.created_at.isoformat(),
                "direction": tx.direction,
                "provider": tx.provider,
                "mobile_number": tx.mobile_number,
                "account_name": tx.account_name,
            })
            
    # Sort claims by created_at descending
    claims.sort(key=lambda c: c["created_at"], reverse=True)
    return {"claims": claims}


@router.post("/claims/{claim_ticket_code}/resolve", status_code=status.HTTP_200_OK)
async def resolve_claim(
    claim_ticket_code: str,
    body: ResolveClaimRequest,
    request: Request,
    authorization: str | None = Header(default=None)
):
    admin = require_admin_session(request, authorization)
    session_factory = request.app.state.db_session_factory
    
    from datetime import datetime
    from sqlalchemy import select
    from app.models.db_models import TransactionRecord, EWalletTransactionRecord
    
    async with session_factory() as session:
        # 1. Look in TransactionRecord
        stmt_std = select(TransactionRecord).where(
            TransactionRecord.claim_ticket_code == claim_ticket_code
        )
        res_std = await session.execute(stmt_std)
        tx_std = res_std.scalar_one_or_none()
        
        if tx_std:
            if tx_std.resolved_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Claim has already been resolved"
                )
            tx_std.state = "RESOLVED"
            tx_std.resolved_at = datetime.utcnow()
            tx_std.resolution_notes = body.resolution_notes
            tx_std.resolved_by = admin.session_id
            await session.commit()
            return {"status": "success", "message": f"Claim {claim_ticket_code} resolved successfully"}
            
        # 2. Look in EWalletTransactionRecord
        stmt_ew = select(EWalletTransactionRecord).where(
            EWalletTransactionRecord.claim_ticket_code == claim_ticket_code
        )
        res_ew = await session.execute(stmt_ew)
        tx_ew = res_ew.scalar_one_or_none()
        
        if tx_ew:
            if tx_ew.resolved_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Claim has already been resolved"
                )
            tx_ew.state = "RESOLVED"
            tx_ew.resolved_at = datetime.utcnow()
            tx_ew.resolution_notes = body.resolution_notes
            tx_ew.resolved_by = admin.session_id
            await session.commit()
            return {"status": "success", "message": f"Claim {claim_ticket_code} resolved successfully"}
            
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim ticket code {claim_ticket_code} not found"
        )
