"""
Ports declared by the integrations area.
These are implemented by the server layer and injected at startup.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

from agent.domain.enums import Channel, Language


class MerchantRef(BaseModel):
    """Lightweight merchant lookup result."""
    id: str
    phone_e164: str
    language: Language
    preferred_channel: Channel


class Store(Protocol):
    """Persistence port – implemented by the server's adapter."""

    def already_processed(self, event_id: str) -> bool:
        ...

    def get_merchant_by_phone(self, phone_e164: str) -> MerchantRef | None:
        ...

    def get_merchant(self, merchant_id: str) -> MerchantRef | None:
        ...

    def last_inbound_at(self, merchant_id: str) -> datetime | None:
        ...

    def save_message(
        self,
        merchant_id: str,
        direction: str,
        channel: str,
        kind: str,
        text: str | None,
        provider_message_id: str | None = None,
    ) -> None:
        ...

    def write_audit(
        self,
        actor: str,
        event_type: str,
        merchant_id: str | None,
        payload: dict,
    ) -> None:
        ...

    def publish_event(
        self,
        type: str,
        merchant_id: str | None,
        data: dict,
    ) -> None:
        ...
