from fastapi import APIRouter, Request

router = APIRouter(tags=["status"])


@router.get("/status")
async def get_status(request: Request):
    status = request.app.state.machine_status
    return status.snapshot().model_dump(mode="json")


@router.post("/status/startup-checks/retry")
async def retry_startup_checks(request: Request):
    import asyncio
    startup_check_service = request.app.state.startup_check_service
    asyncio.create_task(startup_check_service.run_checks())
    return {"status": "triggered"}

