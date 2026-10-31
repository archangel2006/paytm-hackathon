"""
agent/core/executor.py — Executes decisions permitted by Guardrails.

Handles:
- Action status updates (executed, blocked, pending_approval)
- Tool invocation (send_whatsapp, schedule_visit, etc.)
- Database state transitions via store.update_state
- Audit log writes via store.write_audit
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from agent import settings
from agent.core import templates
from agent.core.llm_client import LLMUnavailable, generate_text
from agent.prompts import reply_prompt
from agent.core.context_builder import Context
from agent.core.guardrails import GuardrailResult
from agent.core.planner import PlannerDecision
from agent.domain.enums import (
    ActionStatus,
    ActionType,
    HandoffTarget,
    Language,
    LifecycleState,
)
from agent.policy.retrieval import search_policy
from agent.ports import (
    Channel,
    Clock,
    DocumentChecker,
    OutgoingMessage,
    Store,
)
from agent.tools import impl as tools

logger = logging.getLogger(__name__)


def _message_sent(result: Any) -> bool:
    if not result.ok:
        logger.error("Outbound message tool failed: %s", result.error)
        return False
    if result.data.get("ok") is not True:
        logger.error(
            "Outbound message was not delivered: code=%s detail=%s",
            result.data.get("error_code"),
            result.data.get("error_detail"),
        )
        return False
    return True


def execute(
    decision: PlannerDecision,
    guardrail_res: GuardrailResult,
    action_id: str,
    context: Context,
    store: Store,
    channel: Channel,
    doc_checker: DocumentChecker,
    clock: Clock,
) -> tuple[bool, LifecycleState, ActionStatus]:
    """
    Executes the action if guardrail verdict is 'run' or handles hold/escalate/block.

    Returns:
        (reply_sent, state_after, action_status)
    """
    merchant = context.merchant
    merchant_id = merchant.id
    now = clock.now()
    action = decision.action
    lang = decision.language

    # 1. Blocked
    if guardrail_res.verdict == "block":
        store.update_action_status(action_id, ActionStatus.BLOCKED)
        store.write_audit(
            actor="guardrails",
            event_type="action_blocked",
            merchant_id=merchant_id,
            payload={"action": action.value, "notes": guardrail_res.notes},
        )
        return False, merchant.state, ActionStatus.BLOCKED

    # 2. Hold (L1 Suggestion or L2 Approval)
    if guardrail_res.verdict == "hold":
        store.update_action_status(action_id, guardrail_res.status)
        store.write_audit(
            actor="guardrails",
            event_type="action_held",
            merchant_id=merchant_id,
            payload={
                "action": action.value,
                "status": guardrail_res.status.value,
                "notes": guardrail_res.notes,
            },
        )
        # For OFFER_DISCOUNT, send holding reply so merchant isn't left hanging
        if action == ActionType.OFFER_DISCOUNT:
            text, t_name, t_params = templates.render(
                "saathi_holding_discount", owner_name=merchant.owner_name
            )
            send_result = tools.send_whatsapp(
                merchant_id=merchant_id,
                channel=channel,
                store=store,
                text=text,
                language=lang,
                template_name=t_name,
                template_params=t_params,
            )
            return _message_sent(send_result), merchant.state, guardrail_res.status
        return False, merchant.state, guardrail_res.status

    # 3. Escalate (Handoff to human)
    if guardrail_res.verdict == "escalate" or action == ActionType.ESCALATE:
        target = decision.params.get("target", HandoffTarget.FSE)
        reason = decision.params.get("reason", decision.reasoning)
        handoff_result = tools.escalate_to_human(
            merchant_id=merchant_id,
            action_id=action_id,
            target=target,
            reason=reason,
            store=store,
            clock=clock,
            decision=decision,
        )
        if not handoff_result.ok:
            logger.error("Failed to create handoff: %s", handoff_result.error)
            store.update_action_status(action_id, ActionStatus.FAILED)
            store.write_audit(
                actor="agent",
                event_type="action_failed",
                merchant_id=merchant_id,
                payload={"action": action.value, "error": handoff_result.error},
            )
            return False, merchant.state, ActionStatus.FAILED
        store.update_action_status(action_id, ActionStatus.EXECUTED, executed_at=now)

        # Send holding reply
        text, t_name, t_params = templates.render(
            "saathi_holding_escalation",
            owner_name=merchant.owner_name,
            fse_name="our executive",
        )
        send_result = tools.send_whatsapp(
            merchant_id=merchant_id,
            channel=channel,
            store=store,
            text=text,
            language=lang,
            template_name=t_name,
            template_params=t_params,
        )
        reply_sent = _message_sent(send_result)

        # If escalation happened due to idle device, move to AT_RISK
        if "activation" in str(reason).lower() or context.counters.nudges_sent >= settings.MAX_ACTIVATION_NUDGES:
            if merchant.state in (LifecycleState.ACTIVATING, LifecycleState.INSTALLED):
                store.update_state(merchant_id, LifecycleState.AT_RISK, reason="Activation nudges failed")
                return reply_sent, LifecycleState.AT_RISK, ActionStatus.EXECUTED

        return reply_sent, merchant.state, ActionStatus.EXECUTED

    # 4. Run (L3 Autonomous Execution)
    reply_sent = False
    new_state = merchant.state
    message_required = False

    if action == ActionType.SEND_INTRO:
        message_required = True
        t_id = templates.intro_template_id(lang.value)
        text, t_name, t_params = templates.render(t_id, owner_name=merchant.owner_name)
        res = tools.send_whatsapp(
            merchant_id=merchant_id,
            channel=channel,
            store=store,
            text=text,
            language=lang,
            template_name=t_name,
            template_params=t_params,
        )
        reply_sent = _message_sent(res)
        if reply_sent and merchant.state == LifecycleState.NEW:
            store.update_state(merchant_id, LifecycleState.CONTACTED, reason="Intro message sent")
            new_state = LifecycleState.CONTACTED

    elif action == ActionType.ANSWER_QUERY:
        message_required = True
        query = decision.params.get("query", "")
        if not query:
            query = next(
                (m.text for m in reversed(context.recent_messages) if m.direction == "in" and m.text),
                "",
            )
        passages = search_policy(query, language=lang.value)
        text = decision.params.get("reply_text")

        if text:
            audit_source = passages[0].source if passages else "general_policy"
        elif passages:
            audit_source = passages[0].source
            prompt = reply_prompt.build(
                merchant_name=merchant.owner_name or merchant.shop_name,
                language=lang.value,
                question=query,
                passages=[{"source": p.source, "text": p.text} for p in passages],
            )
            try:
                llm_reply = generate_text(prompt).strip()
                if llm_reply:
                    text = llm_reply
            except (LLMUnavailable, Exception) as exc:
                logger.warning("Executor LLM reply generation failed: %s; using sensible grounded fallback", exc)
                text = None

            if not text:
                if lang in (Language.HINDI, Language.HINGLISH):
                    text = (
                        f"{merchant.owner_name} ji, Paytm Soundbox ka monthly rental ₹125 hai aur "
                        f"UPI payments par koi extra charge nahi lagta (0% MDR under ₹2,000). "
                        f"Kya hum aapki shop ke liye visit schedule karein?"
                    )
                else:
                    text = (
                        f"Hello {merchant.owner_name}, the Paytm Soundbox monthly rental is ₹125/month, "
                        f"and UPI transactions carry zero extra charge (0% for payments under ₹2,000). "
                        f"Would you like us to schedule a visit to install it?"
                    )
        else:
            audit_source = "general_policy"
            if lang in (Language.HINDI, Language.HINGLISH):
                text = (
                    f"Namaste {merchant.owner_name} ji! Main Paytm Saathi hoon. "
                    f"Aap Soundbox ke fees, rental ya installation ke baare mein kuch bhi pooch sakte hain."
                )
            else:
                text = (
                    f"Hello {merchant.owner_name}! I am Paytm Saathi. "
                    f"Feel free to ask any questions about Soundbox rental, fees, or visit scheduling."
                )

        res = tools.send_whatsapp(
            merchant_id=merchant_id,
            channel=channel,
            store=store,
            text=text,
            language=lang,
        )
        reply_sent = _message_sent(res)
        store.write_audit(
            actor="agent",
            event_type="policy_referenced",
            merchant_id=merchant_id,
            payload={"source": audit_source, "query": query},
        )
        if reply_sent and merchant.state in (LifecycleState.NEW, LifecycleState.CONTACTED):
            store.update_state(merchant_id, LifecycleState.ENGAGED, reason="Merchant engaged in query")
            new_state = LifecycleState.ENGAGED

    elif action == ActionType.REQUEST_DOCS:
        message_required = True
        text, t_name, t_params = templates.render("saathi_doc_request", owner_name=merchant.owner_name)
        res = tools.send_whatsapp(
            merchant_id=merchant_id,
            channel=channel,
            store=store,
            text=text,
            language=lang,
            template_name=t_name,
            template_params=t_params,
        )
        reply_sent = _message_sent(res)
        if reply_sent and merchant.state == LifecycleState.ENGAGED:
            store.update_state(merchant_id, LifecycleState.DOCS_PENDING, reason="Documents requested")
            new_state = LifecycleState.DOCS_PENDING

    elif action == ActionType.REREQUEST_DOC:
        message_required = True
        doc_type = decision.params.get("doc_type", "pan")
        text, t_name, t_params = templates.render(
            "saathi_doc_rerequest", owner_name=merchant.owner_name, doc_type=doc_type
        )
        res = tools.send_whatsapp(
            merchant_id=merchant_id,
            channel=channel,
            store=store,
            text=text,
            language=lang,
            template_name=t_name,
            template_params=t_params,
        )
        reply_sent = _message_sent(res)

    elif action == ActionType.SCHEDULE_VISIT:
        v_res = tools.schedule_visit(
            merchant_id=merchant_id,
            store=store,
            clock=clock,
            preferred_slot=decision.params.get("preferred_slot"),
        )
        if not v_res.ok:
            logger.error("Visit scheduling failed: %s", v_res.error)
            store.update_action_status(action_id, ActionStatus.FAILED)
            store.write_audit(
                actor="agent",
                event_type="action_failed",
                merchant_id=merchant_id,
                payload={"action": action.value, "error": v_res.error},
            )
            return False, merchant.state, ActionStatus.FAILED
        message_required = True
        v_data = v_res.data
        slot_time = v_data.get("slot_start", "tomorrow")
        text, t_name, t_params = templates.render(
            "saathi_visit_confirm",
            owner_name=merchant.owner_name,
            date=slot_time.split(" ")[0],
            time=slot_time.split(" ")[1] if " " in slot_time else "11:00 AM",
            fse_name="Amit Sharma",
        )
        res = tools.send_whatsapp(
            merchant_id=merchant_id,
            channel=channel,
            store=store,
            text=text,
            language=lang,
            template_name=t_name,
            template_params=t_params,
        )
        reply_sent = _message_sent(res)
        new_state = LifecycleState.VISIT_SCHEDULED

    elif action == ActionType.SEND_ACTIVATION_NUDGE:
        message_required = True
        nudge_num = decision.params.get("nudge_number", context.counters.nudges_sent + 1)
        text, t_name, t_params = templates.render(
            "saathi_activation_nudge", owner_name=merchant.owner_name, nudge_number=nudge_num
        )
        res = tools.send_whatsapp(
            merchant_id=merchant_id,
            channel=channel,
            store=store,
            text=text,
            language=lang,
            template_name=t_name,
            template_params=t_params,
        )
        reply_sent = _message_sent(res)

    elif action == ActionType.EXPLAIN_SETTLEMENT:
        message_required = True
        settlement_res = tools.check_settlement(merchant_id=merchant_id, store=store)
        if settlement_res.ok and settlement_res.data.get("found"):
            st = settlement_res.data["settlement"]
            amount_str = str(st.get("amount", "0"))
            exp_date_str = str(st.get("expected_date", "next working day"))
            delay_reason = st.get("delay_reason")

            if delay_reason:
                text, t_name, t_params = templates.render(
                    "saathi_settlement_delayed",
                    owner_name=merchant.owner_name,
                    amount=amount_str,
                    expected_date=exp_date_str,
                    delay_reason=delay_reason,
                )
            else:
                text, t_name, t_params = templates.render(
                    "saathi_settlement_ok",
                    owner_name=merchant.owner_name,
                    amount=amount_str,
                    expected_date=exp_date_str,
                )

            res = tools.send_whatsapp(
                merchant_id=merchant_id,
                channel=channel,
                store=store,
                text=text,
                language=lang,
                template_name=t_name,
                template_params=t_params,
            )
            reply_sent = _message_sent(res)
        else:
            # Escalate if settlement not found
            handoff_result = tools.escalate_to_human(
                merchant_id=merchant_id,
                action_id=action_id,
                target=HandoffTarget.SUPPORT,
                reason="no_settlement_record",
                store=store,
                clock=clock,
                decision=decision,
            )
            if not handoff_result.ok:
                logger.error("Failed to create settlement handoff: %s", handoff_result.error)
                store.update_action_status(action_id, ActionStatus.FAILED)
                store.write_audit(
                    actor="agent",
                    event_type="action_failed",
                    merchant_id=merchant_id,
                    payload={"action": action.value, "error": handoff_result.error},
                )
                return False, merchant.state, ActionStatus.FAILED
            text, t_name, t_params = templates.render(
                "saathi_holding_escalation",
                owner_name=merchant.owner_name,
                fse_name="our support team",
            )
            res = tools.send_whatsapp(
                merchant_id=merchant_id,
                channel=channel,
                store=store,
                text=text,
                language=lang,
                template_name=t_name,
                template_params=t_params,
            )
            reply_sent = _message_sent(res)

    elif action == ActionType.CLOSE_LEAD:
        if merchant.state in (LifecycleState.NEW, LifecycleState.ENGAGED, LifecycleState.CONTACTED):
            store.update_state(merchant_id, LifecycleState.LOST, reason="Lead closed")
            new_state = LifecycleState.LOST

    elif action == ActionType.WAIT:
        if decision.params.get("move_to_dormant") and merchant.state in (LifecycleState.CONTACTED, LifecycleState.DOCS_PENDING):
            store.update_state(merchant_id, LifecycleState.DORMANT, reason="Follow-ups exhausted")
            new_state = LifecycleState.DORMANT

    execution_status = (
        ActionStatus.FAILED if message_required and not reply_sent else ActionStatus.EXECUTED
    )
    store.update_action_status(
        action_id,
        execution_status,
        executed_at=now if execution_status == ActionStatus.EXECUTED else None,
    )
    store.write_audit(
        actor="agent",
        event_type="action_executed" if execution_status == ActionStatus.EXECUTED else "action_failed",
        merchant_id=merchant_id,
        payload={"action": action.value, "reply_sent": reply_sent},
    )

    return reply_sent, new_state, execution_status
