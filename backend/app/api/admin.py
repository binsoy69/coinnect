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
