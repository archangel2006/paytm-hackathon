from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Body
from pydantic import BaseModel
import agent
from server.api.deps import get_repo, APIError, require_staff_access
from server.db.models import AgentAction
from server.db.repo import PlatformRepo

router = APIRouter(
    prefix="/actions",
    tags=["actions"],
    dependencies=[Depends(require_staff_access)],
)

class ApproveRequest(BaseModel):
    by: str = "manager"
    edits: Optional[Dict[str, Any]] = None

class RejectRequest(BaseModel):
    by: str = "manager"
    reason_code: str = "unacceptable_terms"

class EditRequest(BaseModel):
    by: str = "manager"
    edits: Dict[str, Any]


def _pending_action(repo: PlatformRepo, action_id: str) -> AgentAction:
    action = repo.db.query(AgentAction).filter(AgentAction.id == action_id).first()
    if not action:
        raise APIError("NOT_FOUND", f"Action {action_id} not found", status_code=404)
    if action.status != "pending_approval":
        raise APIError(
            "INVALID_ACTION_STATUS",
            f"Action {action_id} is not awaiting approval.",
            status_code=409,
        )
    return action


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
def approve_action(
    action_id: str,
    req: ApproveRequest,
    repo: PlatformRepo = Depends(get_repo),
    actor: str = Depends(require_staff_access),
):
    action = _pending_action(repo, action_id)
    result = agent.approve_action(action_id, by=actor, edits=req.edits)
    updated = repo.db.query(AgentAction).filter(AgentAction.id == action_id).first()
    return {
        "status": "approved",
        "action_id": action.id,
        "merchant_id": result.merchant_id,
        "reply_sent": result.reply_sent,
        "executed_at": updated.executed_at.isoformat() if updated and updated.executed_at else None,
    }

@router.post("/{action_id}/reject")
def reject_action(
    action_id: str,
    req: RejectRequest,
    repo: PlatformRepo = Depends(get_repo),
    actor: str = Depends(require_staff_access),
):
    _pending_action(repo, action_id)
    result = agent.reject_action(action_id, by=actor, reason_code=req.reason_code)
    return {
        "status": "rejected",
        "action_id": action_id,
        "merchant_id": result.merchant_id,
        "rejection_reason": req.reason_code
    }

@router.post("/{action_id}/edit")
def edit_action(
    action_id: str,
    req: EditRequest,
    repo: PlatformRepo = Depends(get_repo),
    actor: str = Depends(require_staff_access),
):
    action = _pending_action(repo, action_id)
    result = agent.approve_action(action_id, by=actor, edits=req.edits)
    updated = repo.db.query(AgentAction).filter(AgentAction.id == action_id).first()
    return {
        "status": "approved_with_edits",
        "action_id": action.id,
        "merchant_id": result.merchant_id,
        "reply_sent": result.reply_sent,
        "edits": req.edits,
        "executed_at": updated.executed_at.isoformat() if updated and updated.executed_at else None,
    }
