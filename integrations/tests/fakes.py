from __future__ import annotations

from datetime import datetime, timezone

from agent.domain.enums import Channel, Language
from integrations.ports import MerchantRef


class FakeClock:
    def __init__(self, value: datetime | None = None):
        self.value = value or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self.value


class FakeStore:
    def __init__(self):
        self.merchants: dict[str, MerchantRef] = {}
        self.messages: list[dict] = []
        self.events: list[dict] = []
        self.audit: list[dict] = []
        self.processed: set[str] = set()
        self.inbound: datetime | None = None
        self.last_inbound: dict[str, datetime] = {}

    def add_merchant(self, merchant: MerchantRef) -> None:
        self.merchants[merchant.id] = merchant

    def already_processed(self, event_id: str) -> bool:
        if event_id in self.processed:
            return True
        self.processed.add(event_id)
        return False

    def get_merchant_by_phone(self, phone_e164: str):
        return next((m for m in self.merchants.values() if m.phone_e164 == phone_e164), None)

    def get_merchant(self, merchant_id: str):
        return self.merchants.get(merchant_id)

    def last_inbound_at(self, merchant_id: str):
        return self.last_inbound.get(merchant_id, self.inbound)

    def save_message(self, merchant_id, direction, channel, kind, text, provider_message_id=None):
        self.messages.append(locals())
        if direction == "inbound":
            self.inbound = datetime.now(timezone.utc)
            self.last_inbound[merchant_id] = self.inbound

    def write_audit(self, actor, event_type, merchant_id, payload):
        self.audit.append(locals())

    def publish_event(self, type, merchant_id, data):
        self.events.append(locals())


class RecordingOnIncoming:
    def __init__(self):
        self.calls = []

    def __call__(self, event):
        from agent.ports import AgentResult
        self.calls.append(event)
        return AgentResult(merchant_id=event.merchant_id, success=True)


def make_test_merchant() -> MerchantRef:
    return MerchantRef(
        id="test-merchant",
        phone_e164="+919876543210",
        language=Language.HINDI,
        preferred_channel=Channel.SIMULATOR,
    )


FixedClock = FakeClock
MemoryStore = FakeStore
