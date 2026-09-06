"""Local customer transport and session authorization; webhooks remain separate."""
import hashlib
import ipaddress
from datetime import datetime
from fastapi import HTTPException, Request
from app.models.db_models import KioskSession, EWalletTransactionRecord


def require_local(request):
    host = request.client.host if request.client else ""
    try:
        local = ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = host in {"localhost", "testclient"}
    if not local:
        raise HTTPException(403, "Customer APIs are local to the kiosk")
    origin = request.headers.get("origin")
    settings = request.app.state.settings
    allowed = {o.strip() for o in settings.cors_origins.split(",")}
    if request.url.hostname in {"localhost", "127.0.0.1", "::1"}:
        allowed.add(f"{request.url.scheme}://{request.headers.get('host', '')}")
    if origin and origin not in allowed:
        raise HTTPException(403, "Untrusted browser origin")


async def wallet_access(request: Request):
    if request.url.path.endswith("/webhook"):
        return
    require_local(request)
    if request.url.path.endswith("/session"):
        return
    token = request.headers.get("X-Kiosk-Session", "")
    session_id = hashlib.sha256(token.encode()).hexdigest()
    factory = request.app.state.db_session_factory
    async with factory() as session:
        row = await session.get(KioskSession, session_id)
        if not token or not row or row.expires_at < datetime.utcnow():
            raise HTTPException(401, "Customer session expired")
        tx_id = request.path_params.get("transaction_id")
        if tx_id:
            transaction = await session.get(EWalletTransactionRecord, tx_id)
            if transaction is None or transaction.session_id != session_id:
                raise HTTPException(404, "Transaction not found")
    request.state.kiosk_session = session_id
