from typing import Optional
from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from server.db.session import get_db
from server.events.sse import event_generator

router = APIRouter(tags=["stream"])

@router.get("/stream")
async def get_live_stream(
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    db: Session = Depends(get_db)
):
    lid = None
    if last_event_id:
        try:
            lid = int(last_event_id)
        except ValueError:
            pass

    return StreamingResponse(
        event_generator(db, last_event_id=lid),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

