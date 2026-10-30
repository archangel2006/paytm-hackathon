"""
agent/tests/test_agent_units.py — Unit Tests AG-01 to AG-14.
"""
from datetime import datetime, timezone
import pytest

from agent import settings
from agent.core import (
    autonomy,
    context_builder,
    guardrails,
    nlu,
    planner,
    scoring,
)
from agent.domain.enums import (
    ActionStatus,
    ActionType,
    AutonomyLevel,
    Channel,
    DocQuality,
    DocType,
    HandoffTarget,
    Intent,
    Language,
    LifecycleState,
)
from agent.domain.lifecycle import allowed_actions, is_legal_transition
from agent.fakes import FakeChannel, FakeDocs, FakeStore, FixedClock
from agent.ports import (
    Counters,
    DocValidationResult,
    IncomingEvent,
    MerchantView,
    ProfileForKyc,
    SettlementView,
)
from agent.tools import impl as tools


# --- AG-01: allowed_actions for every state ---
def test_ag_01_allowed_actions():
    assert ActionType.SEND_INTRO in allowed_actions(LifecycleState.NEW)
    assert ActionType.SCHEDULE_VISIT in allowed_actions(LifecycleState.DOCS_VERIFIED)
    assert ActionType.SEND_ACTIVATION_NUDGE in allowed_actions(LifecycleState.INSTALLED)
    assert ActionType.OFFER_DISCOUNT in allowed_actions(LifecycleState.ENGAGED)
    assert ActionType.SEND_INTRO not in allowed_actions(LifecycleState.VISIT_SCHEDULED)


# --- AG-02: Planner retry & fallback ---
def test_ag_02_planner_fallback():
    clock = FixedClock()
    store = FakeStore(clock=clock)
    m = MerchantView(
        id="m_test",
        shop_name="Test",
        owner_name="Test Owner",
        category="kirana",
        city="Delhi",
        area="Rohini",
        language=Language.ENGLISH,
        phone_e164="+919999999999",
        state=LifecycleState.NEW,
        lead_score=50.0,
        score_explanation="",
        footfall_score=0.5,
        fse_id="fse_1",
    )
    store.add_merchant(m)
    bundle = store.get_context_bundle(m.id)
    ctx = context_builder.build(bundle, now=clock.now())
    # Unknown/nonsense input falls back safely or escalates
    dec = planner.decide(context=ctx, nlu=nlu.NluResult(intent=Intent.OTHER, language=Language.ENGLISH, sentiment=0.0, wants_human=False, mentions_money=False, confidence=0.1))
    assert dec.action in allowed_actions(LifecycleState.NEW) or dec.action == ActionType.ESCALATE


# --- AG-03: Short-circuit rules ---
def test_ag_03_short_circuit_rules():
    clock = FixedClock()
    store = FakeStore(clock=clock)
    m = MerchantView(
        id="m_test",
        shop_name="Test",
        owner_name="Test Owner",
        category="kirana",
        city="Delhi",
        area="Rohini",
        language=Language.HINDI,
        phone_e164="+919999999999",
        state=LifecycleState.ENGAGED,
        lead_score=50.0,
        score_explanation="",
        footfall_score=0.5,
        fse_id="fse_1",
    )
    store.add_merchant(m)
    bundle = store.get_context_bundle(m.id)
    ctx = context_builder.build(bundle, now=clock.now())

    # Wants human -> ESCALATE
    nlu_human = nlu.NluResult(intent=Intent.ASK_HUMAN, language=Language.HINDI, sentiment=-0.8, wants_human=True, mentions_money=False, confidence=1.0)
    dec = planner.decide(context=ctx, nlu=nlu_human)
    assert dec.action == ActionType.ESCALATE
    assert dec.source == "rule"

    # Ask discount -> OFFER_DISCOUNT
    nlu_disc = nlu.NluResult(intent=Intent.ASK_DISCOUNT, language=Language.HINDI, sentiment=0.0, wants_human=False, mentions_money=True, confidence=1.0)
    dec2 = planner.decide(context=ctx, nlu=nlu_disc)
    assert dec2.action == ActionType.OFFER_DISCOUNT
    assert dec2.source == "rule"


