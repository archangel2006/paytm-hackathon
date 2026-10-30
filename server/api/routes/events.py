from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from server.db.session import get_db
from server.db.models import Event

router = APIRouter(tags=["events"])

@router.get("/events")
def get_polling_events(
    since: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    evs = db.query(Event).filter(Event.id > since).order_by(Event.id.asc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "type": e.type,
            "merchant_id": e.merchant_id,
            "data": e.data or {},
            "created_at": e.created_at.isoformat()
        }
        for e in evs
    ]

