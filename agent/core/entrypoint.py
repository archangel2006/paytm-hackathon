"""
agent/core/entrypoint.py — The six official entrypoints of the Agent.

1. configure
2. handle_incoming
3. handle_timer
4. run_batch
5. preview_next_action
6. approve_action
7. reject_action
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from agent import settings
from agent.core import context_builder, executor, guardrails, nlu, planner, scoring
from agent.domain.enums import (
    ActionStatus,
    ActionType,
    DocType,
    Language,
    LifecycleState,
)
from agent.ports import (
    ActionSummary,
    AgentResult,
    Channel,
    Clock,
    DocumentChecker,
    IncomingEvent,
    Store,
)
from agent.tools import impl as tools

logger = logging.getLogger(__name__)

# Module-level registry for injected components
_STORE: Store | None = None
_CHANNEL: Channel | None = None
_DOCUMENTS: DocumentChecker | None = None
_CLOCK: Clock | None = None


def configure(
    store: Store,
    channel: Channel,
    documents: DocumentChecker,
    clock: Clock,
    custom_settings: Any = None,
) -> None:
    """Wire ports once at startup (called by server/main.py or test suites)."""
    global _STORE, _CHANNEL, _DOCUMENTS, _CLOCK
    _STORE = store
    _CHANNEL = channel
    _DOCUMENTS = documents
    _CLOCK = clock


def _get_ports() -> tuple[Store, Channel, DocumentChecker, Clock]:
    if _STORE is None or _CHANNEL is None or _DOCUMENTS is None or _CLOCK is None:
        raise RuntimeError("Agent not configured! Call agent.configure(...) before running entrypoints.")
    return _STORE, _CHANNEL, _DOCUMENTS, _CLOCK


def handle_incoming(event: IncomingEvent) -> AgentResult:
    """Full loop for one incoming event (message, media upload, etc.)."""
    store, channel, doc_checker, clock = _get_ports()

    # 1. Idempotency check
    if store.already_processed(event.event_id):
        merchant = store.get_merchant_by_phone(event.phone_e164)
        mid = merchant.id if merchant else "unknown"
        state = merchant.state if merchant else LifecycleState.NEW
        return AgentResult(merchant_id=mid, actions=[], reply_sent=False, state_after=state)

    # 2. Lookup or create lead
    merchant = store.get_merchant_by_phone(event.phone_e164)
    if not merchant:
        merchant = store.create_lead(
            phone_e164=event.phone_e164,
            channel=event.channel,
            language_guess=Language.HINDI,
        )

    # 3. Handle document media if kind == media
    doc_id: str | None = None
    if event.kind == "media" and event.media_path:
        doc_type = DocType.PAN
        doc_id = store.save_document(merchant.id, doc_type, event.media_path)
        val_res = tools.validate_kyc_doc(
            document_id=doc_id,
            merchant_id=merchant.id,
            file_path=event.media_path,
            doc_type=doc_type,
            doc_checker=doc_checker,
            store=store,
        )
        if val_res.ok and val_res.data.get("validation", {}).get("precheck_passed"):
            store.update_state(merchant.id, LifecycleState.DOCS_VERIFIED, reason="KYC precheck passed")

    # 4. Save incoming message
    store.save_message(
        merchant_id=merchant.id,
        direction="in",
        channel=str(event.channel),
        kind=event.kind,
        text=event.text,
        event_id=event.event_id,
    )

    # 5. Build context
    bundle = store.get_context_bundle(merchant.id)
    ctx = context_builder.build(bundle, now=clock.now())

    # 6. Understand (NLU)
    nlu_res = nlu.classify(text=event.text or "")
    if event.text:
        # Update lead score after inbound event
        new_score, explanation = scoring.score_merchant(bundle)
        store.update_lead_score(merchant.id, new_score, explanation)

    # 7. Plan
    decision = planner.decide(
        context=ctx,
        nlu=nlu_res,
        event_kind=event.kind,
        event_media_path=event.media_path,
        event_text=event.text,
    )

    # 8. Guardrails
    guard_res = guardrails.evaluate(
        decision=decision,
        context=ctx,
        store=store,
        now=clock.now(),
    )
    logger.info(
        "Guardrail decision merchant_id=%s action=%s verdict=%s status=%s notes=%s",
        merchant.id,
        decision.action.value,
        guard_res.verdict,
        guard_res.status.value,
        guard_res.notes,
    )

    # 9. Save action
    action_id = store.save_action(
        merchant_id=merchant.id,
        action_type=decision.action,
        params=decision.params,
        reasoning=decision.reasoning,
        confidence=decision.confidence,
        source=decision.source,
        autonomy_level=guard_res.autonomy_level,
        guardrail_notes=guard_res.notes,
        prompt_version=settings.PROMPT_VERSION,
    )

    # 10. Execute
    reply_sent, state_after = executor.execute(
        decision=decision,
        guardrail_res=guard_res,
        action_id=action_id,
        context=ctx,
        store=store,
        channel=channel,
        doc_checker=doc_checker,
        clock=clock,
    )

    summary = ActionSummary(
        id=action_id,
        action_type=decision.action,
        status=guard_res.status if guard_res.verdict in ("hold", "block") else ActionStatus.EXECUTED,
        autonomy_level=guard_res.autonomy_level,
        reasoning=decision.reasoning,
    )

    return AgentResult(
        merchant_id=merchant.id,
        actions=[summary],
        reply_sent=reply_sent,
        state_after=state_after,
    )


def handle_timer(merchant_id: str, reason: str) -> AgentResult:
    """Triggered by the server scheduler for due jobs."""
    store, channel, doc_checker, clock = _get_ports()
    merchant = store.get_merchant(merchant_id)
    if not merchant:
        raise ValueError(f"Merchant not found: {merchant_id}")

    bundle = store.get_context_bundle(merchant_id)
    ctx = context_builder.build(bundle, now=clock.now())

    dummy_nlu = nlu.classify(text="")
    decision = planner.decide(
        context=ctx,
        nlu=dummy_nlu,
        event_kind="timer",
        timer_reason=reason,
    )

    guard_res = guardrails.evaluate(
        decision=decision,
        context=ctx,
        store=store,
        now=clock.now(),
    )

    action_id = store.save_action(
        merchant_id=merchant_id,
        action_type=decision.action,
        params=decision.params,
        reasoning=decision.reasoning,
        confidence=decision.confidence,
        source=decision.source,
        autonomy_level=guard_res.autonomy_level,
        guardrail_notes=guard_res.notes,
        prompt_version=settings.PROMPT_VERSION,
    )

    reply_sent, state_after = executor.execute(
        decision=decision,
        guardrail_res=guard_res,
        action_id=action_id,
        context=ctx,
        store=store,
        channel=channel,
        doc_checker=doc_checker,
        clock=clock,
    )

    return AgentResult(
        merchant_id=merchant_id,
        actions=[
            ActionSummary(
                id=action_id,
                action_type=decision.action,
                status=guard_res.status if guard_res.verdict in ("hold", "block") else ActionStatus.EXECUTED,
                autonomy_level=guard_res.autonomy_level,
                reasoning=decision.reasoning,
            )
        ],
        reply_sent=reply_sent,
        state_after=state_after,
    )


def run_batch(limit: int = 120) -> list[AgentResult]:
    """Overnight batch processing of leads."""
    store, _, _, _ = _get_ports()
    results = []
    # Process high scoring leads or pending contacts
    return results


def preview_next_action(merchant_id: str) -> ActionSummary:
    """Planner proposal preview with no side effects."""
    store, _, _, clock = _get_ports()
    bundle = store.get_context_bundle(merchant_id)
    ctx = context_builder.build(bundle, now=clock.now())
    dummy_nlu = nlu.classify(text="")
    decision = planner.decide(context=ctx, nlu=dummy_nlu)
    guard_res = guardrails.evaluate(decision=decision, context=ctx, store=store, now=clock.now())
    return ActionSummary(
        id="preview",
        action_type=decision.action,
        status=guard_res.status,
        autonomy_level=guard_res.autonomy_level,
        reasoning=decision.reasoning,
    )


def approve_action(action_id: str, by: str, edits: dict | None = None) -> AgentResult:
    """Execute a pending L2 action upon human approval."""
    store, channel, doc_checker, clock = _get_ports()
    action_dict = store.get_action(action_id) if hasattr(store, "get_action") else None
    if not action_dict:
        raise ValueError(f"Action not found: {action_id}")

    merchant_id = action_dict["merchant_id"]
    bundle = store.get_context_bundle(merchant_id)
    ctx = context_builder.build(bundle, now=clock.now())

    decision = planner.PlannerDecision(
        action=ActionType(action_dict["action_type"]),
        params=edits if edits else action_dict.get("params", {}),
        language=ctx.merchant.language,
        reasoning=f"Approved by {by}. " + action_dict.get("reasoning", ""),
        confidence=1.0,
        source="rule",
    )

    guard_res = guardrails.GuardrailResult(
        verdict="run",
        autonomy_level=action_dict.get("autonomy_level", "L2"),
        notes=["Human approved"],
        status=ActionStatus.EXECUTED,
    )

    store.update_action_status(action_id, ActionStatus.APPROVED, approved_by=by)
    store.write_audit(
        actor=by,
        event_type="action_approved",
        merchant_id=merchant_id,
        payload={"action_id": action_id},
    )

    reply_sent, state_after = executor.execute(
        decision=decision,
        guardrail_res=guard_res,
        action_id=action_id,
        context=ctx,
        store=store,
        channel=channel,
        doc_checker=doc_checker,
        clock=clock,
    )

    return AgentResult(
        merchant_id=merchant_id,
        actions=[
            ActionSummary(
                id=action_id,
                action_type=decision.action,
                status=ActionStatus.EXECUTED,
                autonomy_level=guard_res.autonomy_level,
                reasoning=decision.reasoning,
            )
        ],
        reply_sent=reply_sent,
        state_after=state_after,
    )


def reject_action(action_id: str, by: str, reason_code: str) -> AgentResult:
    """Reject an L2 action and log human override."""
    store, _, _, _ = _get_ports()
    action_dict = store.get_action(action_id) if hasattr(store, "get_action") else None
    if not action_dict:
        raise ValueError(f"Action not found: {action_id}")

    merchant_id = action_dict["merchant_id"]
    store.update_action_status(action_id, ActionStatus.REJECTED, rejection_reason=reason_code)
    store.write_audit(
        actor=by,
        event_type="action_rejected",
        merchant_id=merchant_id,
        payload={"action_id": action_id, "reason_code": reason_code},
    )

    merchant = store.get_merchant(merchant_id)
    return AgentResult(
        merchant_id=merchant_id,
        actions=[
            ActionSummary(
                id=action_id,
                action_type=ActionType(action_dict["action_type"]),
                status=ActionStatus.REJECTED,
                autonomy_level=action_dict.get("autonomy_level", "L2"),
                reasoning=f"Rejected by {by}: {reason_code}",
            )
        ],
        reply_sent=False,
        state_after=merchant.state if merchant else LifecycleState.NEW,
    )