# --- AG-04: Guardrails evaluation ---
def test_ag_04_guardrails_blocks_and_escalation():
    clock = FixedClock()
    store = FakeStore(clock=clock)
    m = MerchantView(
        id="m_test",
        shop_name="Test",
        owner_name="Test",
        category="kirana",
        city="Delhi",
        area="Rohini",
        language=Language.ENGLISH,
        phone_e164="+919999999999",
        state=LifecycleState.CONTACTED,
        lead_score=50.0,
        score_explanation="",
        footfall_score=0.5,
        fse_id="fse_1",
    )
    store.add_merchant(m, consent=False)
    bundle = store.get_context_bundle(m.id)
    ctx = context_builder.build(bundle, now=clock.now())

    # No consent -> block
    dec = planner.PlannerDecision(action=ActionType.SEND_INTRO, params={}, language=Language.ENGLISH, reasoning="test", confidence=1.0, source="rule")
    res = guardrails.evaluate(dec, ctx, store=store, now=clock.now())
    assert res.verdict == "block"
    assert res.status == ActionStatus.BLOCKED


# --- AG-05: Autonomy levels (L1, L2, L3) ---
def test_ag_05_autonomy_levels():
    clock = FixedClock()
    store = FakeStore(clock=clock)
    m = MerchantView(
        id="m_test",
        shop_name="Test",
        owner_name="Test",
        category="kirana",
        city="Delhi",
        area="Rohini",
        language=Language.ENGLISH,
        phone_e164="+919999999999",
        state=LifecycleState.ENGAGED,
        lead_score=50.0,
        score_explanation="",
        footfall_score=0.5,
        fse_id="fse_1",
    )
    store.add_merchant(m)
    bundle = store.get_context_bundle(m.id)
    ctx = context_builder.build(bundle, now=clock.now())

    # L3 action
    store.set_autonomy_level(ActionType.ANSWER_QUERY, AutonomyLevel.L3)
    dec_l3 = planner.PlannerDecision(action=ActionType.ANSWER_QUERY, params={}, language=Language.ENGLISH, reasoning="test", confidence=1.0, source="rule")
    assert guardrails.evaluate(dec_l3, ctx, store=store).verdict == "run"

    # L2 action
    store.set_autonomy_level(ActionType.ANSWER_QUERY, AutonomyLevel.L2)
    assert guardrails.evaluate(dec_l3, ctx, store=store).verdict == "hold"

    # L1 action
    store.set_autonomy_level(ActionType.ANSWER_QUERY, AutonomyLevel.L1)
    assert guardrails.evaluate(dec_l3, ctx, store=store).verdict == "hold"


# --- AG-06: Grounded claim check ---
def test_ag_06_grounded_claim_check():
    clock = FixedClock()
    store = FakeStore(clock=clock)
    m = MerchantView(
        id="m_test",
        shop_name="Test",
        owner_name="Test",
        category="kirana",
        city="Delhi",
        area="Rohini",
        language=Language.ENGLISH,
        phone_e164="+919999999999",
        state=LifecycleState.ENGAGED,
        lead_score=50.0,
        score_explanation="",
        footfall_score=0.5,
        fse_id="fse_1",
    )
    store.add_merchant(m)
    bundle = store.get_context_bundle(m.id)
    ctx = context_builder.build(bundle, now=clock.now())

    dec = planner.PlannerDecision(action=ActionType.ANSWER_QUERY, params={}, language=Language.ENGLISH, reasoning="test", confidence=1.0, source="rule")
    res = guardrails.evaluate(
        decision=dec,
        context=ctx,
        store=store,
        tool_outputs={"policy": "rental is ₹125"},
        proposed_text="Your rental fee is ₹9999",  # Ungrounded fee
    )
    assert res.verdict == "block"


# --- AG-07: Policy search ---
def test_ag_07_policy_search():
    res = tools.search_policy("What are the Soundbox rental fees?")
    assert res.ok is True
    assert len(res.data["passages"]) > 0

    res_nonsense = tools.search_policy("xyzaaabbbzzz nonsense string query")
    assert res_nonsense.ok is True
    assert len(res_nonsense.data["passages"]) == 0


def test_query_reply_uses_gemini_with_retrieved_policy(monkeypatch):
    from agent.core import entrypoint
    from agent.policy.retrieval import PolicyPassage

    passage = PolicyPassage(
        source="fees.md > Soundbox Rental",
        text="Monthly rental is ₹125.",
        score=1.0,
    )
    captured_prompts = []
    monkeypatch.setattr(entrypoint, "search_policy", lambda query, language: [passage])
    monkeypatch.setattr(
        entrypoint,
        "generate_text",
        lambda prompt: captured_prompts.append(prompt) or "The monthly rental is ₹125.",
    )

    reply, tool_outputs = entrypoint._prepare_query_reply(
        query="What is the monthly rental?",
        merchant_name="Test Shop",
        language=Language.ENGLISH,
    )

    assert reply == "The monthly rental is ₹125."
    assert tool_outputs == {"policy": ["Monthly rental is ₹125."]}
    assert "What is the monthly rental?" in captured_prompts[0]
    assert "Monthly rental is ₹125." in captured_prompts[0]


