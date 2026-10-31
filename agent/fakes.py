"""
agent/fakes.py — In-memory fakes for all agent ports.

Used by:
  - Agent tests (yourself)
  - Integrations tests (Person 1)
  - Platform tests (Person 3)

All fakes are deterministic and stateful in-memory implementations.
No network, no filesystem, no database required.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal

from agent.domain.enums import (
    ActionStatus,
    ActionType,
    AutonomyLevel,
    Channel,
    DocQuality,
    DocType,
    HandoffTarget,
    Language,
    LifecycleState,
)
from agent.ports import (
    ActionSummary,
    AgentResult,
    ContextBundle,
    Counters,
    DocValidationResult,
    DocumentView,
    KycResult,
    MessageView,
    MerchantView,
    OutgoingMessage,
    ProfileForKyc,
    SendResult,
    SettlementView,
    TicketView,
    VisitView,
)


# ─────────────────────────────────────────────────────────────
# FixedClock
# ─────────────────────────────────────────────────────────────


class FixedClock:
    """Clock that always returns the same time. Use for deterministic tests."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._time = fixed_time or datetime(2026, 10, 30, 10, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._time

    def set(self, dt: datetime) -> None:
        self._time = dt


# ─────────────────────────────────────────────────────────────
# FakeChannel
# ─────────────────────────────────────────────────────────────


class FakeChannel:
    """Records all sent messages. Always succeeds unless told to fail."""

    def __init__(self, fail: bool = False) -> None:
        self.sent: list[OutgoingMessage] = []
        self._fail = fail

    def send_message(self, msg: OutgoingMessage) -> SendResult:
        if self._fail:
            return SendResult(ok=False, used="none", error_code="FAKE_FAIL", error_message="Fake failure")
        self.sent.append(msg)
        return SendResult(ok=True, provider_message_id=f"fake_{uuid.uuid4().hex[:8]}", used="text")

    @property
    def last_sent(self) -> OutgoingMessage | None:
        return self.sent[-1] if self.sent else None

    def reset(self) -> None:
        self.sent.clear()


# ─────────────────────────────────────────────────────────────
# FakeDocs
# ─────────────────────────────────────────────────────────────


class FakeDocs:
    """
    Fake document checker.
    - Returns ok for any file path that ends with 'clear' or 'ok'.
    - Returns blurry for any path containing 'blurry'.
    - Otherwise ok.
    - mock_kyc returns approved unless owner_name contains 'REJECT'.
    """

    def validate_document(
        self,
        file_path: str,
        doc_type: DocType,
        profile: ProfileForKyc,
    ) -> DocValidationResult:
        path_lower = (file_path or "").lower()
        if "blurry" in path_lower:
            return DocValidationResult(
                quality=DocQuality.BLURRY,
                sharpness_score=10.0,
                extracted_pan=None,
                pan_format_valid=False,
                name_match=None,
                issues=["blurry"],
                precheck_passed=False,
            )
        if "cropped" in path_lower:
            return DocValidationResult(
                quality=DocQuality.UNREADABLE,
                sharpness_score=50.0,
                extracted_pan=None,
                pan_format_valid=False,
                name_match=None,
                issues=["pan_not_found"],
                precheck_passed=False,
            )
        # Default: clear / ok
        return DocValidationResult(
            quality=DocQuality.OK,
            sharpness_score=200.0,
            extracted_pan="ABCDE1234F",
            pan_format_valid=True,
            name_match=True,
            issues=[],
            precheck_passed=True,
        )

    def submit_to_mock_kyc(self, document_id: str) -> KycResult:
        return KycResult(status="approved", reference_id=f"MOCKKYC-{document_id}")


# ─────────────────────────────────────────────────────────────
# FakeStore
# ─────────────────────────────────────────────────────────────


