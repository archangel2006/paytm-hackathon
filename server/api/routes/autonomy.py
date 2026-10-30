from fastapi import APIRouter, Depends
from pydantic import BaseModel
from server.api.deps import get_repo, APIError
from server.db.repo import PlatformRepo

router = APIRouter(prefix="/autonomy", tags=["autonomy"])

class UpdateAutonomyRequest(BaseModel):
    level: str  # L1, L2, L3
    by: str = "manager"

@router.get("")
def get_autonomy_settings(repo: PlatformRepo = Depends(get_repo)):
    configs = repo.list_autonomy_config()
    return {
        c.action_type: {
            "level": c.level,
            "updated_by": c.updated_by,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None
        }
        for c in configs
    }

@router.put("/{action_type}")
def update_autonomy_level(action_type: str, req: UpdateAutonomyRequest, repo: PlatformRepo = Depends(get_repo)):
    if req.level not in ("L1", "L2", "L3"):
        raise APIError("VALIDATION_ERROR", f"Invalid autonomy level {req.level}. Must be L1, L2, or L3.", status_code=400)

    cfg = repo.set_autonomy_level(action_type=action_type, level=req.level, by=req.by)
    return {
        "action_type": cfg.action_type,
        "level": cfg.level,
        "updated_by": cfg.updated_by,
        "updated_at": cfg.updated_at.isoformat()
    }

