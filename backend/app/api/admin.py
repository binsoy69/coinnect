import asyncio
import logging

logger = logging.getLogger(__name__)
"""PIN-authenticated local maintenance sessions."""

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, StrictInt

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
    from app.models.db_models import ClaimRecord, TransactionRecord, EWalletTransactionRecord, EWalletIntake, EWalletCoinSession, PhysicalOperation
    
    claims = []
    
    async with session_factory() as session:
        unified = (
            await session.execute(
                select(ClaimRecord).where(ClaimRecord.status != "RESOLVED")
            )
        ).scalars().all()
        claims.extend(request.app.state.claim_service.serialize(claim) for claim in unified)
        all_unified = (await session.execute(select(ClaimRecord))).scalars().all()
        represented = {claim.claim_ticket_code for claim in all_unified}
        represented_transactions = {(claim.source_kind, claim.transaction_id) for claim in all_unified}
        # Query standard transaction claims (unresolved errors with claim tickets)
        stmt_std = select(TransactionRecord).where(
            TransactionRecord.state == "ERROR",
            TransactionRecord.claim_ticket_code.isnot(None),
            TransactionRecord.resolved_at.is_(None)
        )
        res_std = await session.execute(stmt_std)
        for tx in res_std.scalars().all():
            if tx.claim_ticket_code in represented or ("STANDARD", tx.id) in represented_transactions:
                continue
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
            if tx.claim_ticket_code in represented or ("EWALLET", tx.id) in represented_transactions:
                continue
            shortfall = (max(0, tx.inserted_amount - tx.wallet_credited - (tx.fee if tx.wallet_credited else 0) - tx.change_dispensed)
                         if tx.direction == "cash-in" else max(0, tx.amount - tx.dispensed_amount))
            claims.append({
                "claim_ticket_code": tx.claim_ticket_code,
                "transaction_id": tx.id,
                "type": f"ewallet-{tx.direction}",
                "amount": tx.amount,
                "inserted_amount": tx.inserted_amount,
                "dispensed_amount": tx.dispensed_amount,
                "shortfall": shortfall,
                "error_code": tx.error_code,
                "error_message": tx.error_message,
                "created_at": tx.created_at.isoformat(),
                "direction": tx.direction,
                "provider": tx.provider,
                "mobile_number": tx.mobile_number,
                "account_name": tx.account_name,
            })
            
    from app.models.db_models import ForexClaimTicket
    async with session_factory() as session:
        tickets = (await session.execute(select(ForexClaimTicket))).scalars().all()
    for ticket in tickets:
        itemized = await request.app.state.claim_service.get_forex(ticket_id=ticket.id)
        if itemized["status"] != "RESOLVED":
            claims.append(itemized)

    # Sort claims by created_at descending
    claims.sort(key=lambda c: c["created_at"], reverse=True)
    async with session_factory() as session:
        retained = (await session.execute(select(EWalletTransactionRecord).where(
            EWalletTransactionRecord.state == "ABANDONED_RETAINED"
        ).order_by(EWalletTransactionRecord.created_at.desc()))).scalars().all()
        bill_ops = (await session.execute(select(EWalletIntake).where(EWalletIntake.state == "PREPARED"))).scalars().all()
        coin_ops = (await session.execute(select(EWalletCoinSession).where(EWalletCoinSession.state == "UNCERTAIN"))).scalars().all()
        payouts = (await session.execute(select(PhysicalOperation).where(PhysicalOperation.state.in_({"AMBIGUOUS", "STARTED"})))).scalars().all()
    return {"claims": claims, "retained_cash": [{"transaction_id": row.id,
        "amount": row.retained_amount, "created_at": row.created_at.isoformat()} for row in retained],
        "intake_operations": [{"id": row.id, "transaction_id": row.transaction_id, "value": row.value, "medium": "BILL"} for row in bill_ops]
          + [{"id": row.sid, "transaction_id": row.transaction_id, "counts": row.counts, "medium": "COIN"} for row in coin_ops]
          + [{"id": row.id, "transaction_id": row.transaction_id, "medium": "PAYOUT", "denomination": row.denomination, "requested_count": row.requested_count} for row in payouts]}


class EWalletIntakeResolution(BaseModel):
    medium: str
    retained: bool = False
    counts: dict[str, int] = Field(default_factory=dict)
    notes: str = Field(min_length=5, max_length=1000)