_DEFAULT_AUTONOMY: dict[ActionType, AutonomyLevel] = {
    ActionType.SEND_INTRO: AutonomyLevel.L3,
    ActionType.ANSWER_QUERY: AutonomyLevel.L3,
    ActionType.REQUEST_DOCS: AutonomyLevel.L3,
    ActionType.REREQUEST_DOC: AutonomyLevel.L3,
    ActionType.SCHEDULE_VISIT: AutonomyLevel.L3,
    ActionType.SEND_ACTIVATION_NUDGE: AutonomyLevel.L3,
    ActionType.EXPLAIN_SETTLEMENT: AutonomyLevel.L3,
    ActionType.WAIT: AutonomyLevel.L3,
    ActionType.ESCALATE: AutonomyLevel.L3,
    ActionType.CLOSE_LEAD: AutonomyLevel.L1,
    ActionType.OFFER_DISCOUNT: AutonomyLevel.L2,
}


class FakeStore:
    """
    Fully in-memory store. Stateful — use reset() between tests.
    Implements agent.ports.Store.
    """

    def __init__(self, clock: FixedClock | None = None) -> None:
        self._clock = clock or FixedClock()
        self.reset()

    def reset(self) -> None:
        self._merchants: dict[str, MerchantView] = {}
        self._phone_index: dict[str, str] = {}          # phone_e164 → merchant_id
        self._messages: dict[str, list[dict]] = defaultdict(list)
        self._documents: dict[str, dict] = {}           # document_id → record
        self._merchant_docs: dict[str, list[str]] = defaultdict(list)  # merchant_id → [doc_id]
        self._actions: dict[str, dict] = {}             # action_id → record
        self._handoffs: dict[str, dict] = {}
        self._settlements: dict[str, SettlementView] = {}  # merchant_id → latest
        self._visits: dict[str, list[VisitView]] = defaultdict(list)
        self._processed_events: set[str] = set()
        self._audit_log: list[dict] = []
        self._scheduled_jobs: list[dict] = []
        self._autonomy: dict[ActionType, AutonomyLevel] = dict(_DEFAULT_AUTONOMY)
        self._consent: dict[str, bool] = {}
        self._states: dict[str, LifecycleState] = {}
        self._scores: dict[str, tuple[float, str]] = {}
        self._nearby_leads_stub: list[MerchantView] = []

    # ── Merchant ──────────────────────────────────────────────

    def add_merchant(self, merchant: MerchantView, consent: bool = True) -> None:
        """Helper for tests: seed a merchant directly."""
        self._merchants[merchant.id] = merchant
        self._phone_index[merchant.phone_e164] = merchant.id
        self._consent[merchant.id] = consent
        self._states[merchant.id] = merchant.state

    def get_merchant_by_phone(self, phone_e164: str) -> MerchantView | None:
        mid = self._phone_index.get(phone_e164)
        return self._merchants.get(mid) if mid else None

    def get_merchant(self, merchant_id: str) -> MerchantView | None:
        return self._merchants.get(merchant_id)

    def list_merchants(
        self,
        state: LifecycleState | None = None,
        limit: int = 120,
    ) -> list[MerchantView]:
        merchants = list(self._merchants.values())
        if state is not None:
            merchants = [merchant for merchant in merchants if merchant.state == state]
        return sorted(merchants, key=lambda merchant: merchant.lead_score, reverse=True)[:limit]

    def create_lead(
        self,
        phone_e164: str,
        channel: Channel,
        language_guess: Language,
    ) -> MerchantView:
        mid = f"m_{uuid.uuid4().hex[:8]}"
        merchant = MerchantView(
            id=mid,
            shop_name="Unknown Shop",
            owner_name="Unknown Owner",
            category="other",
            city="Delhi",
            area="Unknown",
            language=language_guess,
            phone_e164=phone_e164,
            state=LifecycleState.NEW,
            lead_score=0.0,
            score_explanation="new lead",
            footfall_score=0.5,
            fse_id="fse_default",
        )
        self._merchants[mid] = merchant
        self._phone_index[phone_e164] = mid
        self._consent[mid] = True
        self._states[mid] = LifecycleState.NEW
        return merchant

    def update_lead_score(self, merchant_id: str, score: float, explanation: str) -> None:
        self._scores[merchant_id] = (score, explanation)
        if merchant_id in self._merchants:
            m = self._merchants[merchant_id]
            self._merchants[merchant_id] = m.model_copy(
                update={"lead_score": score, "score_explanation": explanation}
            )

    # ── Idempotency ───────────────────────────────────────────

    def already_processed(self, event_id: str) -> bool:
        return event_id in self._processed_events

    # ── Messages ──────────────────────────────────────────────

    def save_message(
        self,
        merchant_id: str,
        direction: Literal["in", "out"],
        channel: str,
        kind: str,
        text: str | None,
        event_id: str | None = None,
        provider_message_id: str | None = None,
        intent: str | None = None,
        sentiment: float | None = None,
    ) -> str:
        if event_id and event_id in self._processed_events:
            # Find existing message
            for msg in self._messages[merchant_id]:
                if msg.get("event_id") == event_id:
                    return msg["id"]
        mid = f"msg_{uuid.uuid4().hex[:8]}"
        record = {
            "id": mid,
            "merchant_id": merchant_id,
            "direction": direction,
            "channel": channel,
            "kind": kind,
            "text": text,
            "event_id": event_id,
            "provider_message_id": provider_message_id,
            "intent": intent,
            "sentiment": sentiment,
            "created_at": self._clock.now(),
        }
        self._messages[merchant_id].append(record)
        if event_id:
            self._processed_events.add(event_id)
        return mid

    # ── Documents ─────────────────────────────────────────────

    def save_document(self, merchant_id: str, doc_type: DocType, file_path: str) -> str:
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        record = {
            "id": doc_id,
            "merchant_id": merchant_id,
            "doc_type": doc_type,
            "file_path": file_path,
            "quality": None,
            "sharpness_score": None,
            "extracted_pan": None,
            "name_match": None,
            "issues": [],
            "precheck_passed": False,
            "kyc_status": None,
            "kyc_reference": None,
            "attempts": 0,
        }
        self._documents[doc_id] = record
        self._merchant_docs[merchant_id].append(doc_id)
        return doc_id

    def update_document_validation(
        self,
        document_id: str,
        result: DocValidationResult,
        kyc_result=None,
    ) -> None:
        if document_id in self._documents:
            rec = self._documents[document_id]
            rec["quality"] = result.quality
            rec["sharpness_score"] = result.sharpness_score
            rec["extracted_pan"] = result.extracted_pan
            rec["name_match"] = result.name_match
            rec["issues"] = result.issues
            rec["precheck_passed"] = result.precheck_passed
            rec["kyc_status"] = kyc_result.status if kyc_result else "pending"
            rec["kyc_reference"] = kyc_result.reference_id if kyc_result else None
            rec["attempts"] = rec.get("attempts", 0) + 1

    # ── Context ───────────────────────────────────────────────

    def get_context_bundle(self, merchant_id: str) -> ContextBundle:
        merchant = self._merchants.get(merchant_id)
        if not merchant:
            raise KeyError(f"Merchant {merchant_id} not found")

        # Sync state
        state = self._states.get(merchant_id, merchant.state)
        merchant = merchant.model_copy(update={"state": state})
        score_data = self._scores.get(merchant_id)
        if score_data:
            merchant = merchant.model_copy(
                update={"lead_score": score_data[0], "score_explanation": score_data[1]}
            )

        # Documents
        doc_views = []
        for doc_id in self._merchant_docs.get(merchant_id, []):
            rec = self._documents.get(doc_id, {})
            doc_views.append(DocumentView(
                id=doc_id,
                doc_type=rec.get("doc_type", DocType.PAN),
                quality=rec.get("quality"),
                precheck_passed=rec.get("precheck_passed", False),
                kyc_status=rec.get("kyc_status"),
                attempts=rec.get("attempts", 0),
                issues=rec.get("issues", []),
            ))

        # Messages (last 10)
        all_msgs = self._messages.get(merchant_id, [])
        recent = all_msgs[-10:]
        msg_views = [
            MessageView(
                id=m["id"],
                direction=m["direction"],
                channel=m["channel"] if isinstance(m["channel"], Channel) else Channel(m["channel"].split(".")[-1].lower()),
                kind=m["kind"],
                text=m["text"],
                intent=m.get("intent"),
                sentiment=m.get("sentiment"),
                created_at=m["created_at"],
            )
            for m in recent
        ]

        # Counters
        now = self._clock.now()
        outbound_today = sum(
            1 for m in all_msgs
            if m["direction"] == "out"
            and isinstance(m["created_at"], datetime)
            and m["created_at"].date() == now.date()
        )
        contact_attempts = sum(
            1 for a in self._actions.values()
            if a.get("merchant_id") == merchant_id
            and a.get("action_type") in (ActionType.SEND_INTRO,)
        )
        nudges_sent = sum(
            1 for a in self._actions.values()
            if a.get("merchant_id") == merchant_id
            and a.get("action_type") == ActionType.SEND_ACTIVATION_NUDGE
            and a.get("status") == ActionStatus.EXECUTED
        )
        doc_rerequests = sum(
            1 for a in self._actions.values()
            if a.get("merchant_id") == merchant_id
            and a.get("action_type") == ActionType.REREQUEST_DOC
        )

        counters = Counters(
            contact_attempts=contact_attempts,
            nudges_sent=nudges_sent,
            doc_rerequests=doc_rerequests,
            messages_today=outbound_today,
        )

        return ContextBundle(
            merchant=merchant,
            documents=doc_views,
            txn_count=0,
            last_txn_at=None,
            device_status=None,
            installed_at=None,
            open_tickets=[],
            latest_settlement=self._settlements.get(merchant_id),
            recent_messages=msg_views,
            visits=self._visits.get(merchant_id, []),
            counters=counters,
            consent=self._consent.get(merchant_id, True),
        )

    # ── Actions ───────────────────────────────────────────────

    def save_action(
        self,
        merchant_id: str,
        action_type: ActionType,
        params: dict,
        reasoning: str,
        confidence: float,
        source: Literal["rule", "llm", "fallback"],
        autonomy_level: AutonomyLevel,
        guardrail_notes: list[str],
        prompt_version: str,
    ) -> str:
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        self._actions[action_id] = {
            "id": action_id,
            "merchant_id": merchant_id,
            "action_type": action_type,
            "params": params,
            "reasoning": reasoning,
            "confidence": confidence,
            "source": source,
            "autonomy_level": autonomy_level,
            "status": ActionStatus.PROPOSED,
            "guardrail_notes": guardrail_notes,
            "prompt_version": prompt_version,
            "created_at": self._clock.now(),
            "executed_at": None,
            "approved_by": None,
            "rejection_reason": None,
        }
        return action_id

    def update_action_status(
        self,
        action_id: str,
        status: ActionStatus,
        executed_at: datetime | None = None,
        approved_by: str | None = None,
        rejection_reason: str | None = None,
    ) -> None:
        if action_id in self._actions:
            self._actions[action_id]["status"] = status
            if executed_at:
                self._actions[action_id]["executed_at"] = executed_at
            if approved_by:
                self._actions[action_id]["approved_by"] = approved_by
            if rejection_reason:
                self._actions[action_id]["rejection_reason"] = rejection_reason

    def get_action(self, action_id: str) -> dict | None:
        """Helper for tests."""
        return self._actions.get(action_id)

    def get_actions_for(self, merchant_id: str) -> list[dict]:
        """Helper for tests."""
        return [a for a in self._actions.values() if a["merchant_id"] == merchant_id]

    # ── State ─────────────────────────────────────────────────

    def update_state(self, merchant_id: str, new_state: LifecycleState, reason: str) -> None:
        from agent.domain.lifecycle import is_legal_transition
        current = self._states.get(merchant_id)
        if current and not is_legal_transition(current, new_state):
            raise ValueError(
                f"Illegal state transition {current} → {new_state} for merchant {merchant_id}"
            )
        self._states[merchant_id] = new_state
        if merchant_id in self._merchants:
            self._merchants[merchant_id] = self._merchants[merchant_id].model_copy(
                update={"state": new_state}
            )
        self.write_audit(
            actor="agent",
            event_type="state_change",
            merchant_id=merchant_id,
            payload={"from": str(current), "to": str(new_state), "reason": reason},
        )

    def get_state(self, merchant_id: str) -> LifecycleState | None:
        """Helper for tests."""
        return self._states.get(merchant_id)

    # ── Visits ────────────────────────────────────────────────

    def create_visit(
        self,
        merchant_id: str,
        fse_id: str,
        slot_start: str,
        cluster_size: int,
    ) -> str:
        visit_id = f"vis_{uuid.uuid4().hex[:8]}"
        visit = VisitView(
            id=visit_id,
            fse_id=fse_id,
            slot_start=slot_start,
            status="scheduled",
            cluster_size=cluster_size,
        )
        self._visits[merchant_id].append(visit)
        return visit_id

    def find_nearby_leads(
        self,
        merchant_id: str,
        radius_km: float,
        states: list[LifecycleState],
    ) -> list[MerchantView]:
        """Return the stub nearby leads (set via set_nearby_leads for tests)."""
        return [
            m for m in self._nearby_leads_stub
            if m.id != merchant_id and m.state in states
        ]

    def set_nearby_leads(self, leads: list[MerchantView]) -> None:
        """Test helper: set what find_nearby_leads returns."""
        self._nearby_leads_stub = leads

    # ── Settlements ───────────────────────────────────────────

    def get_settlement(self, merchant_id: str) -> SettlementView | None:
        return self._settlements.get(merchant_id)

    def set_settlement(self, merchant_id: str, settlement: SettlementView) -> None:
        """Test helper: seed a settlement record."""
        self._settlements[merchant_id] = settlement

    # ── Handoffs ──────────────────────────────────────────────

    def create_handoff(
        self,
        merchant_id: str,
        action_id: str,
        target: HandoffTarget,
        reason: str,
        summary: dict,
    ) -> str:
        handoff_id = f"hof_{uuid.uuid4().hex[:8]}"
        self._handoffs[handoff_id] = {
            "id": handoff_id,
            "merchant_id": merchant_id,
            "action_id": action_id,
            "target": target,
            "reason": reason,
            "summary": summary,
            "status": "open",
            "created_at": self._clock.now(),
        }
        self.write_audit(
            actor="agent",
            event_type="handoff_created",
            merchant_id=merchant_id,
            payload={"handoff_id": handoff_id, "target": str(target), "reason": reason},
        )
        return handoff_id

    def get_handoffs(self) -> list[dict]:
        """Helper for tests."""
        return list(self._handoffs.values())

    # ── Autonomy ──────────────────────────────────────────────

    def get_autonomy_level(self, action_type: ActionType) -> AutonomyLevel:
        return self._autonomy.get(action_type, AutonomyLevel.L3)

    def set_autonomy_level(self, action_type: ActionType, level: AutonomyLevel) -> None:
        """Test helper: override autonomy levels."""
        self._autonomy[action_type] = level

    # ── Consent ───────────────────────────────────────────────

    def set_consent(self, merchant_id: str, consent: bool) -> None:
        self._consent[merchant_id] = consent

    def get_consent(self, merchant_id: str) -> bool:
        return self._consent.get(merchant_id, True)

    # ── Audit ─────────────────────────────────────────────────

    def write_audit(
        self,
        actor: str,
        event_type: str,
        merchant_id: str | None,
        payload: dict,
    ) -> None:
        self._audit_log.append({
            "id": f"aud_{uuid.uuid4().hex[:8]}",
            "actor": actor,
            "event_type": event_type,
            "merchant_id": merchant_id,
            "payload": payload,
            "created_at": self._clock.now(),
        })

    # ── Scheduler ─────────────────────────────────────────────

    def schedule_job(self, merchant_id: str, reason: str, run_at: datetime) -> None:
        self._scheduled_jobs.append({
            "id": f"job_{uuid.uuid4().hex[:8]}",
            "merchant_id": merchant_id,
            "reason": reason,
            "run_at": run_at,
            "status": "pending",
        })

    def get_scheduled_jobs(self) -> list[dict]:
        """Test helper."""
        return list(self._scheduled_jobs)