def test_query_reply_uses_grounded_policy_when_gemini_is_unavailable(monkeypatch):
    from agent.core import entrypoint
    from agent.core.llm_client import LLMUnavailable
    from agent.policy.retrieval import PolicyPassage

    passage = PolicyPassage(
        source="fees.md > Soundbox Rental",
        text="Monthly rental is ₹125.",
        score=1.0,
    )
    monkeypatch.setattr(entrypoint, "search_policy", lambda query, language: [passage])

    def fail_generation(prompt):
        raise LLMUnavailable("provider unavailable")

    monkeypatch.setattr(entrypoint, "generate_text", fail_generation)

    reply, tool_outputs = entrypoint._prepare_query_reply(
        query="What is the monthly rental?",
        merchant_name="Test Shop",
        language=Language.ENGLISH,
    )

    assert reply == "Regarding Test Shop: Monthly rental is ₹125."
    assert tool_outputs == {"policy": ["Monthly rental is ₹125."]}


def test_query_reply_does_not_invent_when_policy_has_no_match(monkeypatch):
    from agent.core import entrypoint

    monkeypatch.setattr(entrypoint, "search_policy", lambda query, language: [])
    monkeypatch.setattr(
        entrypoint,
        "generate_text",
        lambda prompt: pytest.fail("Gemini must not answer without verified policy"),
    )

    reply, tool_outputs = entrypoint._prepare_query_reply(
        query="What is an unrelated policy?",
        merchant_name="Test Shop",
        language=Language.ENGLISH,
    )

    assert "couldn't find verified information" in reply
    assert tool_outputs == {"policy": []}


# --- AG-08: Schedule visit cluster size ---
def test_ag_08_schedule_visit_cluster():
    clock = FixedClock()
    store = FakeStore(clock=clock)
    m = MerchantView(
        id="m_rahul",
        shop_name="Shop",
        owner_name="Rahul",
        category="kirana",
        city="Delhi",
        area="Rohini",
        language=Language.HINDI,
        phone_e164="+919811100001",
        state=LifecycleState.DOCS_VERIFIED,
        lead_score=80.0,
        score_explanation="",
        footfall_score=0.8,
        fse_id="fse_delhi",
    )
    store.add_merchant(m)
    # 3 nearby verified leads
    nearby = [
        MerchantView(id=f"m_{i}", shop_name=f"Shop {i}", owner_name=f"Owner {i}", category="kirana", city="Delhi", area="Rohini", language=Language.HINDI, phone_e164=f"+91980000000{i}", state=LifecycleState.DOCS_VERIFIED, lead_score=80.0, score_explanation="", footfall_score=0.8, fse_id="fse_delhi")
        for i in range(1, 4)
    ]
    store.set_nearby_leads(nearby)

    res = tools.schedule_visit(merchant_id=m.id, store=store, clock=clock)
    assert res.ok is True
    assert res.data["cluster_size"] == 4


# --- AG-09: Lead scoring ---
def test_ag_09_lead_scoring():
    m = MerchantView(
        id="m_high",
        shop_name="Super Kirana",
        owner_name="Owner",
        category="kirana",
        city="Delhi",
        area="Rohini",
        language=Language.HINDI,
        phone_e164="+919800000010",
        state=LifecycleState.ENGAGED,
        lead_score=0.0,
        score_explanation="",
        footfall_score=1.0,
        fse_id="fse_1",
    )
    store = FakeStore()
    store.add_merchant(m)
    bundle = store.get_context_bundle(m.id)
    score, exp = scoring.score_merchant(bundle, nearby_count=4)
    assert score > 50.0
    assert len(exp) > 0


# --- AG-10: Idempotency ---
def test_ag_10_idempotency():
    from agent.core.entrypoint import configure, handle_incoming
    clock = FixedClock()
    store = FakeStore(clock=clock)
    channel = FakeChannel()
    docs = FakeDocs()
    configure(store=store, channel=channel, documents=docs, clock=clock)

    ev = IncomingEvent(
        event_id="evt_same_123",
        channel=Channel.SIMULATOR,
        kind="text",
        phone_e164="+919811100099",
        text="Hello",
        received_at=clock.now(),
    )
    res1 = handle_incoming(ev)
    res2 = handle_incoming(ev)
    assert len(res2.actions) == 0  # second run does not duplicate


# --- AG-11: LLM timeout & NLU keyword fallback ---
def test_ag_11_nlu_keyword_fallback():
    res = nlu.classify("manager se baat karao", force_keywords=True)
    assert res.intent == Intent.ASK_HUMAN
    assert res.wants_human is True


