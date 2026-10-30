"""
Boundary types and port protocols for the agent.
Owned by Person 2 (agent). Integrations and server import from here.

These are the *minimum* types that Person 1 (integrations) needs.
Person 2 will extend this file with the full agent ports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from agent.domain.enums import Channel, DocQuality, DocType, Language


# ── Incoming event (what integrations sends to the agent) ────────────────────

class IncomingEvent(BaseModel):
    event_id: str
    merchant_id: str | None = None
    phone_e164: str
    channel: Channel
    kind: str  # "text", "media", "voice", "unsupported"
    text: str | None = None
    media_path: str | None = None
    media_mime: str | None = None
    timestamp: datetime


# ── Outgoing message (what the agent asks integrations to send) ──────────────

class OutgoingMessage(BaseModel):
    merchant_id: str
    phone_e164: str
    channel: Channel
    text: str | None = None
    template_name: str | None = None
    template_params: list[str] = Field(default_factory=list)
    language: Language = Language.HINDI


# ── Send result ──────────────────────────────────────────────────────────────

class SendResult(BaseModel):
    ok: bool
    provider_message_id: str | None = None
    error_code: str | None = None
    error_detail: str | None = None


# ── Document types ───────────────────────────────────────────────────────────

class ProfileForKyc(BaseModel):
    merchant_id: str
    owner_name: str
    phone_e164: str


class DocValidationResult(BaseModel):
    quality: DocQuality
    extracted_pan: str | None = None
    name_match: bool | None = None  # None means could not determine
    issues: list[str] = Field(default_factory=list)
    precheck_passed: bool = False


class KycResult(BaseModel):
    status: str  # "approved" or "rejected"
    reference_id: str | None = None
    reason: str | None = None


# ── Agent result (what handle_incoming returns) ──────────────────────────────

class AgentResult(BaseModel):
    merchant_id: str | None = None
    action_taken: str | None = None
    reply_text: str | None = None
    success: bool = True
    error: str | None = None


# ── Port protocols ───────────────────────────────────────────────────────────

@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class DocumentChecker(Protocol):
    def validate_document(
        self, file_path: str, doc_type: DocType, profile: ProfileForKyc
    ) -> DocValidationResult: ...

    def submit_to_mock_kyc(self, document_id: str) -> KycResult: ...
