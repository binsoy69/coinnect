"""Inventory REST API endpoints for machine consumables."""

import logging

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["inventory"])


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
