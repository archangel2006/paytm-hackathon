import pytest
from server.db.repo import PlatformRepo
from server.db.models import AuditLog, Message

def test_pl02_save_message_idempotency(test_repo):
    merchant = test_repo.create_lead("+919999900001")
    event_id = "evt_dedupe_12345"

    msg1 = test_repo.save_message(
        merchant_id=merchant.id,
        direction="in",
        channel="whatsapp",
        kind="text",
        text="Hello Saathi",
        event_id=event_id
    )

    msg2 = test_repo.save_message(
        merchant_id=merchant.id,
        direction="in",
        channel="whatsapp",
        kind="text",
        text="Hello Saathi Duplicate",
        event_id=event_id
    )

    assert msg1.id == msg2.id
    total_msgs = test_repo.db.query(Message).filter(Message.event_id == event_id).count()
    assert total_msgs == 1

def test_pl03_illegal_state_transition(test_repo):
    merchant = test_repo.create_lead("+919999900002")
    assert merchant.state == "NEW"

    # Legal transition
    test_repo.update_state(merchant.id, "CONTACTED")
    assert merchant.state == "CONTACTED"

    # Illegal transition: CONTACTED cannot jump straight to ACTIVATED
    with pytest.raises(ValueError, match="Illegal state transition"):
        test_repo.update_state(merchant.id, "ACTIVATED")

def test_pl04_context_bundle_fields(test_repo):
    merchant = test_repo.create_lead("+919999900003")
    bundle = test_repo.get_context_bundle(merchant.id)

    required_keys = ["merchant", "docs", "activity", "open_tickets", "recent_messages", "counters", "consent", "now"]
    for k in required_keys:
        assert k in bundle, f"Context bundle missing key: {k}"

    counters = bundle["counters"]
    assert "contact_attempts" in counters
    assert "nudges_sent" in counters
    assert "doc_rerequests" in counters
    assert "messages_today" in counters

def test_pl05_audit_log_append_only(test_repo):
    # Verify no update_audit or delete_audit functions exist on repo
    assert not hasattr(test_repo, "update_audit"), "Audit log must not have update method"
    assert not hasattr(test_repo, "delete_audit"), "Audit log must not have delete method"

    count_before = test_repo.db.query(AuditLog).count()
    entry = test_repo.write_audit("admin", "test_event", "m_test", {"foo": "bar"})

    count_after = test_repo.db.query(AuditLog).count()
    assert count_after == count_before + 1
    assert entry.actor == "admin"
    assert entry.payload == {"foo": "bar"}

