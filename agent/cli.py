"""
agent/cli.py — Agent CLI runner for testing scenarios.

Usage:
  python -m agent.cli scenario all
  python -m agent.cli scenario rahul
"""
import sys
import uuid
from datetime import datetime, timezone

from agent import (
    approve_action,
    configure,
    handle_incoming,
    handle_timer,
    reject_action,
)
from agent.domain.enums import (
    ActionStatus,
    ActionType,
    Channel,
    DocQuality,
    DocType,
    Language,
    LifecycleState,
)
from agent.fakes import FakeChannel, FakeDocs, FakeStore, FixedClock
from agent.ports import IncomingEvent, MerchantView, SettlementView


def run_scenario(name: str) -> bool:
    clock = FixedClock()
    store = FakeStore(clock=clock)
    channel = FakeChannel()
    docs = FakeDocs()
    configure(store=store, channel=channel, documents=docs, clock=clock)

    print(f"--- Running Scenario: {name.upper()} ---")

    if name.lower() == "rahul":
        # AG-S1: Rahul Kirana Store
        # State: CONTACTED -> asks fee -> ANSWER_QUERY -> agrees visit -> SCHEDULE_VISIT -> VISIT_SCHEDULED
        rahul = MerchantView(
            id="m_rahul",
            shop_name="Rahul Kirana Store",
            owner_name="Rahul Sharma",
            category="kirana",
            city="Delhi",
            area="Rohini",
            language=Language.HINDI,
            phone_e164="+919811100001",
            state=LifecycleState.CONTACTED,
            lead_score=85.0,
            score_explanation="high footfall",
            footfall_score=0.9,
            fse_id="fse_delhi",
        )
        store.add_merchant(rahul)

        # 1. Ask fee
        ev1 = IncomingEvent(
            event_id=f"ev_{uuid.uuid4().hex[:6]}",
            channel=Channel.SIMULATOR,
            kind="text",
            phone_e164=rahul.phone_e164,
            text="Soundbox ke monthly fees kitne hain?",
            received_at=clock.now(),
        )
        res1 = handle_incoming(ev1)
        assert res1.actions[0].action_type == ActionType.ANSWER_QUERY
        assert res1.state_after == LifecycleState.ENGAGED

        # 2. Agree visit
        ev2 = IncomingEvent(
            event_id=f"ev_{uuid.uuid4().hex[:6]}",
            channel=Channel.SIMULATOR,
            kind="text",
            phone_e164=rahul.phone_e164,
            text="Theek hai, visit schedule kar do",
            received_at=clock.now(),
        )
        res2 = handle_incoming(ev2)
        assert res2.actions[0].action_type == ActionType.SCHEDULE_VISIT
        assert res2.state_after == LifecycleState.VISIT_SCHEDULED
        print("[PASS] Rahul scenario completed successfully.")
        return True

    elif name.lower() == "meena":
        # AG-S2: Meena blurry PAN then clear PAN
        meena = MerchantView(
            id="m_meena",
            shop_name="Meena Beauty Salon",
            owner_name="Meena Devi",
            category="salon",
            city="Noida",
            area="Sector 18",
            language=Language.HINGLISH,
            phone_e164="+919811100002",
            state=LifecycleState.DOCS_PENDING,
            lead_score=72.0,
            score_explanation="good engagement",
            footfall_score=0.7,
            fse_id="fse_noida",
        )
        store.add_merchant(meena)

        # 1. Blurry PAN
        ev1 = IncomingEvent(
            event_id=f"ev_{uuid.uuid4().hex[:6]}",
            channel=Channel.SIMULATOR,
            kind="media",
            phone_e164=meena.phone_e164,
            text=None,
            media_path="meena_pan_blurry.jpg",
            received_at=clock.now(),
        )
        res1 = handle_incoming(ev1)
        assert res1.actions[0].action_type == ActionType.REREQUEST_DOC

        # 2. Clear PAN
        ev2 = IncomingEvent(
            event_id=f"ev_{uuid.uuid4().hex[:6]}",
            channel=Channel.SIMULATOR,
            kind="media",
            phone_e164=meena.phone_e164,
            text=None,
            media_path="meena_pan_clear.jpg",
            received_at=clock.now(),
        )
        res2 = handle_incoming(ev2)
        assert res2.actions[0].action_type == ActionType.SCHEDULE_VISIT
        assert res2.state_after == LifecycleState.VISIT_SCHEDULED
        print("[PASS] Meena scenario completed successfully.")
        return True

    elif name.lower() == "sunil":
        # AG-S3: Sunil installed, 2 nudges, then escalation
        sunil = MerchantView(
            id="m_sunil",
            shop_name="Sunil Chai Point",
            owner_name="Sunil Yadav",
            category="chai stall",
            city="Gurugram",
            area="Sector 14",
            language=Language.HINDI,
            phone_e164="+919811100003",
            state=LifecycleState.INSTALLED,
            lead_score=60.0,
            score_explanation="low footfall",
            footfall_score=0.6,
            fse_id="fse_gurugram",
        )
        store.add_merchant(sunil)

        # Nudge 1
        res1 = handle_timer(sunil.id, "activation_check")
        assert res1.actions[0].action_type == ActionType.SEND_ACTIVATION_NUDGE

        # Nudge 2
        res2 = handle_timer(sunil.id, "activation_check")
        assert res2.actions[0].action_type == ActionType.SEND_ACTIVATION_NUDGE

        # Escalation
        res3 = handle_timer(sunil.id, "activation_check")
        assert res3.actions[0].action_type == ActionType.ESCALATE
        assert res3.state_after == LifecycleState.AT_RISK
        print("[PASS] Sunil scenario completed successfully.")
        return True

    elif name.lower() == "farida":
        # AG-S4: Farida settlement check
        farida = MerchantView(
            id="m_farida",
            shop_name="Farida Sweets",
            owner_name="Farida Khan",
            category="sweet shop",
            city="Ghaziabad",
            area="Indirapuram",
            language=Language.HINGLISH,
            phone_e164="+919811100004",
            state=LifecycleState.ACTIVATED,
            lead_score=88.0,
            score_explanation="active merchant",
            footfall_score=0.8,
            fse_id="fse_ghaziabad",
        )
        store.add_merchant(farida)
        store.set_settlement(
            farida.id,
            SettlementView(
                id="st_123",
                amount=4820.0,
                expected_date="tomorrow",
                status="delayed",
                delay_reason="bank holiday",
            ),
        )

        ev = IncomingEvent(
            event_id=f"ev_{uuid.uuid4().hex[:6]}",
            channel=Channel.SIMULATOR,
            kind="text",
            phone_e164=farida.phone_e164,
            text="Mera settlement nahi aaya abhi tak",
            received_at=clock.now(),
        )
        res = handle_incoming(ev)
        assert res.actions[0].action_type == ActionType.EXPLAIN_SETTLEMENT
        assert "bank holiday" in channel.last_sent.text.lower()
        print("[PASS] Farida scenario completed successfully.")
        return True

    elif name.lower() == "vikram":
        # AG-S5: Vikram demands discount -> OFFER_DISCOUNT hold L2 -> approve
        vikram = MerchantView(
            id="m_vikram",
            shop_name="Vikram Mobile Repair",
            owner_name="Vikram Singh",
            category="mobile repair",
            city="Delhi",
            area="Lajpat Nagar",
            language=Language.HINGLISH,
            phone_e164="+919811100005",
            state=LifecycleState.ENGAGED,
            lead_score=65.0,
            score_explanation="moderate",
            footfall_score=0.6,
            fse_id="fse_delhi",
        )
        store.add_merchant(vikram)

        ev = IncomingEvent(
            event_id=f"ev_{uuid.uuid4().hex[:6]}",
            channel=Channel.SIMULATOR,
            kind="text",
            phone_e164=vikram.phone_e164,
            text="Mujhe rental fee me discount chahiye ya device wapas le jao",
            received_at=clock.now(),
        )
        res = handle_incoming(ev)
        act = res.actions[0]
        assert act.action_type == ActionType.OFFER_DISCOUNT
        assert act.status == ActionStatus.PENDING_APPROVAL

        # Approve action
        app_res = approve_action(act.id, by="manager_amit")
        assert app_res.actions[0].status == ActionStatus.EXECUTED
        print("[PASS] Vikram scenario completed successfully.")
        return True

    elif name.lower() == "pooja":
        # AG-S6: Pooja first intro
        pooja = MerchantView(
            id="m_pooja",
            shop_name="Pooja Medical",
            owner_name="Pooja Verma",
            category="pharmacy",
            city="Noida",
            area="Sector 62",
            language=Language.ENGLISH,
            phone_e164="+919811100006",
            state=LifecycleState.NEW,
            lead_score=75.0,
            score_explanation="pharmacy lead",
            footfall_score=0.8,
            fse_id="fse_noida",
        )
        store.add_merchant(pooja)

        from agent.core import context_builder, executor, guardrails, planner

        bundle = store.get_context_bundle(pooja.id)
        ctx = context_builder.build(bundle, now=clock.now())
        dec = planner.PlannerDecision(
            action=ActionType.SEND_INTRO,
            params={},
            language=Language.ENGLISH,
            reasoning="New lead outreach",
            confidence=1.0,
            source="rule",
        )
        guard_res = guardrails.evaluate(dec, ctx, store=store)
        act_id = store.save_action(
            merchant_id=pooja.id,
            action_type=dec.action,
            params=dec.params,
            reasoning=dec.reasoning,
            confidence=dec.confidence,
            source=dec.source,
            autonomy_level=guard_res.autonomy_level,
            guardrail_notes=guard_res.notes,
            prompt_version="v1",
        )
        reply_sent, st_after, _execution_status = executor.execute(
            dec, guard_res, act_id, ctx, store, channel, docs, clock
        )
        assert st_after == LifecycleState.CONTACTED
        assert reply_sent is True
        print("[PASS] Pooja scenario completed successfully.")
        return True

    print(f"Unknown scenario: {name}")
    return False


def main():
    target = sys.argv[2] if len(sys.argv) > 2 else "all"
    scenarios = ["rahul", "meena", "sunil", "farida", "vikram", "pooja"] if target == "all" else [target]

    all_ok = True
    for sc in scenarios:
        ok = run_scenario(sc)
        if not ok:
            all_ok = False

    if all_ok:
        print("\n>>> ALL SCENARIOS PASSED <<<")
    else:
        print("\n>>> SOME SCENARIOS FAILED <<<")
        sys.exit(1)


if __name__ == "__main__":
    main()
