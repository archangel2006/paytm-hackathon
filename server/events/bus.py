import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session
from server.db.models import Event
from server.db.session import SessionLocal

class EventBus:
    def __init__(self):
        self._subscribers: List[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def publish(
        self,
        event_type: str,
        merchant_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ) -> Event:
        payload = data or {}
        event_record = Event(
            type=event_type,
            merchant_id=merchant_id,
            data=payload,
            created_at=datetime.now(timezone.utc)
        )

        owns_session = False
        if db is None:
            db = SessionLocal()
            owns_session = True

        try:
            db.add(event_record)
            db.commit()
            db.refresh(event_record)
        finally:
            if owns_session:
                db.close()

        # Fan out to connected in-memory SSE queues
        event_msg = {
            "id": event_record.id,
            "type": event_record.type,
            "merchant_id": event_record.merchant_id,
            "data": event_record.data,
            "created_at": event_record.created_at.isoformat()
        }

        for q in list(self._subscribers):
            try:
                q.put_nowait(event_msg)
            except Exception:
                pass

        return event_record

# Global event bus instance
event_bus = EventBus()

