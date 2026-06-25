"""Inventory REST API endpoints for machine consumables."""

import logging
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.admin import require_admin_session
from app.services.inventory_service import InventoryUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["inventory"])


class InventoryBatchUpdate(BaseModel):
    updates: list[InventoryUpdate] = Field(min_length=1)
    reason: Literal["REFILL", "PHYSICAL_COUNT", "CORRECTION"]
    note: str | None = Field(default=None, max_length=500)


@router.get("/")
async def get_inventory(request: Request):
    """Get full inventory state with alerts."""
    machine_status = request.app.state.machine_status
    snapshot = machine_status.snapshot()
    return {
        "bill_storage_counts": snapshot.consumables.bill_storage_counts,
        "bill_dispenser_counts": snapshot.consumables.bill_dispenser_counts,
        "coin_counts": snapshot.consumables.coin_counts,
        "alerts": snapshot.consumables.alerts,
    }


@router.get("/acceptable-denominations")
async def get_acceptable_denominations(request: Request):
    """Get denominations that can still be accepted (storage not full)."""
    machine_status = request.app.state.machine_status
    return {
        "denominations": machine_status.get_acceptable_denominations(),
    }


@router.put("/")
async def update_inventory(
    body: InventoryBatchUpdate,
    request: Request,
    authorization: str | None = Header(default=None),
):
    admin = require_admin_session(request, authorization)
    try:
        await request.app.state.inventory_service.apply_admin_updates(
            updates=body.updates,
            reason=body.reason,
            note=body.note,
            session_id=admin.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    snapshot = request.app.state.machine_status.snapshot().consumables
    return {
        "bill_storage_counts": snapshot.bill_storage_counts,
        "bill_dispenser_counts": snapshot.bill_dispenser_counts,
        "coin_counts": snapshot.coin_counts,
        "alerts": snapshot.alerts,
    }


@router.get("/adjustments")
async def get_inventory_adjustments(
    request: Request,
    authorization: str | None = Header(default=None),
    source: Literal["ADMIN", "SYSTEM"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    require_admin_session(request, authorization)
    rows = await request.app.state.inventory_service.list_adjustments(
        source=source, limit=limit
    )
    return {
        "adjustments": [
            {
                "id": row.id,
                "location": row.location,
                "denomination": row.denomination,
                "old_count": row.old_count,
                "new_count": row.new_count,
                "delta": row.delta,
                "reason": row.reason,
                "source": row.source,
                "note": row.note,
                "session_id": row.session_id,
                "reference_id": row.reference_id,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }
