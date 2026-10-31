"""
Phone simulator channel.

Behaves identically to WhatsApp from the Agent's perspective: it builds
``IncomingEvent`` objects and passes them to ``on_incoming``.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Callable

from agent.domain.enums import Channel, DocType
from agent.ports import AgentResult, Clock, IncomingEvent

from integrations import settings
from integrations.phone import mask
from integrations.ports import Store

logger = logging.getLogger(__name__)

_store: Store | None = None
_on_incoming: Callable[[IncomingEvent], AgentResult] | None = None
_clock: Clock | None = None


def configure(
    *,
    store: Store,
    on_incoming: Callable[[IncomingEvent], AgentResult],
    clock: Clock,
) -> None:
    global _store, _on_incoming, _clock
    _store = store
    _on_incoming = on_incoming
    _clock = clock


def _get_deps():
    assert _store and _on_incoming and _clock, "simulator not configured"
    return _store, _on_incoming, _clock


# ── Public API ───────────────────────────────────────────────────────────────

def receive_text(merchant_id: str, text: str) -> AgentResult:
    """Simulate a merchant sending a text message."""
    store, on_incoming, clock = _get_deps()

    merchant = store.get_merchant(merchant_id)
    if merchant is None:
        return AgentResult(success=False, error=f"Unknown merchant: {merchant_id}")

    event_id = f"sim-{uuid.uuid4().hex[:12]}"

    event = IncomingEvent(
        event_id=event_id,
        merchant_id=merchant_id,
        phone_e164=merchant.phone_e164,
        channel=Channel.SIMULATOR,
        kind="text",
        text=text,
        received_at=clock.now(),
    )

    logger.info(
        "simulator.receive_text merchant=%s phone=%s event_id=%s",
        merchant_id,
        mask(merchant.phone_e164),
        event_id,
    )

    from integrations.router import use_outbound_channel

    with use_outbound_channel(Channel.SIMULATOR):
        result = on_incoming(event)
    if not store.already_processed(event_id):
        store.save_message(
            merchant_id=merchant_id,
            direction="in",
            channel="simulator",
            kind="text",
            text=text,
        )
    return result


def receive_media(
    merchant_id: str,
    file_bytes: bytes,
    filename: str,
    mime: str,
    document_type: DocType = DocType.PAN,
) -> AgentResult:
    """Simulate a merchant sending a media file (image or document)."""
    store, on_incoming, clock = _get_deps()

    merchant = store.get_merchant(merchant_id)
    if merchant is None:
        return AgentResult(success=False, error=f"Unknown merchant: {merchant_id}")

    # Validate MIME
    if mime not in settings.ALLOWED_MIMES:
        return AgentResult(
            success=False,
            error=f"Unsupported MIME type: {mime}",
        )

    # Validate size
    max_bytes = int(settings.MAX_UPLOAD_MB * 1024 * 1024)
    if len(file_bytes) > max_bytes:
        return AgentResult(
            success=False,
            error=f"File too large: {len(file_bytes)} bytes (max {max_bytes})",
        )

    event_id = f"sim-{uuid.uuid4().hex[:12]}"

    # Save the file
    upload_dir = os.path.join(settings.UPLOAD_DIR, merchant_id)
    os.makedirs(upload_dir, exist_ok=True)
    safe_filename = os.path.basename(filename.replace("\\", "/"))[:120]
    ext = safe_filename.rsplit(".", 1)[-1] if "." in safe_filename else "bin"
    save_name = safe_filename or f"upload.{ext}"
    save_path = os.path.join(upload_dir, f"{event_id}_{save_name}")
    with open(save_path, "wb") as f:
        f.write(file_bytes)

    event = IncomingEvent(
        event_id=event_id,
        merchant_id=merchant_id,
        phone_e164=merchant.phone_e164,
        channel=Channel.SIMULATOR,
        kind="media",
        text=filename,
        media_path=save_path,
        mime_type=mime,
        document_type=document_type,
        received_at=clock.now(),
    )

    logger.info(
        "simulator.receive_media merchant=%s file=%s event_id=%s",
        merchant_id,
        filename,
        event_id,
    )

    from integrations.router import use_outbound_channel

    with use_outbound_channel(Channel.SIMULATOR):
        result = on_incoming(event)
    if not store.already_processed(event_id):
        store.save_message(
            merchant_id=merchant_id,
            direction="in",
            channel="simulator",
            kind="media",
            text=filename,
        )
    return result
