from typing import Optional
from fastapi import APIRouter, Depends, Query
from server.api.deps import get_repo
from server.db.repo import PlatformRepo

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("")
def list_audit_logs(
    merchant_id: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    repo: PlatformRepo = Depends(get_repo)
):
    logs = repo.list_audit_logs(merchant_id=merchant_id, actor=actor, event_type=event_type, limit=limit)
    return [
        {
            "id": l.id,
            "actor": l.actor,
            "event_type": l.event_type,
            "merchant_id": l.merchant_id,
            "payload": l.payload or {},
            "created_at": l.created_at.isoformat()
        }
        for l in logs
    ]

