from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from sqlalchemy.orm import Session
from server.db.repo import PlatformRepo
from server.db.session import current_session
from server.events.bus import event_bus

class MerchantRef(BaseModel):
    id: str
    phone_e164: str
    language: str = "hindi"
    preferred_channel: str = "whatsapp"

class IntegrationsStoreAdapter:
    """
    Implements integrations.ports.Store.
    Adapts database models to plain models expected by Integrations.
    """
    def __init__(self, db: Optional[Session] = None):
        self._db = db

    @property
    def db(self) -> Session:
        return self._db or current_session()

    @property
    def repo(self) -> PlatformRepo:
        return PlatformRepo(self.db)

    def already_processed(self, event_id: str) -> bool:
        return self.repo.already_processed(event_id)

    def get_merchant_by_phone(self, phone_e164: str) -> Optional[MerchantRef]:
        m = self.repo.get_merchant_by_phone(phone_e164)
        if not m:
            return None
        return MerchantRef(
            id=m.id,
            phone_e164=m.phone_e164,
            language=m.language,
            preferred_channel=m.preferred_channel
        )

    def get_merchant(self, merchant_id: str) -> Optional[MerchantRef]:
        m = self.repo.get_merchant(merchant_id)
        if not m:
            return None
        return MerchantRef(
            id=m.id,
            phone_e164=m.phone_e164,
            language=m.language,
            preferred_channel=m.preferred_channel
        )

    def last_inbound_at(self, merchant_id: str) -> Optional[datetime]:
        return self.repo.last_inbound_at(merchant_id)

    def save_message(
        self,
        merchant_id: str,
        direction: str,
        channel: str,
        kind: str,
        text: Optional[str],
        provider_message_id: Optional[str] = None
    ) -> None:
        normalized_direction = {
            "inbound": "in",
            "outbound": "out",
        }.get(direction, direction)
        self.repo.save_message(
            merchant_id=merchant_id,
            direction=normalized_direction,
            channel=channel,
            kind=kind,
            text=text,
            provider_message_id=provider_message_id
        )

    def write_audit(self, actor: str, event_type: str, merchant_id: Optional[str], payload: Dict[str, Any]) -> None:
        self.repo.write_audit(actor, event_type, merchant_id, payload)

    def publish_event(self, type: str, merchant_id: Optional[str], data: Dict[str, Any]) -> None:
        event_bus.publish(type, merchant_id, data, self.db)
