from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Body
from pydantic import BaseModel
from server.api.deps import get_repo, APIError
from server.db.repo import PlatformRepo

router = APIRouter(prefix="/actions", tags=["actions"])

class ApproveRequest(BaseModel):
    by: str = "manager"
    edits: Optional[Dict[str, Any]] = None

class RejectRequest(BaseModel):
    by: str = "manager"
    reason_code: str = "unacceptable_terms"

class EditRequest(BaseModel):
    by: str = "manager"
    edits: Dict[str, Any]

@router.get("")
def list_actions(
    status: Optional[str] = Query(None),
    merchant_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    repo: PlatformRepo = Depends(get_repo)
):
    actions = repo.list_actions(status=status, merchant_id=merchant_id, limit=limit)
    res = []
    for a in actions:
        m = repo.get_merchant(a.merchant_id)
        shop_name = m.shop_name if m else "Unknown Shop"
        res.append({
            "id": a.id,
            "merchant_id": a.merchant_id,
            "shop_name": shop_name,
            "action_type": a.action_type,
            "autonomy_level": a.autonomy_level,
            "status": a.status,
            "reasoning": a.reasoning,
            "confidence": a.confidence,
            "source": a.source,
            "guardrail_notes": a.guardrail_notes or [],
            "created_at": a.created_at.isoformat(),
            "executed_at": a.executed_at.isoformat() if a.executed_at else None
        })
    return res

@router.post("/{action_id}/approve")
def approve_action(action_id: str, req: ApproveRequest, repo: PlatformRepo = Depends(get_repo)):
    act = repo.db.query(repo.db.models.AgentAction if hasattr(repo.db, 'models') else None).filter_by(id=action_id).first() if False else None
    action = repo.update_action_status(action_id=action_id, status="approved", approved_by=req.by)
    if not action:
        raise APIError("NOT_FOUND", f"Action {action_id} not found", status_code=404)

    # If action was OFFER_DISCOUNT or similar, execute the side effect
    m = repo.get_merchant(action.merchant_id)
    return {
        "status": "approved",
        "action_id": action.id,
        "merchant_id": action.merchant_id,
        "executed_at": action.executed_at.isoformat() if action.executed_at else None
    }

@router.post("/{action_id}/reject")
def reject_action(action_id: str, req: RejectRequest, repo: PlatformRepo = Depends(get_repo)):
    action = repo.update_action_status(action_id=action_id, status="rejected", approved_by=req.by, rejection_reason=req.reason_code)
    if not action:
        raise APIError("NOT_FOUND", f"Action {action_id} not found", status_code=404)
    return {
        "status": "rejected",
        "action_id": action.id,
        "rejection_reason": req.reason_code
    }

@router.post("/{action_id}/edit")
def edit_action(action_id: str, req: EditRequest, repo: PlatformRepo = Depends(get_repo)):
    action = repo.update_action_status(action_id=action_id, status="approved", approved_by=req.by)
    if not action:
        raise APIError("NOT_FOUND", f"Action {action_id} not found", status_code=404)
    return {
        "status": "approved_with_edits",
        "action_id": action.id,
        "edits": req.edits
    }

