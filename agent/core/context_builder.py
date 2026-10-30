"""
agent/core/context_builder.py — Builds the rich Context object for the planner.

Calls store.get_context_bundle and shapes it into the Context the planner consumes.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from agent.domain.enums import Language, LifecycleState
from agent.ports import (
    ContextBundle,
    Counters,
    DocumentView,
    MessageView,
    MerchantView,
    SettlementView,
    Store,
    TicketView,
    VisitView,
)

if TYPE_CHECKING:
    pass


class DocsView(BaseModel):
    pan_status: str = "not_submitted"        # not_submitted, pending, failed, verified
    pan_attempts: int = 0
    pan_issues: list[str] = []
    address_status: str = "not_submitted"
    address_attempts: int = 0
    all_verified: bool = False


class ActivityView(BaseModel):
    txn_count: int = 0
    last_txn_at: datetime | None = None
    device_status: str | None = None
    installed_at: datetime | None = None


class Context(BaseModel):
    """The structured context consumed by the planner and guardrails."""
    merchant: MerchantView
    docs: DocsView
    activity: ActivityView
    open_tickets: list[TicketView]
    recent_messages: list[MessageView]
    counters: Counters
    settlement: SettlementView | None
    consent: bool
    now: datetime
    visits: list[VisitView]

    def to_compact_json(self) -> str:
        """Compact JSON for inclusion in LLM prompts. Keep under ~500 tokens."""
        import json
        return json.dumps({
            "merchant": {
                "id": self.merchant.id,
                "shop": self.merchant.shop_name,
                "owner": self.merchant.owner_name,
                "category": self.merchant.category,
                "area": self.merchant.area,
                "language": self.merchant.language,
                "state": self.merchant.state,
                "lead_score": self.merchant.lead_score,
            },
            "docs": {
                "pan": self.docs.pan_status,
                "pan_attempts": self.docs.pan_attempts,
                "pan_issues": self.docs.pan_issues,
                "address": self.docs.address_status,
            },
            "activity": {
                "txn_count": self.activity.txn_count,
                "device_status": self.activity.device_status,
            },
            "counters": self.counters.model_dump(),
            "settlement": self.settlement.model_dump() if self.settlement else None,
            "consent": self.consent,
            "recent_messages": [
                {
                    "direction": m.direction,
                    "text": (m.text or "")[:200],
                    "intent": m.intent,
                }
                for m in self.recent_messages[-5:]
            ],
        }, indent=2)


def _build_docs_view(documents: list[DocumentView]) -> DocsView:
    pan_doc = next((d for d in reversed(documents) if d.doc_type == "pan"), None)
    addr_doc = next((d for d in reversed(documents) if d.doc_type == "address_proof"), None)

    def _status(doc: DocumentView | None) -> str:
        if not doc:
            return "not_submitted"
        if doc.precheck_passed and doc.kyc_status == "approved":
            return "verified"
        if doc.precheck_passed:
            return "precheck_passed"
        if doc.quality and doc.quality != "ok":
            return "failed"
        return "pending"

    return DocsView(
        pan_status=_status(pan_doc),
        pan_attempts=pan_doc.attempts if pan_doc else 0,
        pan_issues=pan_doc.issues if pan_doc else [],
        address_status=_status(addr_doc),
        address_attempts=addr_doc.attempts if addr_doc else 0,
        all_verified=(
            (pan_doc is not None and pan_doc.precheck_passed)
            and (addr_doc is not None and addr_doc.precheck_passed)
        ),
    )


def build(bundle: ContextBundle, now: datetime) -> Context:
    """Build a Context from a raw ContextBundle."""
    docs_view = _build_docs_view(bundle.documents)
    activity = ActivityView(
        txn_count=bundle.txn_count,
        last_txn_at=bundle.last_txn_at,
        device_status=bundle.device_status,
        installed_at=bundle.installed_at,
    )
    return Context(
        merchant=bundle.merchant,
        docs=docs_view,
        activity=activity,
        open_tickets=bundle.open_tickets,
        recent_messages=bundle.recent_messages,
        counters=bundle.counters,
        settlement=bundle.latest_settlement,
        consent=bundle.consent,
        now=now,
        visits=bundle.visits,
    )

