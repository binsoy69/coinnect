from fastapi import APIRouter, Request

router = APIRouter(tags=["status"])


@router.get("/status")
async def get_status(request: Request):
    status = request.app.state.machine_status
    return status.snapshot().model_dump(mode="json")
