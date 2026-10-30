import hmac
from typing import Generator
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from server.db.session import get_db
from server.db.repo import PlatformRepo
from server.settings import settings

def get_repo(db: Session = Depends(get_db)) -> PlatformRepo:
    return PlatformRepo(db)

class APIError(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict = None):
        super().__init__(
            status_code=status_code,
            detail={"error": {"code": code, "message": message, "details": details or {}}}
        )


def require_staff_access(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> str:
    """Authenticate staff API access, allowing only an isolated local demo fallback."""
    configured_key = settings.SAATHI_API_KEY.strip()
    supplied_key = x_api_key
    if supplied_key is None and authorization and authorization.startswith("Bearer "):
        supplied_key = authorization[7:].strip()

    if configured_key:
        if supplied_key and hmac.compare_digest(supplied_key, configured_key):
            return "api-key"
        raise APIError("UNAUTHORIZED", "Valid staff API credentials are required.", status_code=401)

    client_host = request.client.host if request.client else None
    if client_host in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return "local-demo"

    raise APIError(
        "AUTH_NOT_CONFIGURED",
        "Staff API authentication is not configured.",
        status_code=503,
    )
