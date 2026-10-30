"""
agent/tools/impl.py — Implementation of the 7 Agent Tools.

1. get_lead_context
2. send_whatsapp
3. validate_kyc_doc
4. schedule_visit
5. check_settlement
6. search_policy
7. escalate_to_human
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List, Optional
from pydantic import BaseModel

from agent import settings
from agent.core import context_builder, handoff
from agent.domain.enums import (
    DocType,
    HandoffTarget,
    Language,
    LifecycleState,
)
from agent.policy.retrieval import search_policy as do_search_policy
from agent.ports import (
    Channel,
    Clock,
    DocValidationResult,
    DocumentChecker,
    KycResult,
    OutgoingMessage,
    ProfileForKyc,
    SendResult,
    Store,
)
from agent.tools.base import ToolResult, wrap_tool


# --- Tool 1: get_lead_context ---
def _get_lead_context(merchant_id: str, store: Store, clock: Clock) -> dict[str, Any]:
    bundle = store.get_context_bundle(merchant_id)
    ctx = context_builder.build(bundle, now=clock.now())
    return {"context": ctx.model_dump()}


get_lead_context = wrap_tool(_get_lead_context)


# --- Tool 2: send_whatsapp ---
def _send_whatsapp(
    merchant_id: str,
    channel: Channel,
    store: Store,
    text: str,
    language: Language,
    template_name: str | None = None,
    template_params: list[str] | None = None,
) -> dict[str, Any]:
    merchant = store.get_merchant(merchant_id)
    if not merchant:
        raise ValueError(f"Merchant not found: {merchant_id}")

    msg = OutgoingMessage(
        merchant_id=merchant_id,
        phone_e164=merchant.phone_e164,
        channel=merchant.preferred_channel if hasattr(merchant, "preferred_channel") else "simulator",
        text=text,
        template_name=template_name,
        template_params=template_params or [],
        language=language,
    )
    result: SendResult = channel.send_message(msg)
    if result.ok:
        store.save_message(
            merchant_id=merchant_id,
            direction="out",
            channel=str(msg.channel),
            kind="template" if result.used == "template" else "text",
            text=text,
            provider_message_id=result.provider_message_id,
        )
    return result.model_dump()


send_whatsapp = wrap_tool(_send_whatsapp)


# --- Tool 3: validate_kyc_doc ---
def _validate_kyc_doc(
    document_id: str,
    merchant_id: str,
    file_path: str,
    doc_type: DocType,
    doc_checker: DocumentChecker,
    store: Store,
) -> dict[str, Any]:
    merchant = store.get_merchant(merchant_id)
    if not merchant:
        raise ValueError(f"Merchant not found: {merchant_id}")

    profile = ProfileForKyc(owner_name=merchant.owner_name, shop_name=merchant.shop_name)
    val_result: DocValidationResult = doc_checker.validate_document(file_path, doc_type, profile)
    store.update_document_validation(document_id, val_result)

    kyc_res: KycResult | None = None
    if val_result.precheck_passed:
        kyc_res = doc_checker.submit_to_mock_kyc(document_id)

    return {
        "validation": val_result.model_dump(),
        "kyc": kyc_res.model_dump() if kyc_res else None,
    }


validate_kyc_doc = wrap_tool(_validate_kyc_doc)


# --- Tool 4: schedule_visit ---
def _schedule_visit(
    merchant_id: str,
    store: Store,
    clock: Clock,
    preferred_slot: str | None = None,
) -> dict[str, Any]:
    merchant = store.get_merchant(merchant_id)
    if not merchant:
        raise ValueError(f"Merchant not found: {merchant_id}")

    nearby = store.find_nearby_leads(
        merchant_id=merchant_id,
        radius_km=settings.VISIT_NEARBY_RADIUS_KM,
        states=[LifecycleState.DOCS_VERIFIED],
    )
    cluster_size = len(nearby) + 1  # includes current merchant

    # Slot planning: 11:00 next working day
    now = clock.now()
    next_day = now + timedelta(days=1)
    if next_day.weekday() >= 5:  # Weekend adjustment
        next_day += timedelta(days=(7 - next_day.weekday()))
    slot_time = next_day.replace(hour=settings.VISIT_START_HOUR, minute=0, second=0, microsecond=0)
    slot_start_str = slot_time.strftime("%Y-%m-%d %H:%M")

    fse_id = merchant.fse_id or "fse_default"
    visit_id = store.create_visit(
        merchant_id=merchant_id,
        fse_id=fse_id,
        slot_start=slot_start_str,
        cluster_size=cluster_size,
    )
    store.update_state(merchant_id, LifecycleState.VISIT_SCHEDULED, reason="FSE visit scheduled")

    return {
        "visit_id": visit_id,
        "fse_id": fse_id,
        "slot_start": slot_start_str,
        "cluster_size": cluster_size,
    }


schedule_visit = wrap_tool(_schedule_visit)


# --- Tool 5: check_settlement ---
def _check_settlement(merchant_id: str, store: Store) -> dict[str, Any]:
    settlement = store.get_settlement(merchant_id)
    if not settlement:
        return {"found": False}
    return {
        "found": True,
        "settlement": settlement.model_dump(),
    }


check_settlement = wrap_tool(_check_settlement)


# --- Tool 6: search_policy ---
def _search_policy(query: str, language: str = "english") -> dict[str, Any]:
    passages = do_search_policy(query=query, language=language)
    return {
        "passages": [
            {"source": p.source, "text": p.text, "score": p.score}
            for p in passages
        ]
    }


search_policy = wrap_tool(_search_policy)


# --- Tool 7: escalate_to_human ---
def _escalate_to_human(
    merchant_id: str,
    action_id: str,
    target: HandoffTarget,
    reason: str,
    store: Store,
    clock: Clock,
    decision: Any,
) -> dict[str, Any]:
    bundle = store.get_context_bundle(merchant_id)
    ctx = context_builder.build(bundle, now=clock.now())
    summary = handoff.build_summary(ctx, decision)

    handoff_id = store.create_handoff(
        merchant_id=merchant_id,
        action_id=action_id,
        target=target,
        reason=reason,
        summary=summary.model_dump(),
    )
    return {
        "handoff_id": handoff_id,
        "summary": summary.model_dump(),
    }


escalate_to_human = wrap_tool(_escalate_to_human)

