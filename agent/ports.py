"""
agent/ports.py — Boundary models and Protocol interfaces.

This is the SINGLE SOURCE OF TRUTH for all types that cross the agent boundary.
- Integrations imports from here (IncomingEvent, OutgoingMessage, etc.)
- Server adapters implement the Protocols declared here.
- The agent imports nothing from integrations or server.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

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

# ─────────────────────────────────────────────────────────────
# Boundary Models — types that travel between areas
# ─────────────────────────────────────────────────────────────


class IncomingEvent(BaseModel):
    """Built by Integrations, consumed by the agent."""
    event_id: str                         # WhatsApp message id or uuid (idempotency key)
    merchant_id: str | None = None
    channel: Channel
    kind: Literal["text", "media", "voice", "audio"]
    phone_e164: str                       # normalised, e.g. +919876543210
    text: str | None = None               # for voice: the transcript
    media_path: str | None = None         # local file path after download
    mime_type: str | None = None
    document_type: DocType = DocType.PAN
    received_at: datetime


class OutgoingMessage(BaseModel):
    """Built by the agent, sent by Integrations."""
    merchant_id: str
    phone_e164: str
    channel: Channel
    text: str = ""                         # free-form, used when 24-hour window is open
    template_name: str | None = None      # approved template for when the window is closed
    template_params: list[str] = []
    language: Language = Language.HINDI


class SendResult(BaseModel):
    """Result of sending a message through the channel."""
    ok: bool
    provider_message_id: str | None = None
    used: Literal["text", "template", "none"] = "none"
    error_code: str | None = None
    error_detail: str | None = None

    @property
    def error_message(self) -> str | None:
        return self.error_detail


class ProfileForKyc(BaseModel):
    """Merchant profile passed to the document checker."""
    owner_name: str
    shop_name: str = ""
    merchant_id: str | None = None
    phone_e164: str | None = None


class DocValidationResult(BaseModel):
    """Result of the document pre-check (NOT KYC verification)."""
    quality: DocQuality
    sharpness_score: float = 0.0
    extracted_pan: str | None = None
    pan_format_valid: bool = False
    name_match: bool | None = None       # None when no name could be read
    issues: list[str] = []               # blurry, unreadable, pan_not_found, pan_format_invalid, name_mismatch
    precheck_passed: bool = False        # a pre-check, NEVER call this "KYC verified"


class KycResult(BaseModel):
    """Result from the mock KYC service."""
    status: Literal["submitted", "approved", "rejected"]
    reference_id: str | None = None


class ActionSummary(BaseModel):
    """Summary of an agent action, returned to callers."""
    id: str
    action_type: ActionType
    status: ActionStatus
    autonomy_level: AutonomyLevel
    reasoning: str


class AgentResult(BaseModel):
    """Result returned from any agent entrypoint."""
    merchant_id: str = ""
    actions: list[ActionSummary] = []
    reply_sent: bool = False
    state_after: LifecycleState = LifecycleState.NEW
    success: bool = True
    error: str | None = None


# ─────────────────────────────────────────────────────────────
# View Models — what the Store returns to the agent
# ─────────────────────────────────────────────────────────────


class MerchantView(BaseModel):
    """Merchant profile as seen by the agent."""
    id: str
    shop_name: str
    owner_name: str
    category: str
    city: str
    area: str
    language: Language
    phone_e164: str
    preferred_channel: Channel = Channel.WHATSAPP
    state: LifecycleState
    lead_score: float
    score_explanation: str
    footfall_score: float
    fse_id: str
    lat: float | None = None
    lng: float | None = None


class DocumentView(BaseModel):
    """Document record as seen by the agent."""
    id: str
    doc_type: DocType
    quality: DocQuality | None = None
    precheck_passed: bool = False
    kyc_status: str | None = None
    attempts: int = 0
    issues: list[str] = []


class MessageView(BaseModel):
    """A single message in the conversation history."""
    id: str
    direction: Literal["in", "out"]
    channel: Channel
    kind: str
    text: str | None
    intent: str | None = None
    sentiment: float | None = None
    created_at: datetime


class TicketView(BaseModel):
    """An open ticket."""
    id: str
    type: str
    status: str


class SettlementView(BaseModel):
    """Latest settlement record."""
    id: str
    amount: float
    expected_date: str | None
    status: str
    delay_reason: str | None


class VisitView(BaseModel):
    """A scheduled visit."""
    id: str
    fse_id: str
    slot_start: str
    status: str
    cluster_size: int


class Counters(BaseModel):
    """Per-merchant action counters."""
    contact_attempts: int = 0
    nudges_sent: int = 0
    doc_rerequests: int = 0
    messages_today: int = 0


class ContextBundle(BaseModel):
    """Raw bundle from the store; shaped into Context by context_builder."""
    merchant: MerchantView
    documents: list[DocumentView]
    txn_count: int
    last_txn_at: datetime | None
    device_status: str | None
    installed_at: datetime | None
    open_tickets: list[TicketView]
    latest_settlement: SettlementView | None
    recent_messages: list[MessageView]    # last 10, newest last
    visits: list[VisitView]
    counters: Counters
    consent: bool


# ─────────────────────────────────────────────────────────────
# Protocol Interfaces — the agent declares what it needs
# ─────────────────────────────────────────────────────────────


@runtime_checkable
class Channel(Protocol):  # type: ignore[no-redef]
    """Sends outbound messages to merchants."""

    def send_message(self, msg: OutgoingMessage) -> SendResult:
        ...


@runtime_checkable
class DocumentChecker(Protocol):
    """Validates documents and submits to the mock KYC service."""

    def validate_document(
        self,
        file_path: str,
        doc_type: DocType,
        profile: ProfileForKyc,
    ) -> DocValidationResult:
        ...

    def submit_to_mock_kyc(self, document_id: str) -> KycResult:
        ...


@runtime_checkable
class Clock(Protocol):
    """Provides the current time (injectable for demo day time travel)."""

    def now(self) -> datetime:
        ...


@runtime_checkable
class Store(Protocol):
    """
    All reads and writes of persisted data.
    The agent never sees SQL. It receives and returns the plain models defined here.
    """

    def get_merchant_by_phone(self, phone_e164: str) -> MerchantView | None:
        ...

    def get_merchant(self, merchant_id: str) -> MerchantView | None:
        ...

    def list_merchants(
        self,
        state: LifecycleState | None = None,
        limit: int = 120,
    ) -> list[MerchantView]:
        ...

    def create_lead(
        self,
        phone_e164: str,
        channel: Channel,
        language_guess: Language,
    ) -> MerchantView:
        ...

    def update_lead_score(
        self,
        merchant_id: str,
        score: float,
        explanation: str,
    ) -> None:
        ...

    def already_processed(self, event_id: str) -> bool:
        ...

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
    ) -> str:  # returns message_id
        ...

    def save_document(
        self,
        merchant_id: str,
        doc_type: DocType,
        file_path: str,
    ) -> str:  # returns document_id
        ...

    def update_document_validation(
        self,
        document_id: str,
        result: DocValidationResult,
        kyc_result: KycResult | None = None,
    ) -> None:
        ...

    def get_context_bundle(self, merchant_id: str) -> ContextBundle:
        ...

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
    ) -> str:  # returns action_id
        ...

    def update_action_status(
        self,
        action_id: str,
        status: ActionStatus,
        executed_at: datetime | None = None,
        approved_by: str | None = None,
        rejection_reason: str | None = None,
    ) -> None:
        ...

    def update_state(
        self,
        merchant_id: str,
        new_state: LifecycleState,
        reason: str,
    ) -> None:
        ...

    def create_visit(
        self,
        merchant_id: str,
        fse_id: str,
        slot_start: str,
        cluster_size: int,
    ) -> str:  # returns visit_id
        ...

    def find_nearby_leads(
        self,
        merchant_id: str,
        radius_km: float,
        states: list[LifecycleState],
    ) -> list[MerchantView]:
        ...

    def get_settlement(self, merchant_id: str) -> SettlementView | None:
        ...

    def create_handoff(
        self,
        merchant_id: str,
        action_id: str,
        target: HandoffTarget,
        reason: str,
        summary: dict,
    ) -> str:  # returns handoff_id
        ...

    def get_autonomy_level(self, action_type: ActionType) -> AutonomyLevel:
        ...

    def set_consent(self, merchant_id: str, consent: bool) -> None:
        ...

    def write_audit(
        self,
        actor: str,
        event_type: str,
        merchant_id: str | None,
        payload: dict,
    ) -> None:
        ...

    def schedule_job(
        self,
        merchant_id: str,
        reason: str,
        run_at: datetime,
    ) -> None:
        ...

