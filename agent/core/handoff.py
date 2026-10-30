"""
agent/core/handoff.py — Generates structured handoff summaries for humans.

A person must be able to act in under a minute without asking the merchant anything.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from agent.domain.enums import HandoffTarget

if TYPE_CHECKING:
    from agent.core.context_builder import Context
    from agent.core.planner import PlannerDecision


class HandoffSummary(BaseModel):
    headline: str
    state_and_score: str
    what_happened: str
    sentiment_and_objection: str
    documents: str
    recommended_next_step: str


def _recommended_next_step(reason: str, target: HandoffTarget) -> str:
    r = reason.lower()
    if "discount" in r or "pricing" in r:
        return "Call within 2 hours and discuss pricing / waiver options in person."
    if "idle" in r or "nudge" in r or "activation" in r:
        return "Call after 3 PM; check QR placement, network connectivity, and Soundbox battery."
    if "settlement" in r:
        return "Check with the settlement operations team for bank status, then call merchant back."
    if "doc" in r or "kyc" in r:
        return "Visit merchant shop to collect physical copy of PAN or assist with live photo capture."
    if "negative" in r or "human" in r or "angry" in r:
        return "Call merchant immediately (within 30 mins); acknowledge dissatisfaction and address objections."
    if target == HandoffTarget.SUPPORT:
        return "Review open ticket in portal, contact partner bank if needed, and update merchant."
    return "Call merchant within 2 hours to resolve issue."


def build_summary(context: Context, decision: PlannerDecision) -> HandoffSummary:
    m = context.merchant
    headline = f"{m.owner_name} ({m.shop_name}) - {m.area}, {m.city} [{m.language.value.upper()}]"
    state_and_score = f"State: {m.state.value} | Lead Score: {m.lead_score}/100 ({m.score_explanation})"

    # Condense last messages/actions
    recent_events = []
    for msg in context.recent_messages[-5:]:
        prefix = "Merchant" if msg.direction == "in" else "Saathi"
        recent_events.append(f"{prefix}: {(msg.text or '')[:80]}")
    what_happened = " -> ".join(recent_events) if recent_events else "No previous conversation history."

    # Sentiment & objection
    last_inbound = next((msg for msg in reversed(context.recent_messages) if msg.direction == "in"), None)
    sentiment_val = f"{last_inbound.sentiment:.2f}" if (last_inbound and last_inbound.sentiment is not None) else "neutral"
    objection = last_inbound.intent if (last_inbound and last_inbound.intent) else "unspecified query"
    sentiment_and_objection = f"Sentiment: {sentiment_val} | Intent/Objection: {objection}"

    # Documents
    doc_info = f"PAN: {context.docs.pan_status} (attempts: {context.docs.pan_attempts}), Address: {context.docs.address_status}"
    if context.docs.pan_issues:
        doc_info += f" | Issues: {', '.join(context.docs.pan_issues)}"

    reason = str(decision.params.get("reason", decision.reasoning))
    target = decision.params.get("target", HandoffTarget.FSE)
    if isinstance(target, str):
        target = HandoffTarget(target)

    recommended = _recommended_next_step(reason, target)

    return HandoffSummary(
        headline=headline,
        state_and_score=state_and_score,
        what_happened=what_happened,
        sentiment_and_objection=sentiment_and_objection,
        documents=doc_info,
        recommended_next_step=recommended,
    )

