"""
WhatsApp webhook – FastAPI ``APIRouter`` with verify (GET) and receive (POST).

Mounted by ``server/main.py`` at ``/webhooks/whatsapp``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, Query, Request, Response

from integrations.whatsapp import security, parser
from integrations import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["whatsapp-webhook"])


# ── GET: Meta webhook verification ───────────────────────────────────────────

@router.get("/webhooks/whatsapp")
async def verify_webhook(
    response: Response,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
) -> Any:
    """Verify the webhook with Meta."""
    if (
        hub_mode == "subscribe"
        and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN
    ):
        logger.info("Webhook verified successfully")
        return Response(content=hub_challenge or "", media_type="text/plain")

    logger.warning("Webhook verification failed: mode=%s", hub_mode)
    return Response(content="Forbidden", status_code=403)


# ── POST: incoming messages ──────────────────────────────────────────────────

@router.post("/webhooks/whatsapp")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
) -> Response:
    """Receive and enqueue WhatsApp messages. Returns 200 immediately."""
    body = await request.body()

    # Verify HMAC signature
    if not security.verify_signature(body, x_hub_signature_256):
        logger.warning("Webhook signature verification failed")
        return Response(content="Unauthorized", status_code=401)

    # Enqueue processing in background
    background_tasks.add_task(_process_payload, body)

    return Response(content="OK", status_code=200)


async def _process_payload(raw_body: bytes) -> None:
    """Parse the webhook payload and dispatch to the agent."""
    import json

    from integrations import get_on_incoming, get_store
    from integrations.phone import normalize, mask

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("Failed to decode webhook JSON")
        return

    store = get_store()

    events = parser.parse_payload(payload)
    for parsed in events:
        if parsed.kind == "status":
            # Delivery status – log and skip
            store.write_audit(
                actor="whatsapp",
                event_type="delivery_status",
                merchant_id=None,
                payload=parsed.raw,
            )
            continue

        # Deduplicate
        if store.already_processed(parsed.event_id):
            logger.info("Duplicate event_id=%s, skipping", parsed.event_id)
            continue

        # Normalise phone
        try:
            phone = normalize("+" + parsed.sender)
        except ValueError:
            logger.warning("Bad phone number: %s", parsed.sender)
            continue

        # Download media if needed
        media_path = None
        media_mime = None
        if parsed.media_id:
            from integrations.whatsapp.media import download_media
            media_path, media_mime = await download_media(
                media_id=parsed.media_id,
                mime_type=parsed.media_mime or "application/octet-stream",
                merchant_phone=phone,
                event_id=parsed.event_id,
            )

        # Look up merchant
        merchant = store.get_merchant_by_phone(phone)
        merchant_id = merchant.id if merchant else None

        if parsed.kind == "unsupported":
            from agent.ports import OutgoingMessage
            from agent.domain.enums import Channel, Language
            from integrations.router import send_message

            if merchant is not None:
                send_message(OutgoingMessage(
                    merchant_id=merchant.id,
                    phone_e164=phone,
                    channel=Channel.WHATSAPP,
                    text="Please send a text message or a clear photo so I can help.",
                    template_name="saathi_followup",
                    language=Language.ENGLISH,
                ))
            store.write_audit(
                actor="whatsapp",
                event_type="unsupported_message",
                merchant_id=merchant_id,
                payload={"type": parsed.raw.get("type")},
            )
            continue

        from agent.ports import IncomingEvent
        from agent.domain.enums import Channel

        event = IncomingEvent(
            event_id=parsed.event_id,
            merchant_id=merchant_id,
            phone_e164=phone,
            channel=Channel.WHATSAPP,
            kind=parsed.kind,
            text=parsed.text,
            media_path=media_path,
            mime_type=media_mime,
            received_at=parsed.timestamp,
        )

        logger.info(
            "Processing event_id=%s phone=%s kind=%s",
            parsed.event_id,
            mask(phone),
            parsed.kind,
        )

        on_incoming = get_on_incoming()
        try:
            result = on_incoming(event)
            logger.info(
                "Agent result for event_id=%s: success=%s reply_sent=%s action=%s",
                parsed.event_id,
                result.success,
                result.reply_sent,
                result.actions[0].action_type.value if result.actions else None,
            )
        except Exception:
            logger.exception("Agent failed for event_id=%s", parsed.event_id)
