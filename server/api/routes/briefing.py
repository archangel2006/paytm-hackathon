from fastapi import APIRouter, Depends
from server.api.deps import get_repo
from server.db.repo import PlatformRepo

router = APIRouter(tags=["briefing"])

@router.get("/briefing")
def get_morning_briefing(repo: PlatformRepo = Depends(get_repo)):
    return repo.get_briefing()

