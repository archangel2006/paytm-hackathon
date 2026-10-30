from fastapi import APIRouter, Depends
from server.api.deps import get_repo
from server.db.repo import PlatformRepo

router = APIRouter(tags=["scoreboard"])

@router.get("/scoreboard")
def get_scoreboard(repo: PlatformRepo = Depends(get_repo)):
    return repo.get_scoreboard()

