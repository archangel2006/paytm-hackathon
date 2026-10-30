from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from server.api.deps import get_repo, APIError
from server.db.repo import PlatformRepo

router = APIRouter(prefix="/handoffs", tags=["handoffs"])

class ResolveRequest(BaseModel):
    note: str

@router.get("")
def list_handoffs(
    target: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    repo: PlatformRepo = Depends(get_repo)
):
    items = repo.list_handoffs(target=target, status=status)
    res = []
    for h in items:
        m = repo.get_merchant(h.merchant_id)
        shop_name = m.shop_name if m else "Unknown Shop"
        res.append({
            "id": h.id,
            "merchant_id": h.merchant_id,
            "shop_name": shop_name,
            "target": h.target,
            "reason": h.reason,
            "summary": h.summary or {},
            "status": h.status,
            "resolution_note": h.resolution_note,
            "created_at": h.created_at.isoformat()
        })
    return res

@router.post("/{handoff_id}/resolve")
def resolve_handoff(handoff_id: str, req: ResolveRequest, repo: PlatformRepo = Depends(get_repo)):
    handoff = repo.resolve_handoff(handoff_id, req.note)
    if not handoff:
        raise APIError("NOT_FOUND", f"Handoff {handoff_id} not found", status_code=404)
    return {
        "status": "resolved",
        "handoff_id": handoff.id,
        "resolution_note": handoff.resolution_note
    }