@router.post("/ewallet/intakes/{operation_id}/reconcile")
async def reconcile_ewallet_intake(operation_id: str, body: EWalletIntakeResolution,
    request: Request, authorization: str | None = Header(default=None)):
    admin = require_admin_session(request, authorization)
    orchestrator = request.app.state.ewallet_orchestrator
    if orchestrator.has_active_transaction:
        raise HTTPException(409, detail="Close the customer session before reconciliation")
    notes = f"{admin.session_id}: {body.notes}"
    try:
        if body.medium == "BILL":
            return await orchestrator.reconcile_intake(operation_id, body.retained, notes)
        if body.medium != "COIN" or set(body.counts) != {"1", "5", "10", "20"} or any(type(v) is not int or not 0 <= v <= 1000 for v in body.counts.values()):
            raise ValueError("Enter confirmed counts for PHP 1, 5, 10, and 20")
        return await orchestrator.reconcile_coin_session(int(operation_id), body.counts, notes)
    except Exception as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@router.post("/ewallet/{transaction_id}/reconcile")
async def reconcile_ewallet_payment(transaction_id: str, request: Request,
    authorization: str | None = Header(default=None)):
    require_admin_session(request, authorization)
    orchestrator = request.app.state.ewallet_orchestrator
    try:
        record = await orchestrator._record(transaction_id)
        if record.direction == "cash-out":
            return await orchestrator._verify_and_dispense_cash_out(transaction_id)
        if not record.gateway_batch_transfer_id:
            raise ValueError("No verified transfer identifiers; inspect the gateway by transaction reference")
        return await orchestrator._verify_and_complete_cash_in(transaction_id)
    except Exception as exc:
        raise HTTPException(409, detail=str(exc)) from exc


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
    from app.models.db_models import ClaimRecord, TransactionRecord, EWalletTransactionRecord
    
    async with session_factory() as session:
        from app.models.db_models import ForexClaimTicket
        if await session.get(ForexClaimTicket, claim_ticket_code):
            raise HTTPException(status_code=409, detail="Resolve each currency item separately")
        claim = (
            await session.execute(
                select(ClaimRecord).where(
                    ClaimRecord.claim_ticket_code == claim_ticket_code
                )
            )
        ).scalar_one_or_none()
        if claim:
            if claim.source_kind == "FOREX":
                raise HTTPException(status_code=409, detail="Legacy forex claim requires accounting review")
            if claim.status == "PROVISIONAL":
                raise HTTPException(status_code=409, detail="Reconcile the uncertain outcome before settling this claim")
            if claim.resolved_at is not None:
                raise HTTPException(status_code=400, detail="Claim has already been resolved")
            claim.status = "RESOLVED"
            claim.resolved_at = datetime.utcnow()
            claim.resolution_notes = body.resolution_notes
            claim.resolved_by = admin.session_id
            model = EWalletTransactionRecord if claim.source_kind == "EWALLET" else TransactionRecord
            source = await session.get(model, claim.transaction_id)
            if source:
                source.resolved_at = claim.resolved_at
                source.resolved_by = admin.session_id
                source.resolution_notes = body.resolution_notes
                source.state = "RESOLVED"
            await session.commit()
            return {"status": "success", "message": f"Claim {claim_ticket_code} resolved successfully"}
        # 1. Look in TransactionRecord
        stmt_std = select(TransactionRecord).where(
            TransactionRecord.claim_ticket_code == claim_ticket_code
        )
        res_std = await session.execute(stmt_std)
        tx_std = res_std.scalar_one_or_none()
        
        if tx_std:
            if tx_std.type.startswith("forex-"):
                raise HTTPException(status_code=409, detail="Legacy forex claim requires accounting review")
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


class ReconcilePhysicalOperationRequest(BaseModel):
    actual_dispensed_count: int = Field(ge=0, le=50)
    resolution_notes: str = Field(min_length=1, max_length=1000)


