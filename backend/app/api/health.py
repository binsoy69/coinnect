from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request):
    status = request.app.state.machine_status
    snapshot = status.snapshot()
    return {
        "status": "ok",
        "bill_device": snapshot.bill_device.connection.value,
        "coin_device": snapshot.coin_device.connection.value,
    }
