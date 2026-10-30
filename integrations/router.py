"""
Outbound message router.

``send_message(msg)`` is the single entry-point used by the agent's
``send_whatsapp`` tool.  It picks the right channel (simulator or WhatsApp),
decides between free-text and template, handles retries, and always returns a
``SendResult`` – never raises.
"""

from __future__ import annotations

import logging
from datetime import timedelta, timezone

from agent.domain.enums import Channel
from agent.ports import OutgoingMessage, SendResult

from integrations import settings
from integrations.ports import Store

logger = logging.getLogger(__name__)

# Module-level dependencies – set by configure()
_store: Store | None = None
_clock = None  # agent.ports.Clock


def configure(*, store: Store, clock) -> None:
    global _store, _clock
    _store = store
    _clock = clock


def _get_store() -> Store:
    assert _store is not None, "router not configured"
    return _store


def _get_clock():
    assert _clock is not None, "router not configured"
    return _clock


def send_message(msg: OutgoingMessage) -> SendResult:
    """Route an outgoing message to the correct channel.

    Never raises – always returns a ``SendResult``.
    """
    try:
        if msg.channel == Channel.SIMULATOR:
            return _send_simulator(msg)
        elif msg.channel == Channel.WHATSAPP:
            return _send_whatsapp(msg)
        else:
            return SendResult(ok=False, error_code="UNKNOWN_CHANNEL",
                              error_detail=f"Unsupported channel: {msg.channel}")
    except Exception as exc:
        logger.exception("router.send_message failed")
        return SendResult(ok=False, error_code="ROUTER_ERROR", error_detail=str(exc))


# ── Simulator path ───────────────────────────────────────────────────────────

def _send_simulator(msg: OutgoingMessage) -> SendResult:
    store = _get_store()
    text = msg.text or f"[template:{msg.template_name}]"
    store.save_message(
        merchant_id=msg.merchant_id,
        direction="outbound",
        channel="simulator",
        kind="text",
        text=text,
    )
    store.publish_event(
        type="message.new",
        merchant_id=msg.merchant_id,
        data={"direction": "outbound", "channel": "simulator", "text": text},
    )
    return SendResult(ok=True, provider_message_id=None)


# ── WhatsApp path ────────────────────────────────────────────────────────────

def _send_whatsapp(msg: OutgoingMessage) -> SendResult:
    store = _get_store()
    clock = _get_clock()

    # Check 24-hour window
    last_inbound = store.last_inbound_at(msg.merchant_id)
    now = clock.now()
    if last_inbound is not None and last_inbound.tzinfo is None:
        last_inbound = last_inbound.replace(tzinfo=timezone.utc)
    window_open = (
        last_inbound is not None
        and (now - last_inbound) < timedelta(seconds=settings.WINDOW_SECONDS)
    )

    if window_open and msg.text:
        # Send free text
        result = _wa_send_text(msg)
    elif msg.template_name:
        # Send template
        result = _wa_send_template(msg)
    elif not window_open and not msg.template_name:
        return SendResult(
            ok=False,
            error_code="WINDOW_CLOSED",
            error_detail="24-hour window closed and no template_name provided.",
        )
    else:
        result = _wa_send_text(msg)

    if not result.ok:
        logger.warning(
            "WhatsApp reply not sent merchant_id=%s code=%s detail=%s",
            msg.merchant_id,
            result.error_code,
            result.error_detail,
        )
    if result.ok:
        store.save_message(
            merchant_id=msg.merchant_id,
            direction="outbound",
            channel="whatsapp",
            kind="template" if msg.template_name and not window_open else "text",
            text=msg.text or f"[template:{msg.template_name}]",
            provider_message_id=result.provider_message_id,
        )
    return result


def _wa_send_text(msg: OutgoingMessage) -> SendResult:
    """Send a free-text WhatsApp message via Graph API with retries."""
    from integrations.whatsapp.client import send_text
    return send_text(to=msg.phone_e164, body=msg.text or "")


def _wa_send_template(msg: OutgoingMessage) -> SendResult:
    """Send a template WhatsApp message via Graph API with retries."""
    from integrations.whatsapp.client import send_template
    lang_code = settings.TEMPLATES.get(msg.template_name or "", "en")
    return send_template(
        to=msg.phone_e164,
        template_name=msg.template_name or "",
        language_code=lang_code,
        params=msg.template_params,
    )