@router.post("/physical-operations/{operation_id}/reconcile")
async def reconcile_physical_operation(
    operation_id: str,
    body: ReconcilePhysicalOperationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    admin = require_admin_session(request, authorization)
    from datetime import datetime
    from sqlalchemy import select
    from app.models.db_models import (
        ClaimRecord,
        DispenseExecution,
        PhysicalOperation,
        PhysicalOperationState,
    )

    factory = request.app.state.db_session_factory
    async with factory() as session:
        operation = await session.get(PhysicalOperation, operation_id)
        if operation is None:
            raise HTTPException(status_code=404, detail="Physical operation not found")
        execution = await session.get(DispenseExecution, operation.execution_id)
        if execution.source_kind == "FOREX":
            raise HTTPException(status_code=409, detail="Legacy forex payout requires accounting review")
        if operation.state not in {"AMBIGUOUS", "STARTED"}:
            raise HTTPException(status_code=409, detail="Operation is not ambiguous")
        if body.actual_dispensed_count > operation.requested_count:
            raise HTTPException(status_code=422, detail="Actual count exceeds requested count")
        restore_count = operation.requested_count - body.actual_dispensed_count
        operation.confirmed_count = body.actual_dispensed_count
        operation.state = PhysicalOperationState.RECONCILED.value
        operation.inventory_reconciled = True
        operation.completed_at = datetime.utcnow()
        operation.reconciliation_notes = body.resolution_notes
        operation.reconciled_by = admin.session_id
        execution = await session.get(DispenseExecution, operation.execution_id)
        operations = (
            await session.execute(
                select(PhysicalOperation).where(
                    PhysicalOperation.execution_id == operation.execution_id
                )
            )
        ).scalars().all()
        confirmed = sum(op.confirmed_count * op.denomination_value for op in operations)
        ambiguous = sum(
            (op.requested_count - op.confirmed_count) * op.denomination_value
            for op in operations if op.state in {"AMBIGUOUS", "STARTED"}
        )
        execution.confirmed_amount = confirmed
        execution.ambiguous_amount = ambiguous
        execution.state = (
            "AMBIGUOUS" if ambiguous
            else "COMPLETE" if confirmed == execution.requested_amount
            else "FAILED"
        )
        claim = (
            await session.execute(
                select(ClaimRecord).where(
                    ClaimRecord.transaction_id == operation.transaction_id,
                    ClaimRecord.status != "RESOLVED",
                ).limit(1)
            )
        ).scalar_one_or_none()
        if claim:
            claim.confirmed_dispensed_amount = confirmed
            claim.ambiguous_amount = ambiguous
            from app.models.db_models import TransactionRecord, EWalletTransactionRecord
            converter = await session.get(TransactionRecord, operation.transaction_id)
            wallet = await session.get(EWalletTransactionRecord, operation.transaction_id) if execution.source_kind.startswith("EWALLET") else None
            obligation = converter.inserted_amount if converter else execution.requested_amount
            if wallet and wallet.resolved_at is None:
                if execution.source_kind == "EWALLET_CHANGE":
                    wallet.change_dispensed = confirmed
                    obligation = max(0, wallet.inserted_amount - wallet.wallet_credited - (wallet.fee if wallet.wallet_credited else 0))
                else:
                    wallet.dispensed_amount = confirmed
                    obligation = wallet.transfer_amount if confirmed >= wallet.transfer_amount else wallet.amount
                    wallet.refunded_fee = wallet.fee if confirmed < wallet.transfer_amount else 0
            claim.amount = max(0, obligation - confirmed)
            if claim.amount == 0 and not ambiguous:
                claim.status = "RESOLVED"
                claim.resolved_at = datetime.utcnow()
                claim.resolved_by = admin.session_id
                if wallet and wallet.resolved_at is None:
                    wallet.state = "RESOLVED"
                    wallet.resolved_at = claim.resolved_at
                    wallet.resolved_by = admin.session_id
                    wallet.resolution_notes = body.resolution_notes
            else:
                claim.status = "PROVISIONAL" if ambiguous else "OPEN"
            claim.resolution_notes = body.resolution_notes
        if restore_count:
            location = "BILL_DISPENSER" if operation.controller == "BILL" else "COIN_DISPENSER"
            await request.app.state.inventory_service.restore_in_session(
                session,
                {(location, operation.denomination): restore_count},
                reference_id=operation.transaction_id,
            )
        await session.commit()

    if execution.source_kind in {"FOREX_EXCHANGE", "FOREX_CHANGE"}:
        await request.app.state.forex_transaction_orchestrator.reconcile_payout(operation.transaction_id)
    await request.app.state.inventory_service._refresh_runtime()
    controller = (
        request.app.state.bill_controller
        if operation.controller == "BILL"
        else request.app.state.coin_controller
    )
    from app.core.errors import HardwareError

    try:
        await controller.acknowledge_operation(operation.id)
    except HardwareError as exc:
        # The operator's verified counts are already committed. A controller
        # reset or cleared journal can leave nothing to acknowledge.
        if exc.code != "NOT_FOUND":
            raise HTTPException(503, detail=f"Reconciliation saved, but controller acknowledgement failed: {exc}") from exc
        logger.info("Reconciled operation %s is no longer in the controller journal", operation.id)
    return {
        "operation_id": operation.id,
        "state": "RECONCILED",
        "actual_dispensed_count": body.actual_dispensed_count,
        "restored_count": restore_count,
    }


class UpdateFeesRequest(BaseModel):
    fee_bill_to_bill: float | None = None
    fee_bill_to_coin: float | None = None
    fee_coin_to_bill: float | None = None
    ewallet_fee_tiers: list | None = None
    forex_fees: dict | None = None


@router.get("/fees", status_code=status.HTTP_200_OK)
async def get_fees(request: Request):
    """Get current machine fee settings."""
    settings = request.app.state.settings
    return {
        "fee_bill_to_bill": int(getattr(settings, "fee_bill_to_bill", 10)),
        "fee_bill_to_coin": int(getattr(settings, "fee_bill_to_coin", 15)),
        "fee_coin_to_bill": int(getattr(settings, "fee_coin_to_bill", 3)),
        "ewallet_fee_tiers": [
            tier.model_dump() if hasattr(tier, "model_dump") else tier
            for tier in getattr(settings, "ewallet_fee_tiers", [])
        ],
        "forex_fees": {
            "usd-to-php": float(getattr(settings, "forex_fee_usd_to_php", 5.0)),
            "php-to-usd": float(getattr(settings, "forex_fee_php_to_usd", 5.0)),
            "eur-to-php": float(getattr(settings, "forex_fee_eur_to_php", 5.0)),
            "php-to-eur": float(getattr(settings, "forex_fee_php_to_eur", 5.0)),
        },
    }


@router.put("/fees", status_code=status.HTTP_200_OK)
async def update_fees(
    body: UpdateFeesRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Update machine fee settings (Admin session required)."""
    require_admin_session(request, authorization)
    settings = request.app.state.settings

    if body.fee_bill_to_bill is not None:
        settings.fee_bill_to_bill = int(body.fee_bill_to_bill)
    if body.fee_bill_to_coin is not None:
        settings.fee_bill_to_coin = int(body.fee_bill_to_coin)
    if body.fee_coin_to_bill is not None:
        settings.fee_coin_to_bill = int(body.fee_coin_to_bill)

    if body.ewallet_fee_tiers is not None:
        from app.core.config import EWalletFeeTier
        new_tiers = []
        for t in body.ewallet_fee_tiers:
            if isinstance(t, dict):
                new_tiers.append(EWalletFeeTier(**t))
            elif isinstance(t, EWalletFeeTier):
                new_tiers.append(t)
        settings.ewallet_fee_tiers = new_tiers

    if body.forex_fees is not None:
        try:
            await request.app.state.forex_rate_service.update_fees(body.forex_fees)
        except (ValueError, ArithmeticError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return await get_fees(request)


@router.post("/tamper-recovery", status_code=status.HTTP_200_OK)
async def tamper_recovery(
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Recover machine from tamper lockdown state after technician inspection."""
    require_admin_session(request, authorization)
    session_factory = request.app.state.db_session_factory
    from sqlalchemy import select
    from app.models.db_models import PhysicalOperation, ConverterIntakeOperation, ConverterCoinSession

    async with session_factory() as session:
        unresolved = (
            await session.execute(
                select(PhysicalOperation).where(
                    PhysicalOperation.state.in_(["AMBIGUOUS", "STARTED"])
                )
            )
        ).scalars().all()
        if unresolved:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unresolved physical operations exist. Reconcile them before completing tamper recovery."
            )

    async with session_factory() as session:
        intake = (await session.execute(select(ConverterIntakeOperation).where(
            ConverterIntakeOperation.state.in_(["PREPARED", "UNCERTAIN"])
        ))).scalars().first()
        coins = (await session.execute(select(ConverterCoinSession).where(
            ConverterCoinSession.state != "CLOSED"
        ))).scalars().first()
        if intake or coins:
            raise HTTPException(status_code=409, detail="Reconcile retained cash and coin sessions first")

    machine_status = request.app.state.machine_status
    coin_controller = getattr(request.app.state, "coin_controller", None)
    bill_controller = getattr(request.app.state, "bill_controller", None) or getattr(
        getattr(request.app.state, "bill_acceptor", None), "_bill", None
    )
    if not coin_controller or not bill_controller:
        raise HTTPException(status_code=503, detail="Both controllers are required for recovery")
    try:
        await coin_controller.clear_emergency()
        await bill_controller.clear_emergency()
        await bill_controller.home()
        await coin_controller.security_lock()
    except Exception as exc:
        machine_status.update_security(tamper_active=True)
        await asyncio.gather(
            coin_controller.emergency_stop(), bill_controller.emergency_stop(),
            return_exceptions=True,
        )
        raise HTTPException(status_code=503, detail="Hardware recovery failed; lockdown remains active") from exc
    machine_status.update_security(tamper_active=False)
    orchestrator = getattr(request.app.state, "transaction_orchestrator", None)
    if orchestrator:
        orchestrator._has_accounting_fault = False

    return {"status": "success", "message": "Tamper recovery completed"}


class IntakeResolutionRequest(BaseModel):
    retained: bool
    denomination: str | None = None
    notes: str = Field(min_length=1, max_length=1000)


class CoinSessionResolutionRequest(BaseModel):
    counts: dict[str, StrictInt]
    notes: str = Field(min_length=1, max_length=1000)


async def _refresh_converter_claim(session, transaction_id):
    from sqlalchemy import select
    from app.models.db_models import TransactionRecord, ConverterIntakeOperation, ClaimRecord
    record = await session.get(TransactionRecord, transaction_id)
    uncertain = (await session.execute(select(ConverterIntakeOperation).where(
        ConverterIntakeOperation.transaction_id == transaction_id,
        ConverterIntakeOperation.state.in_(["PREPARED", "UNCERTAIN"]),
    ))).scalars().all()
    ambiguity = sum(op.value for op in uncertain)
    claims = (await session.execute(select(ClaimRecord).where(
        ClaimRecord.transaction_id == transaction_id, ClaimRecord.status != "RESOLVED",
    ))).scalars().all()
    for claim in claims:
        claim.amount = max(0, record.inserted_amount - record.dispensed_amount) + ambiguity
        claim.ambiguous_amount = ambiguity
        claim.status = "PROVISIONAL" if ambiguity else "OPEN" if claim.amount else "RESOLVED"
    meta = dict(record.converter_metadata or {})
    meta["revision"] = meta.get("revision", 0) + 1
    record.converter_metadata = meta


@router.get("/converter-reconciliation")
async def converter_reconciliation(request: Request, authorization: str | None = Header(default=None)):
    require_admin_session(request, authorization)
    from sqlalchemy import select
    from app.models.db_models import ConverterIntakeOperation, ConverterCoinSession
    async with request.app.state.db_session_factory() as session:
        bills = (await session.execute(select(ConverterIntakeOperation).where(
            ConverterIntakeOperation.state.in_(["PREPARED", "UNCERTAIN"])
        ))).scalars().all()
        coins = (await session.execute(select(ConverterCoinSession).where(
            ConverterCoinSession.state != "CLOSED"
        ))).scalars().all()
        return {
            "bills": [{"id": op.id, "transaction_id": op.transaction_id, "denomination": op.denomination, "value": op.value, "state": op.state} for op in bills],
            "coins": [{"sid": op.session_id, "transaction_id": op.transaction_id, "state": op.state,
                       "credited_counts": {str(d): getattr(op, f"cursor_php_{d}") for d in (1,5,10,20)}} for op in coins],
        }


@router.post("/converter-reconciliation/bills/{operation_id}")
async def reconcile_converter_bill(operation_id: str, body: IntakeResolutionRequest, request: Request,
                                   authorization: str | None = Header(default=None)):
    require_admin_session(request, authorization)
    from app.models.db_models import ConverterIntakeOperation, TransactionRecord
    orchestrator = request.app.state.transaction_orchestrator
    async with orchestrator._accounting_lock:
        async with request.app.state.db_session_factory() as session:
            op = await session.get(ConverterIntakeOperation, operation_id)
            if not op:
                raise HTTPException(status_code=404, detail="Intake operation not found")
            target = "RETAINED" if body.retained else "RETURNED"
            if op.state not in {"PREPARED", "UNCERTAIN", target}:
                raise HTTPException(status_code=409, detail="Intake outcome already resolved differently")
            if body.retained:
                if op.denomination == "UNKNOWN":
                    if body.denomination not in {"PHP_20", "PHP_50", "PHP_100", "PHP_200", "PHP_500", "PHP_1000"}:
                        raise HTTPException(status_code=422, detail="Identify the retained bill denomination")
                    op.denomination = body.denomination
                    op.value = int(body.denomination.split("_")[1])
                if not op.inventory_credited:
                    await request.app.state.inventory_service.adjust_in_session(
                        session, "BILL_STORAGE", op.denomination, 1,
                        reason="INTAKE_RECONCILIATION", reference_id=op.transaction_id,
                    )
                    op.inventory_credited = True
                if not op.transaction_credited:
                    record = await session.get(TransactionRecord, op.transaction_id)
                    record.inserted_amount += op.value
                    counts = dict(record.inserted_denominations or {})
                    counts[str(op.value)] = counts.get(str(op.value), 0) + 1
                    record.inserted_denominations = counts
                    op.transaction_credited = True
            op.state = target
            op.error_message = body.notes
            await session.flush()
            await _refresh_converter_claim(session, op.transaction_id)
            await session.commit()
        await request.app.state.inventory_service.refresh_runtime()
    return {"status": "OK", "operation_id": operation_id, "state": target}


@router.post("/converter-reconciliation/coins/{sid}")
async def reconcile_converter_coins(sid: int, body: CoinSessionResolutionRequest, request: Request,
                                    authorization: str | None = Header(default=None)):
    require_admin_session(request, authorization)
    from sqlalchemy import select
    from app.models.db_models import ConverterCoinSession, TransactionRecord
    if set(body.counts) != {"1", "5", "10", "20"} or any(type(c) is not int or not 0 <= c <= 65535 for c in body.counts.values()):
        raise HTTPException(status_code=422, detail="Supply nonnegative cumulative counts for all four denominations")
    orchestrator = request.app.state.transaction_orchestrator
    async with request.app.state.db_session_factory() as session:
        row = (await session.execute(select(ConverterCoinSession).where(ConverterCoinSession.session_id == sid))).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Coin session not found")
        transaction_id = row.transaction_id
        if any(body.counts[str(d)] < getattr(row, f"cursor_php_{d}") for d in (1,5,10,20)):
            raise HTTPException(status_code=409, detail="Observed counts cannot remove already credited cash")
    await orchestrator._apply_coin_counts(transaction_id, sid, {int(d): c for d, c in body.counts.items()}, closed=True)
    await request.app.state.coin_controller.coin_session_ack(sid)
    async with request.app.state.db_session_factory() as session:
        await _refresh_converter_claim(session, transaction_id)
        record = await session.get(TransactionRecord, transaction_id)
        meta = dict(record.converter_metadata or {})
        meta["coin_reconciliation"] = {"sid": sid, "notes": body.notes, "counts": body.counts}
        record.converter_metadata = meta
        await session.commit()
    return {"status": "OK", "sid": sid}


@router.get("/forex-audit")
async def forex_audit(request: Request, authorization: str | None = Header(default=None)):
    require_admin_session(request, authorization)
    return {"records": await request.app.state.claim_service.forex_legacy_audit()}


@router.post("/forex-claims/{ticket_id}/items/{item_id}/resolve")
async def resolve_forex_item(ticket_id: str, item_id: str, body: ResolveClaimRequest,
                             request: Request, authorization: str | None = Header(default=None)):
    admin = require_admin_session(request, authorization)
    try:
        return await request.app.state.claim_service.resolve_forex_item(ticket_id, item_id, admin.session_id, body.resolution_notes)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/forex-intakes")
async def forex_intakes(request: Request, authorization: str | None = Header(default=None)):
    require_admin_session(request, authorization)
    from sqlalchemy import select
    from app.models.db_models import ForexIntake
    async with request.app.state.db_session_factory() as session:
        rows = (await session.execute(select(ForexIntake).where(ForexIntake.state.in_(["PREPARED", "UNCERTAIN"])))).scalars().all()
        return {"items": [{"id": r.id, "transaction_id": r.transaction_id, "denomination": r.denomination, "value": r.value} for r in rows]}


@router.post("/forex-intakes/{operation_id}/reconcile")
async def reconcile_forex_intake(operation_id: str, body: IntakeResolutionRequest, request: Request,
                                authorization: str | None = Header(default=None)):
    admin = require_admin_session(request, authorization)
    try:
        return await request.app.state.forex_transaction_orchestrator.reconcile_intake(operation_id, body.retained, admin.session_id, body.notes)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
