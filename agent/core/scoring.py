"""
agent/core/scoring.py — Lead scoring.

Pure function, no model, no I/O.
Score from 0 to 100 based on five weighted factors.
"""
from __future__ import annotations

from agent.ports import ContextBundle
from agent import settings

# Category value lookup (0.0 – 1.0)
_CATEGORY_VALUE: dict[str, float] = {
    "kirana": 1.0,
    "restaurant": 0.9,
    "pharmacy": 0.9,
    "sweet shop": 0.8,
    "sweet_shop": 0.8,
    "salon": 0.7,
    "clothing": 0.7,
    "mobile repair": 0.6,
    "mobile_repair": 0.6,
    "chai stall": 0.6,
    "chai_stall": 0.6,
}


def _category_value(category: str) -> float:
    return _CATEGORY_VALUE.get(category.lower().strip(), 0.5)


def _engagement_factor(bundle: ContextBundle) -> float:
    """
    0.0 = no reply
    0.5 = replied
    1.0 = asked questions or sent documents
    """
    inbound = [m for m in bundle.recent_messages if m.direction == "in"]
    if not inbound:
        return 0.0
    # Check if any message has a doc-oriented or question intent
    active_intents = {"ask_fees", "ask_documents", "send_document", "ask_discount",
                      "settlement_query", "device_issue", "ask_fees", "interest"}
    for m in inbound:
        if m.intent and m.intent in active_intents:
            return 1.0
    return 0.5


def _responsiveness_factor(bundle: ContextBundle) -> float:
    """
    1.0 if median reply time < 10 minutes
    0.5 if median reply time < 2 hours
    0.2 otherwise
    0.3 if unknown (no inbound messages)
    """
    inbound = [m for m in bundle.recent_messages if m.direction == "in"]
    if not inbound:
        return 0.3

    outbound = [m for m in bundle.recent_messages if m.direction == "out"]
    if not outbound or not inbound:
        return 0.3

    # Compute time from last outbound to first subsequent inbound
    reply_times_minutes: list[float] = []
    for out_msg in outbound:
        for in_msg in inbound:
            if in_msg.created_at > out_msg.created_at:
                delta = (in_msg.created_at - out_msg.created_at).total_seconds() / 60.0
                reply_times_minutes.append(delta)
                break

    if not reply_times_minutes:
        return 0.3

    median_minutes = sorted(reply_times_minutes)[len(reply_times_minutes) // 2]
    if median_minutes < 10:
        return 1.0
    if median_minutes < 120:
        return 0.5
    return 0.2


def _proximity_factor(bundle: ContextBundle) -> float:
    """
    (number of other leads within 2 km) / 5, capped at 1.0.
    We receive the nearby lead count from counters or merchant context.
    For now, proximity is derived from leads in context or stubbed to 0.
    The store's find_nearby_leads is called from the schedule_visit tool, not here.
    We approximate from the bundle — no external call allowed.
    """
    # Proximity is computed by the caller before calling score_merchant
    # and passed in via the bundle — we return 0 here as a safe default.
    # The caller should set merchant.lead_score via update_lead_score after
    # calling find_nearby_leads.
    return 0.0


def score_merchant(bundle: ContextBundle, nearby_count: int = 0) -> tuple[float, str]:
    """
    Compute the lead score for a merchant.

    Args:
        bundle: The merchant's context bundle.
        nearby_count: Number of other qualifying leads within 2 km (from store).

    Returns:
        (score, explanation) where score is 0–100.
    """
    footfall = bundle.merchant.footfall_score
    category = _category_value(bundle.merchant.category)
    engagement = _engagement_factor(bundle)
    responsiveness = _responsiveness_factor(bundle)
    proximity = min(nearby_count / 5.0, 1.0)

    w = settings
    score = 100 * (
        w.SCORE_WEIGHT_FOOTFALL * footfall
        + w.SCORE_WEIGHT_CATEGORY * category
        + w.SCORE_WEIGHT_ENGAGEMENT * engagement
        + w.SCORE_WEIGHT_RESPONSIVENESS * responsiveness
        + w.SCORE_WEIGHT_PROXIMITY * proximity
    )
    score = round(min(max(score, 0.0), 100.0), 2)

    parts: list[str] = []
    if footfall >= 0.8:
        parts.append("high footfall")
    elif footfall >= 0.5:
        parts.append("medium footfall")
    else:
        parts.append("low footfall")

    if engagement == 1.0:
        parts.append("actively engaged")
    elif engagement == 0.5:
        parts.append("replied")

    if responsiveness == 1.0:
        parts.append("replies quickly")
    elif responsiveness == 0.5:
        parts.append("moderate response time")

    if nearby_count > 0:
        parts.append(f"{nearby_count} nearby lead{'s' if nearby_count > 1 else ''}")

    explanation = ", ".join(parts) if parts else "default scoring"
    return score, explanation

