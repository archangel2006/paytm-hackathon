"""
agent/core/guardrails.py — Guardrail evaluation.

guardrails.evaluate(decision, context, tool_outputs, store, clock) -> GuardrailResult

Evaluation order (stop at first trigger):
1. Hard blocks
2. Escalation triggers
3. Autonomy level lookup
4. Special rule: OFFER_DISCOUNT always L2
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from agent.core.autonomy import resolve as resolve_autonomy
from agent.core.context_builder import Context
from agent.core.planner import PlannerDecision
from agent.domain.enums import ActionStatus, ActionType, AutonomyLevel
from agent.ports import Store
from agent import settings


class GuardrailResult(BaseModel):
    verdict: Literal["run", "hold", "escalate", "block"]
    autonomy_level: AutonomyLevel
    notes: list[str]
    status: ActionStatus


# ── Forbidden actions (never execute autonomously in MVP) ─────
_FORBIDDEN_AUTO: frozenset[ActionType] = frozenset({
    # OFFER_DISCOUNT handled separately below
})

# ── Sensitive topic keywords ──────────────────────────────────
_SENSITIVE_KEYWORDS = [
    "fraud", "chargeback", "legal", "court", "police", "consumer forum",
    "scam", "cheating", "chargebacks", "lawsuit",
]


def _has_unverifiable_claim(text: str, tool_outputs: dict[str, Any]) -> bool:
    """
    Check if the proposed reply text contains a specific number, currency, or date
    that does NOT appear in the tool outputs of this step.

    Simple heuristic: find all numbers and dates in the text and check they appear
    somewhere in the serialized tool outputs.
    """
    if not text:
        return False

    # Find numbers with currency or date-like patterns
    claims = re.findall(r"₹[\d,]+|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d+ (?:days?|hours?|working days?)", text)
    if not claims:
        return False

    tool_str = str(tool_outputs)
    for claim in claims:
        # Strip ₹ and commas for comparison
        bare = re.sub(r"[₹,]", "", claim)
        if bare not in tool_str and claim not in tool_str:
            return True
    return False


def evaluate(
    decision: PlannerDecision,
    context: Context,
    store: Store,
    tool_outputs: dict[str, Any] | None = None,
    now: datetime | None = None,
    proposed_text: str = "",
) -> GuardrailResult:
    """
    Evaluate a planner decision against all guardrail rules.

    Args:
        decision: The planner's proposed action.
        context: Current merchant context.
        store: The store port (for autonomy lookup).
        tool_outputs: Outputs from tools called in this step (for grounded-claim check).
        now: Current time (from clock).
        proposed_text: The text that would be sent to the merchant.

    Returns:
        GuardrailResult with verdict, autonomy_level, notes, and status.
    """
    tool_outputs = tool_outputs or {}
    now = now or context.now
    notes: list[str] = []

    action = decision.action

    # ── STEP 1: Hard blocks ───────────────────────────────────

    # 1a. Consent check
    if not context.consent and action not in (ActionType.WAIT, ActionType.CLOSE_LEAD):
        notes.append("Merchant has opted out — no outbound messages allowed.")
        return GuardrailResult(
            verdict="block",
            autonomy_level=AutonomyLevel.L3,
            notes=notes,
            status=ActionStatus.BLOCKED,
        )

    # 1b. Daily message rate limit (outbound only)
    _outbound_actions = {
        ActionType.SEND_INTRO, ActionType.ANSWER_QUERY, ActionType.REQUEST_DOCS,
        ActionType.REREQUEST_DOC, ActionType.SCHEDULE_VISIT,
        ActionType.SEND_ACTIVATION_NUDGE, ActionType.EXPLAIN_SETTLEMENT,
        ActionType.ESCALATE,
    }

    # 1c. Daily message rate limit (outbound only)
    if (
        action in _outbound_actions
        and settings.MAX_MESSAGES_PER_DAY > 0
        and context.counters.messages_today >= settings.MAX_MESSAGES_PER_DAY
    ):
        notes.append(
            f"Daily message limit reached ({settings.MAX_MESSAGES_PER_DAY} messages today)."
        )
        return GuardrailResult(
            verdict="block",
            autonomy_level=AutonomyLevel.L3,
            notes=notes,
            status=ActionStatus.BLOCKED,
        )

    # 1d. Unverifiable claim in proposed text
    if proposed_text and _has_unverifiable_claim(proposed_text, tool_outputs):
        notes.append("Unverifiable claim detected in proposed reply — replaced with safe template.")
        return GuardrailResult(
            verdict="block",
            autonomy_level=AutonomyLevel.L3,
            notes=notes,
            status=ActionStatus.BLOCKED,
        )

    # 1e. Forbidden actions (loans/refunds — OFFER_DISCOUNT handled below)
    if action in _FORBIDDEN_AUTO:
        notes.append(f"Action {action} is forbidden in this prototype.")
        return GuardrailResult(
            verdict="block",
            autonomy_level=AutonomyLevel.L2,
            notes=notes,
            status=ActionStatus.BLOCKED,
        )

    # ── STEP 2: Escalation triggers ───────────────────────────

    # 2a. Negative sentiment
    last_inbound = next(
        (m for m in reversed(context.recent_messages) if m.direction == "in"), None
    )
    if last_inbound and last_inbound.sentiment is not None:
        if last_inbound.sentiment < settings.SENTIMENT_ESCALATE_THRESHOLD:
            notes.append(
                f"Negative sentiment ({last_inbound.sentiment:.2f}) — escalating to FSE."
            )
            return GuardrailResult(
                verdict="escalate",
                autonomy_level=AutonomyLevel.L3,
                notes=notes,
                status=ActionStatus.PROPOSED,
            )

    # 2b. Planner low confidence
    if decision.confidence < settings.MIN_PLANNER_CONFIDENCE:
        notes.append(
            f"Low planner confidence ({decision.confidence:.2f}) — escalating."
        )
        return GuardrailResult(
            verdict="escalate",
            autonomy_level=AutonomyLevel.L3,
            notes=notes,
            status=ActionStatus.PROPOSED,
        )

    # 2c. Sensitive topic in recent messages
    recent_text = " ".join(
        (m.text or "").lower() for m in context.recent_messages[-3:]
    )
    if any(kw in recent_text for kw in _SENSITIVE_KEYWORDS):
        notes.append("Sensitive topic detected — escalating to support.")
        return GuardrailResult(
            verdict="escalate",
            autonomy_level=AutonomyLevel.L3,
            notes=notes,
            status=ActionStatus.PROPOSED,
        )

    # ── STEP 3: Special case — OFFER_DISCOUNT always L2 ──────
    if action == ActionType.OFFER_DISCOUNT:
        notes.append("Discounts are never promised autonomously — queued for approval.")
        return GuardrailResult(
            verdict="hold",
            autonomy_level=AutonomyLevel.L2,
            notes=notes,
            status=ActionStatus.PENDING_APPROVAL,
        )

    # ── STEP 4: Autonomy level lookup ─────────────────────────
    level, initial_status = resolve_autonomy(action, store)

    if level == AutonomyLevel.L1:
        notes.append("L1 autonomy — showing as suggestion only.")
        return GuardrailResult(
            verdict="hold",
            autonomy_level=AutonomyLevel.L1,
            notes=notes,
            status=ActionStatus.PROPOSED,
        )
    if level == AutonomyLevel.L2:
        notes.append("L2 autonomy — queued for human approval.")
        return GuardrailResult(
            verdict="hold",
            autonomy_level=AutonomyLevel.L2,
            notes=notes,
            status=ActionStatus.PENDING_APPROVAL,
        )

    # L3 — execute
    return GuardrailResult(
        verdict="run",
        autonomy_level=AutonomyLevel.L3,
        notes=notes,
        status=ActionStatus.PROPOSED,
    )
