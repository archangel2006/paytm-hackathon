"""
Parse a WhatsApp Cloud API webhook payload into simple dataclass objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ParsedEvent:
    """A single parsed incoming event from a WhatsApp webhook payload."""
    event_id: str
    sender: str  # phone number without '+'
    kind: str    # "text", "media", "audio", "unsupported", "status"
    text: str | None = None
    media_id: str | None = None
    media_mime: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict = field(default_factory=dict)


def parse_payload(payload: dict) -> list[ParsedEvent]:
    """Extract all events from a WhatsApp webhook payload.

    Returns a list because a single webhook POST can contain multiple
    entries / changes / messages.
    """
    events: list[ParsedEvent] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})

            # Handle delivery statuses
            for status in value.get("statuses", []):
                events.append(ParsedEvent(
                    event_id=status.get("id", ""),
                    sender="",
                    kind="status",
                    raw=status,
                ))

            # Handle messages
            for msg in value.get("messages", []):
                event = _parse_message(msg)
                if event:
                    events.append(event)

    return events


def _parse_message(msg: dict) -> ParsedEvent | None:
    """Parse a single message object from the webhook."""
    msg_type: str = msg.get("type", "")
    sender: str = msg.get("from", "")
    msg_id: str = msg.get("id", "")

    # Parse timestamp
    ts_str = msg.get("timestamp", "")
    try:
        ts = datetime.fromtimestamp(int(ts_str), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        ts = datetime.now(timezone.utc)

    if msg_type == "text":
        return ParsedEvent(
            event_id=msg_id,
            sender=sender,
            kind="text",
            text=msg.get("text", {}).get("body"),
            timestamp=ts,
            raw=msg,
        )

    if msg_type == "image":
        img = msg.get("image", {})
        return ParsedEvent(
            event_id=msg_id,
            sender=sender,
            kind="media",
            media_id=img.get("id"),
            media_mime=img.get("mime_type"),
            timestamp=ts,
            raw=msg,
        )

    if msg_type == "audio":
        audio = msg.get("audio", {})
        return ParsedEvent(
            event_id=msg_id,
            sender=sender,
            kind="audio",
            media_id=audio.get("id"),
            media_mime=audio.get("mime_type"),
            timestamp=ts,
            raw=msg,
        )

    if msg_type in ("interactive", "button"):
        # Treat interactive / button replies as text
        text = None
        if msg_type == "interactive":
            ir = msg.get("interactive", {})
            if ir.get("type") == "button_reply":
                text = ir.get("button_reply", {}).get("title")
            elif ir.get("type") == "list_reply":
                text = ir.get("list_reply", {}).get("title")
        elif msg_type == "button":
            text = msg.get("button", {}).get("text")

        return ParsedEvent(
            event_id=msg_id,
            sender=sender,
            kind="text",
            text=text,
            timestamp=ts,
            raw=msg,
        )

    # Unsupported type
    return ParsedEvent(
        event_id=msg_id,
        sender=sender,
        kind="unsupported",
        timestamp=ts,
        raw=msg,
    )
