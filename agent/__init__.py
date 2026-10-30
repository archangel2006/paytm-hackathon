from __future__ import annotations

from typing import Any

from agent.domain.enums import Channel, Language
from agent.ports import AgentResult, IncomingEvent, OutgoingMessage

_store: Any = None
_channel: Any = None
_clock: Any = None


def configure(store: Any, channel: Any, documents: Any, clock: Any, settings: Any = None) -> None:
    global _store, _channel, _clock
    _store, _channel, _clock = store, channel, clock


def handle_incoming(event: IncomingEvent) -> AgentResult:
    if _store is None or _channel is None:
        return AgentResult(success=False, error="agent is not configured")
    merchant = _store.get_merchant_by_phone(event.phone_e164)
    if merchant is None:
        merchant = _store.create_lead(event.phone_e164, event.channel, Language.ENGLISH)
    text = (event.text or "").lower()
    if "fee" in text or "charge" in text or "rental" in text:
        reply = "The Soundbox rental is Rs 99 per month. UPI payments have no extra charge."
        action = "ANSWER_QUERY"
    elif "settlement" in text:
        reply = "Your settlement is expected on the next working day. I can ask the field team to check it."
        action = "EXPLAIN_SETTLEMENT"
    elif event.kind == "media":
        reply = "I received your document. I will run a document pre-check and tell you if anything needs to be clearer."
        action = "VALIDATE_KYC_DOC"
    elif "visit" in text or "kal" in text:
        reply = "Thanks. I have noted your visit request. An executive will confirm the available slot."
        action = "SCHEDULE_VISIT"
    else:
        reply = "Namaste! I am Saathi. I can help with Soundbox fees, settlements, documents, and visit scheduling."
        action = "SEND_INTRO"
    result = _channel.send_message(OutgoingMessage(
        merchant_id=merchant.id,
        phone_e164=merchant.phone_e164,
        channel=event.channel,
        text=reply,
        language=merchant.language,
    ))
    _store.save_message(merchant.id, "inbound", event.channel.value, event.kind, event.text)
    _store.write_audit("agent", "action_executed", merchant.id, {"action": action, "send_ok": result.ok})
    return AgentResult(merchant_id=merchant.id, action_taken=action, reply_text=reply, success=result.ok, error=result.error_detail)


def handle_timer(merchant_id: str, reason: str) -> AgentResult:
    return AgentResult(merchant_id=merchant_id, action_taken="WAIT", success=True)


def run_batch(limit: int = 120) -> list[AgentResult]:
    return []