# --- AG-12: Opt-out ---
def test_ag_12_opt_out():
    from agent.core.entrypoint import configure, handle_incoming
    clock = FixedClock()
    store = FakeStore(clock=clock)
    channel = FakeChannel()
    docs = FakeDocs()
    configure(store=store, channel=channel, documents=docs, clock=clock)

    m = MerchantView(
        id="m_opt",
        shop_name="Opt Shop",
        owner_name="Opt Owner",
        category="kirana",
        city="Delhi",
        area="Rohini",
        language=Language.HINDI,
        phone_e164="+919800000020",
        state=LifecycleState.CONTACTED,
        lead_score=50.0,
        score_explanation="",
        footfall_score=0.5,
        fse_id="fse_1",
    )
    store.add_merchant(m)

    ev = IncomingEvent(
        event_id="evt_stop",
        channel=Channel.SIMULATOR,
        kind="text",
        phone_e164=m.phone_e164,
        text="stop mat bhejo message",
        received_at=clock.now(),
    )
    res = handle_incoming(ev)
    assert res.actions[0].action_type == ActionType.WAIT


# --- AG-13: Retry limits ---
def test_ag_13_retry_limits():
    clock = FixedClock()
    store = FakeStore(clock=clock)
    m = MerchantView(
        id="m_retry",
        shop_name="Retry Shop",
        owner_name="Retry",
        category="kirana",
        city="Delhi",
        area="Rohini",
        language=Language.HINDI,
        phone_e164="+919800000030",
        state=LifecycleState.INSTALLED,
        lead_score=50.0,
        score_explanation="",
        footfall_score=0.5,
        fse_id="fse_1",
    )
    store.add_merchant(m)
    # simulate 2 nudges already sent
    store.save_action(m.id, ActionType.SEND_ACTIVATION_NUDGE, {}, "n1", 1.0, "rule", AutonomyLevel.L3, [], "v1")
    store.save_action(m.id, ActionType.SEND_ACTIVATION_NUDGE, {}, "n2", 1.0, "rule", AutonomyLevel.L3, [], "v1")
    for a in store.get_actions_for(m.id):
        store.update_action_status(a["id"], ActionStatus.EXECUTED)

    from agent.core.entrypoint import configure, handle_timer
    configure(store=store, channel=FakeChannel(), documents=FakeDocs(), clock=clock)
    res = handle_timer(m.id, "activation_check")
    assert res.actions[0].action_type == ActionType.ESCALATE


# --- AG-14: Quiet hours ---
def test_ag_14_quiet_hours():
    clock = FixedClock(fixed_time=datetime(2026, 10, 30, 22, 0, 0, tzinfo=timezone.utc))
    store = FakeStore(clock=clock)
    m = MerchantView(
        id="m_quiet",
        shop_name="Quiet",
        owner_name="Owner",
        category="kirana",
        city="Delhi",
        area="Rohini",
        language=Language.ENGLISH,
        phone_e164="+919800000040",
        state=LifecycleState.NEW,
        lead_score=50.0,
        score_explanation="",
        footfall_score=0.5,
        fse_id="fse_1",
    )
    store.add_merchant(m)
    bundle = store.get_context_bundle(m.id)
    ctx = context_builder.build(bundle, now=clock.now())
    dec = planner.PlannerDecision(action=ActionType.SEND_INTRO, params={}, language=Language.ENGLISH, reasoning="outreach", confidence=1.0, source="rule")

    res = guardrails.evaluate(dec, ctx, store=store, now=clock.now())
    assert res.verdict == "block"
    assert res.status == ActionStatus.BLOCKED


def test_hinglish_fee_query_retrieves_soundbox_rental_policy():
    from agent.policy.retrieval import search_policy

    passages = search_policy("Soundbox lena hai, fees kya hain?")

    assert passages
    assert passages[0].source.startswith("fees.md > Soundbox Rental")
    assert "125" in passages[0].text


def test_failed_outbound_message_is_reported_without_advancing_lead():
    from agent.core.entrypoint import configure, handle_incoming

    clock = FixedClock()
    store = FakeStore(clock=clock)
    configure(store=store, channel=FakeChannel(fail=True), documents=FakeDocs(), clock=clock)
    event = IncomingEvent(
        event_id="evt_failed_outbound",
        channel=Channel.SIMULATOR,
        kind="text",
        phone_e164="+919800000099",
        text="Soundbox fees kya hain?",
        received_at=clock.now(),
    )

    result = handle_incoming(event)

    assert result.reply_sent is False
    assert result.state_after == LifecycleState.NEW
    assert result.actions[0].status == ActionStatus.FAILED
