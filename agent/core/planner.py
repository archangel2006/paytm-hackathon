"""
agent/core/planner.py — Next-best-action planner.

decide(context, nlu, event) -> PlannerDecision

Strategy:
1. Compute allowed actions from lifecycle state
2. Run short-circuit rules (fast, no model)
3. If no rule matches, call the LLM planner
4. If the LLM returns an invalid action, retry once
5. If still invalid or LLM fails, return ESCALATE with source="fallback"
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel

from agent.core.context_builder import Context
from agent.core.llm_client import LLMUnavailable, generate_json
from agent.core.nlu import NluResult
from agent.domain.enums import ActionType, HandoffTarget, Intent, Language, LifecycleState
from agent.domain.lifecycle import allowed_actions
from agent import settings

logger = logging.getLogger(__name__)


class PlannerDecision(BaseModel):
    action: ActionType
    params: dict = {}
    language: Language
    reasoning: str
    confidence: float          # 0.0 to 1.0
    source: Literal["rule", "llm", "fallback"]


class _LLMDecision(BaseModel):
    action: str
    params: dict = {}
    language: str
    reasoning: str
    confidence: float
    source: str = "llm"


def _rule_based(
    context: Context,
    nlu: NluResult,
    event_kind: str,
    event_media_path: str | None,
    event_document_type: str = "pan",
    allowed: frozenset | None = None,
) -> PlannerDecision | None:
    """
    Short-circuit rules. The first matching rule wins with source="rule".
    Returns None if no rule applies.
    """
    state = context.merchant.state
    allowed = allowed or allowed_actions(state)
    counters = context.counters
    lang = nlu.language or context.merchant.language

    if event_kind == "preview":
        recommendations = {
            LifecycleState.NEW: (
                ActionType.SEND_INTRO,
                f"New lead. Initiate contact in {context.merchant.language.value}.",
            ),
            LifecycleState.CONTACTED: (
                ActionType.ANSWER_QUERY,
                "Lead reached out. Awaiting inquiry.",
            ),
            LifecycleState.ENGAGED: (
                ActionType.REQUEST_DOCS,
                "Merchant interested. Request PAN card and address proof.",
            ),
            LifecycleState.DOCS_PENDING: (
                ActionType.REREQUEST_DOC,
                "Documents pending verification or re-request.",
            ),
            LifecycleState.DOCS_VERIFIED: (
                ActionType.SCHEDULE_VISIT,
                "Documents passed pre-check. Cluster route with nearby merchants.",
            ),
            LifecycleState.VISIT_SCHEDULED: (
                ActionType.WAIT,
                "Visit scheduled. Waiting for FSE to install Soundbox.",
            ),
            LifecycleState.INSTALLED: (
                ActionType.SEND_ACTIVATION_NUDGE,
                "Device installed. Nudge merchant to complete first 10 transactions.",
            ),
            LifecycleState.ACTIVATING: (
                ActionType.SEND_ACTIVATION_NUDGE,
                "Device installed. Nudge merchant to complete first 10 transactions.",
            ),
            LifecycleState.ACTIVATED: (
                ActionType.EXPLAIN_SETTLEMENT,
                "Activated merchant. Ready for daily settlement assistance.",
            ),
            LifecycleState.AT_RISK: (
                ActionType.ESCALATE,
                "Device idle after 2 nudges. Warm handoff to FSE.",
            ),
        }
        action, reasoning = recommendations.get(
            state,
            (ActionType.WAIT, "Lead dormant or closed."),
        )
        if action not in allowed:
            action = ActionType.WAIT
        return PlannerDecision(
            action=action,
            params={},
            language=lang,
            reasoning=reasoning,
            confidence=0.90,
            source="rule",
        )
        if ActionType.REQUEST_DOCS in allowed:
            return PlannerDecision(
        action=ActionType.REQUEST_DOCS,
        params={},
        language=lang,
        reasoning="Document received. Requesting any remaining required documents before scheduling a visit.",
        confidence=1.0,
        source="rule",
            )

    if event_kind == "batch" and state == LifecycleState.NEW:
        if ActionType.SEND_INTRO in allowed:
            return PlannerDecision(
                action=ActionType.SEND_INTRO,
                params={},
                language=lang,
                reasoning="Ranked new lead selected for overnight outreach.",
                confidence=0.92,
                source="rule",
            )

    if event_kind != "media" and nlu.intent == Intent.OTHER and ActionType.ESCALATE in allowed:
            return PlannerDecision(
                action=ActionType.ESCALATE,
                params={"target": HandoffTarget.SUPPORT, "reason": "unsupported_question"},
                language=lang,
                reasoning="The question is outside the verified agent knowledge. Routing it to a human advisor.",
                confidence=1.0,
                source="rule",
            )

    # Rule 1: Opt-out
    if nlu.intent == Intent.OPT_OUT:
        return PlannerDecision(
            action=ActionType.WAIT,
            params={"days": 365, "reason": "opt-out"},
            language=lang,
            reasoning="Merchant has opted out. Setting consent to False and pausing all outbound messages.",
            confidence=1.0,
            source="rule",
        )

    # Rule 2: Wants human or very negative sentiment
    if nlu.wants_human or nlu.sentiment < settings.SENTIMENT_ESCALATE_THRESHOLD:
        return PlannerDecision(
            action=ActionType.ESCALATE,
            params={"target": HandoffTarget.FSE, "reason": "merchant_requested_human"},
            language=lang,
            reasoning="Merchant requested a human or expressed strong negative sentiment.",
            confidence=1.0,
            source="rule",
        )

    # Rule 3: Document uploads only progress after both required documents pass.
    if event_kind == "media" and event_media_path:
        uploaded_status = (
            context.docs.pan_status
            if event_document_type == "pan"
            else context.docs.address_status
        )
        if context.docs.all_verified and ActionType.SCHEDULE_VISIT in allowed:
            return PlannerDecision(
                action=ActionType.SCHEDULE_VISIT,
                params={},
                language=lang,
                reasoning="Both required documents passed their pre-checks and mock KYC. Scheduling the field visit.",
                confidence=1.0,
                source="rule",
            )
        if uploaded_status == "failed":
            if counters.doc_rerequests < settings.MAX_DOC_REREQUESTS:
                issues = (
                    context.docs.pan_issues
                    if event_document_type == "pan"
                    else context.docs.address_issues
                )
                return PlannerDecision(
                    action=ActionType.REREQUEST_DOC,
                    params={"doc_type": event_document_type, "issues": issues},
                    language=lang,
                    reasoning=f"Document failed pre-check (issues: {issues}). Requesting resubmission.",
                    confidence=1.0,
                    source="rule",
                )
            else:
                return PlannerDecision(
                    action=ActionType.ESCALATE,
                    params={"target": HandoffTarget.FSE, "reason": "doc_resubmission_exhausted"},
                    language=lang,
                    reasoning="Document re-request limit reached. Escalating to FSE.",
                    confidence=1.0,
                    source="rule",
                )

    # Rule 4: Settlement query
    if nlu.intent == Intent.SETTLEMENT_QUERY:
        if context.settlement is not None:
            return PlannerDecision(
                action=ActionType.EXPLAIN_SETTLEMENT,
                params={},
                language=lang,
                reasoning="Merchant asked about settlement. Looking up current status.",
                confidence=1.0,
                source="rule",
            )
        else:
            return PlannerDecision(
                action=ActionType.ESCALATE,
                params={"target": HandoffTarget.SUPPORT, "reason": "no_settlement_record"},
                language=lang,
                reasoning="No settlement record found. Escalating to support team.",
                confidence=1.0,
                source="rule",
            )

    # Rule 5: Discount request
    if nlu.intent == Intent.ASK_DISCOUNT:
        return PlannerDecision(
            action=ActionType.OFFER_DISCOUNT,
            params={"amount": 0},
            language=lang,
            reasoning="Merchant requested a discount. This requires human approval.",
            confidence=1.0,
            source="rule",
        )

    # Rule 6: Timer — activation check
    if event_kind == "timer":
        reason = context.merchant.state  # passed via params in handle_timer

    # Rule 8: Fee questions / interest / general queries
    if nlu.intent in (Intent.ASK_FEES, Intent.INTEREST, Intent.GREETING, Intent.ASK_DOCUMENTS):
        if ActionType.ANSWER_QUERY in allowed:
            inbound_query = next(
                (m.text for m in reversed(context.recent_messages) if m.direction == "in" and m.text),
                "",
            )
            query_text = inbound_query.strip() if inbound_query else nlu.intent.value
            return PlannerDecision(
                action=ActionType.ANSWER_QUERY,
                params={"query": query_text},
                language=lang,
                reasoning="Merchant asked about fees or product details. Providing grounded answer from policy.",
                confidence=0.95,
                source="rule",
            )

    # Rule 9: Agree visit
    if nlu.intent == Intent.AGREE_VISIT:
        if ActionType.SCHEDULE_VISIT in allowed:
            return PlannerDecision(
                action=ActionType.SCHEDULE_VISIT,
                params={},
                language=lang,
                reasoning="Merchant agreed to visit. Booking FSE slot.",
                confidence=0.95,
                source="rule",
            )

    return None


def _timer_rule(
    context: Context,
    timer_reason: str,
) -> PlannerDecision | None:
    """Rules for timer events."""
    counters = context.counters
    lang = context.merchant.language

    if timer_reason == "activation_check":
        if context.activity.txn_count == 0:
            if counters.nudges_sent < settings.MAX_ACTIVATION_NUDGES:
                return PlannerDecision(
                    action=ActionType.SEND_ACTIVATION_NUDGE,
                    params={"nudge_number": counters.nudges_sent + 1},
                    language=lang,
                    reasoning=f"Activation check: device has 0 transactions. Sending nudge {counters.nudges_sent + 1}.",
                    confidence=1.0,
                    source="rule",
                )
            else:
                return PlannerDecision(
                    action=ActionType.ESCALATE,
                    params={"target": HandoffTarget.FSE, "reason": "activation_nudges_exhausted"},
                    language=lang,
                    reasoning="2 activation nudges sent with no transactions. Escalating to FSE.",
                    confidence=1.0,
                    source="rule",
                )

    if timer_reason == "followup":
        if counters.contact_attempts >= settings.MAX_CONTACT_ATTEMPTS:
            return PlannerDecision(
                action=ActionType.WAIT,
                params={"days": 7, "move_to_dormant": True},
                language=lang,
                reasoning=f"Contact attempt limit ({settings.MAX_CONTACT_ATTEMPTS}) reached. Moving to DORMANT.",
                confidence=1.0,
                source="rule",
            )

    return None


def _llm_decide(context: Context, nlu: NluResult, allowed: frozenset) -> PlannerDecision:
    """Call the LLM planner. Retries once if it returns an invalid action. Falls back to ESCALATE."""
    from agent.prompts import planner_prompt

    allowed_list = [a.value for a in allowed]
    context_json = context.to_compact_json()
    nlu_json = json.dumps(nlu.model_dump(), default=str)
    prompt = planner_prompt.build(
        context_json=context_json,
        nlu_json=nlu_json,
        allowed_actions=allowed_list,
    )

    for attempt in range(2):
        try:
            raw = generate_json(prompt, _LLMDecision)
            # Validate action is in allowed
            try:
                action = ActionType(raw.action)
            except ValueError:
                logger.warning("LLM returned invalid action %r (attempt %d)", raw.action, attempt + 1)
                if attempt == 0:
                    continue
                raise ValueError(f"Invalid action: {raw.action}")

            if action not in allowed:
                logger.warning("LLM returned action %r not in allowed set (attempt %d)", action, attempt + 1)
                if attempt == 0:
                    continue
                raise ValueError(f"Action {action} not in allowed set")

            try:
                lang = Language(raw.language)
            except ValueError:
                lang = context.merchant.language

            return PlannerDecision(
                action=action,
                params=raw.params,
                language=lang,
                reasoning=raw.reasoning,
                confidence=max(0.0, min(1.0, raw.confidence)),
                source="llm",
            )
        except (LLMUnavailable, ValueError, Exception) as exc:
            if attempt == 0:
                logger.warning("LLM planner attempt 1 failed: %s", exc)
                continue
            logger.error("LLM planner failed after 2 attempts: %s", exc)
            break

    # Fallback
    return PlannerDecision(
        action=ActionType.ESCALATE,
        params={"target": HandoffTarget.FSE, "reason": "planner_fallback"},
        language=context.merchant.language,
        reasoning="Planner could not determine a valid action. Escalating as a precaution.",
        confidence=0.0,
        source="fallback",
    )


def decide(
    context: Context,
    nlu: NluResult,
    event_kind: str = "text",
    event_media_path: str | None = None,
    event_document_type: str = "pan",
    timer_reason: str | None = None,
) -> PlannerDecision:
    """
    Decide the next best action for a merchant.

    Args:
        context: Current merchant context.
        nlu: NLU result for the latest message.
        event_kind: "text", "media", "voice", or "timer".
        event_media_path: Path to uploaded media file (if any).
        timer_reason: Reason string for timer events.

    Returns:
        PlannerDecision with action, params, language, reasoning, confidence, source.
    """
    state = context.merchant.state
    allowed = allowed_actions(state)

    # Timer events use dedicated rules
    if event_kind == "timer" and timer_reason:
        timer_decision = _timer_rule(context, timer_reason)
        if timer_decision and timer_decision.action in allowed:
            return timer_decision

    # Short-circuit rules
    rule_decision = _rule_based(
        context,
        nlu,
        event_kind,
        event_media_path,
        event_document_type,
        allowed=allowed,
    )
    if rule_decision is not None:
        # Ensure the rule's action is allowed in the current state
        if rule_decision.action in allowed:
            return rule_decision
        # If the rule fires but the action isn't allowed, use LLM
        logger.warning(
            "Rule decided %s but it's not allowed in state %s — falling through to LLM",
            rule_decision.action,
            state,
        )

    # LLM planner
    return _llm_decide(context, nlu, allowed)
