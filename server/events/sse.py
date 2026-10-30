import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional
from sqlalchemy.orm import Session
from server.db.models import Event
from server.events.bus import event_bus

async def event_generator(
    db: Session,
    last_event_id: Optional[int] = None
) -> AsyncGenerator[str, None]:
    """
    Yields SSE formatted data with replay support and 15s keep-alive heartbeat comments.
    """
    # 1. Replay missed events if Last-Event-ID is provided
    if last_event_id is not None:
        missed = db.query(Event).filter(Event.id > last_event_id).order_by(Event.id.asc()).all()
        for ev in missed:
            yield f"id: {ev.id}\nevent: {ev.type}\ndata: {json.dumps(ev.data or {})}\n\n"

    # 2. Subscribe to live events
    queue = event_bus.subscribe()
    try:
        while True:
            try:
                # Wait for next event or 15 seconds timeout for heartbeat
                item = await asyncio.wait_for(queue.get(), timeout=15.0)
                event_id = item["id"]
                event_type = item["type"]
                event_data = json.dumps(item.get("data") or {})
                yield f"id: {event_id}\nevent: {event_type}\ndata: {event_data}\n\n"
            except asyncio.TimeoutError:
                # 15s heartbeat comment
                yield ": heartbeat\n\n"
    finally:
        event_bus.unsubscribe(queue)

