from typing import Generator
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from server.db.session import get_db
from server.db.repo import PlatformRepo

def get_repo(db: Session = Depends(get_db)) -> PlatformRepo:
    return PlatformRepo(db)

class APIError(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict = None):
        super().__init__(
            status_code=status_code,
            detail={"error": {"code": code, "message": message, "details": details or {}}}
        )

