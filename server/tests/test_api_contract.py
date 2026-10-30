import os
import json
import pytest
from fastapi.testclient import TestClient
from server.main import app
from server.db.seed import seed_database
from server.events.bus import event_bus

client = None

@pytest.fixture(scope="module", autouse=True)
def setup_seed():
    global client
    seed_database()
    with TestClient(app) as test_client:
        client = test_client
        yield

def test_pl08_api_contract_routes():
    # 1. GET /api/health
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ok", "degraded")
    assert "clock_simulated_now" in data

    # 2. GET /api/briefing
    r = client.get("/api/briefing")
    assert r.status_code == 200
    briefing = r.json()
    assert "overnight" in briefing
    assert "route" in briefing
    assert "top_leads" in briefing
    assert "pending_approvals" in briefing
    assert "open_handoffs" in briefing

    # 3. GET /api/merchants
    r = client.get("/api/merchants?limit=10")
    assert r.status_code == 200
    merchants = r.json()
    assert "items" in merchants
    assert len(merchants["items"]) == 10
    assert merchants["total"] >= 300

    # 4. GET /api/merchants/m_rahul
    r = client.get("/api/merchants/m_rahul")
    assert r.status_code == 200
    rahul = r.json()
    assert rahul["id"] == "m_rahul"
    assert rahul["shop_name"] == "Rahul Kirana Store"
    assert "documents" in rahul
    assert "visits" in rahul

    # 5. GET /api/merchants/m_rahul/next-action
    r = client.get("/api/merchants/m_rahul/next-action")
    assert r.status_code == 200
    na = r.json()
    assert "action_type" in na
    assert "reasoning" in na
    assert "autonomy_level" in na

    # 6. GET /api/scoreboard
    r = client.get("/api/scoreboard")
    assert r.status_code == 200
    sb = r.json()
    assert "counters" in sb
    assert "funnel" in sb
    assert "conversion_rate" in sb

    # 7. GET /api/autonomy
    r = client.get("/api/autonomy")
    assert r.status_code == 200
    aut = r.json()
    assert "SEND_INTRO" in aut

    # 8. GET /api/audit
    r = client.get("/api/audit?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_merchant_portfolio_counts_successful_transactions_and_hides_pan_values():
    from datetime import datetime, timezone
    from server.db.models import Device, Document, Visit
    from server.db.session import SessionLocal
    from server.db.repo import PlatformRepo

    client.post("/api/demo/reset")
    db = SessionLocal()
    try:
        repo = PlatformRepo(db)
        merchant = repo.get_merchant("m_rahul")
        assert merchant is not None
        for doc_type in ("pan", "address_proof"):
            db.add(Document(
                id=f"doc_{merchant.id}_{doc_type}_contract",
                merchant_id=merchant.id,
                doc_type=doc_type,
                file_path=f"synthetic://{doc_type}",
                quality="ok",
                precheck_passed=True,
                kyc_status="approved",
                created_at=datetime.now(timezone.utc),
            ))
        db.commit()
        expected_total = len(merchant.transactions)
        expected_successful = sum(transaction.status == "success" for transaction in merchant.transactions)

        portfolio = client.get("/api/merchants?limit=300").json()
        item = next(row for row in portfolio["items"] if row["id"] == merchant.id)
        assert item["txn_count"] == expected_total
        assert item["successful_txn_count"] == expected_successful
        assert item["docs_status"] == "verified"
        assert item["activation_eligible"] is False

        db.add(Visit(
            id=f"visit_{merchant.id}_activation_contract",
            merchant_id=merchant.id,
            fse_id=merchant.fse_id,
            slot_start=datetime.now(timezone.utc),
            status="done",
        ))
        db.commit()
        portfolio = client.get("/api/merchants?limit=300").json()
        item = next(row for row in portfolio["items"] if row["id"] == merchant.id)
        assert item["activation_eligible"] is False

        db.add(Device(
            id=f"device_{merchant.id}_activation_contract",
            merchant_id=merchant.id,
            status="active",
        ))
        db.commit()
        portfolio = client.get("/api/merchants?limit=300").json()
        item = next(row for row in portfolio["items"] if row["id"] == merchant.id)
        assert item["activation_eligible"] is True

        meena = next(row for row in portfolio["items"] if row["id"] == "m_meena")
        assert meena["docs_status"] == "pending"
        assert meena["activation_eligible"] is False

        detail = client.get(f"/api/merchants/{merchant.id}").json()
        assert detail["successful_txn_count"] == expected_successful
        for document in detail["documents"]:
            assert "kyc_status" in document
            assert "kyc_reference" in document
            assert "extracted_pan" not in document
    finally:
        db.close()


def test_demo_transactions_require_verified_documents_completed_visit_and_installed_device():
    from datetime import datetime, timezone
    from server.db.models import Document, Visit, Transaction
    from server.db.session import SessionLocal
    from server.db.repo import PlatformRepo

    client.post("/api/demo/reset")
    blocked = client.post(
        "/api/demo/device-event",
        json={"merchant_id": "m_rahul", "event": "transaction", "count": 1},
    )
    assert blocked.status_code == 409
    assert "approved PAN and address documents" in blocked.json()["error"]["message"]

    db = SessionLocal()
    try:
        repo = PlatformRepo(db)
        merchant = repo.get_merchant("m_rahul")
        assert merchant is not None
        now = datetime.now(timezone.utc)
        for doc_type in ("pan", "address_proof"):
            db.add(Document(
                id=f"doc_{merchant.id}_{doc_type}_transaction_test",
                merchant_id=merchant.id,
                doc_type=doc_type,
                file_path=f"synthetic://{doc_type}",
                quality="ok",
                precheck_passed=True,
                kyc_status="approved",
                created_at=now,
            ))
        merchant.state = "VISIT_SCHEDULED"
        db.add(Visit(
            id="visit_merchant_activation_test",
            merchant_id=merchant.id,
            fse_id=merchant.fse_id,
            slot_start=now,
            status="scheduled",
            cluster_size=1,
            created_at=now,
        ))
        db.commit()
    finally:
        db.close()

    install = client.post(
        "/api/demo/device-event",
        json={"merchant_id": "m_rahul", "event": "installed"},
    )
    assert install.status_code == 200
    assert install.json()["merchant_state"] == "ACTIVATING"

    transaction = client.post(
        "/api/demo/device-event",
        json={"merchant_id": "m_rahul", "event": "transaction", "count": 10},
    )
    assert transaction.status_code == 200
    assert transaction.json()["total_transactions"] == 10
    assert transaction.json()["merchant_state"] == "ACTIVATED"

    db = SessionLocal()
    try:
        assert db.query(Transaction).filter(
            Transaction.merchant_id == "m_rahul",
            Transaction.status == "success",
        ).count() == 10
        assert db.query(Visit).filter(
            Visit.id == "visit_merchant_activation_test",
            Visit.status == "done",
        ).count() == 1
    finally:
        db.close()

    duplicate_goal = client.post(
        "/api/demo/device-event",
        json={"merchant_id": "m_rahul", "event": "transaction", "count": 1},
    )
    assert duplicate_goal.status_code == 409


def test_document_upload_uses_selected_type_and_schedules_visit_after_both_approvals():
    from pathlib import Path

    client.post("/api/demo/reset")
    samples = Path("integrations/documents/samples")
    pan_bytes = (samples / "meena_pan_clear.jpg").read_bytes()
    blurry_bytes = (samples / "pan_blurry.jpg").read_bytes()

    blurry = client.post(
        "/api/documents/m_meena?doc_type=pan",
        files={"file": ("pan_blurry.jpg", blurry_bytes, "image/jpeg")},
    )
    assert blurry.status_code == 200
    assert blurry.json()["precheck_passed"] is False
    assert "not clear" in blurry.json()["reply"].lower()

    pan = client.post(
        "/api/documents/m_meena?doc_type=pan",
        files={"file": ("meena_pan_clear.jpg", pan_bytes, "image/jpeg")},
    )
    assert pan.status_code == 200
    assert pan.json()["doc_type"] == "pan"
    assert pan.json()["precheck_passed"] is True
    assert pan.json()["merchant_state"] == "DOCS_PENDING"

    address = client.post(
        "/api/documents/m_meena?doc_type=address_proof",
        files={"file": ("meena_pan_clear.jpg", pan_bytes, "image/jpeg")},
    )
    assert address.status_code == 200
    assert address.json()["doc_type"] == "address_proof"
    assert address.json()["precheck_passed"] is True
    assert address.json()["merchant_state"] == "VISIT_SCHEDULED"
    detail = client.get("/api/merchants/m_meena").json()
    latest_by_type = {}
    for document in detail["documents"]:
        latest_by_type[document["doc_type"]] = document
    assert latest_by_type["pan"]["id"] == pan.json()["document_id"]
    assert latest_by_type["pan"]["precheck_passed"] is True
    assert latest_by_type["pan"]["kyc_status"] == "approved"
    assert latest_by_type["address_proof"]["id"] == address.json()["document_id"]
    assert latest_by_type["address_proof"]["precheck_passed"] is True
    assert latest_by_type["address_proof"]["kyc_status"] == "approved"
    assert detail["state"] == "VISIT_SCHEDULED"
    assert address.json()["merchant_state"] == "VISIT_SCHEDULED"
    assert address.json()["visit_id"]

    assert {document["doc_type"] for document in detail["documents"] if document["kyc_status"] == "approved"} == {
        "pan",
        "address_proof",
    }


def test_unanswered_question_creates_support_handoff(monkeypatch):
    from agent.core.nlu import NluResult
    from agent.domain.enums import Intent, Language

    client.post("/api/demo/reset")
    monkeypatch.setattr(
        "agent.core.entrypoint.nlu.classify",
        lambda text: NluResult(
            intent=Intent.OTHER,
            language=Language.ENGLISH,
            sentiment=0.0,
            wants_human=False,
            mentions_money=False,
            confidence=1.0,
        ),
    )
    response = client.post(
        "/api/chat/m_rahul/message",
        json={"text": "Can you check this question for me?"},
    )
    assert response.status_code == 200
    assert response.json()["action"]["action_type"] == "ESCALATE"

    handoff = next(
        item for item in client.get("/api/handoffs?status=open").json()
        if item["merchant_id"] == "m_rahul"
    )
    assert handoff["target"] == "support"
    assert handoff["reason"] == "unsupported_question"


def test_pl10_polling_endpoint_with_since():
    # Publish two events
    e1 = event_bus.publish("test.event.one", "m_test1", {"n": 1})
    e2 = event_bus.publish("test.event.two", "m_test2", {"n": 2})

    r = client.get(f"/api/events?since={e1.id}")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    assert any(it["id"] == e2.id for it in items)
    assert not any(it["id"] <= e1.id for it in items)

def test_pl13_autonomy_put_and_audit():
    # Promote or demote an action type
    r = client.put("/api/autonomy/SEND_ACTIVATION_NUDGE", json={"level": "L2", "by": "test_manager"})
    assert r.status_code == 200
    data = r.json()
    assert data["level"] == "L2"

    # Verify next read sees L2
    r_check = client.get("/api/autonomy")
    assert r_check.json()["SEND_ACTIVATION_NUDGE"]["level"] == "L2"

    # Reset back to L3
    client.put("/api/autonomy/SEND_ACTIVATION_NUDGE", json={"level": "L3", "by": "test_manager"})


def test_pl14_demo_state_and_duplicate_webhook_idempotency():
    # AT-8 style platform durability: clock and slow mode persist in demo state
    client.post("/api/demo/reset")
    r = client.post("/api/demo/advance", json={"hours": 12})
    assert r.status_code == 200
    assert r.json()["clock_offset_seconds"] >= 43200

    r_state = client.get("/api/demo/state")
    assert r_state.status_code == 200
    assert r_state.json()["clock_offset_seconds"] >= 43200

    r_slow = client.post("/api/demo/slow-mode", json={"enabled": True})
    assert r_slow.status_code == 200
    assert r_slow.json()["slow_mode"] is True

    # Duplicate WhatsApp deliveries should not create a second row/message
    from server.db.session import SessionLocal
    from server.db.models import Message
    db = SessionLocal()
    try:
        from server.db.repo import PlatformRepo
        repo = PlatformRepo(db)
        merchant = repo.get_merchant_by_phone("+919000000001")
        m1 = repo.save_message(merchant.id, "in", "whatsapp", "text", "duplicate test", event_id="evt_demo_1")
        m2 = repo.save_message(merchant.id, "in", "whatsapp", "text", "duplicate test 2", event_id="evt_demo_1")
        assert m1.id == m2.id
        assert db.query(Message).filter(Message.event_id == "evt_demo_1").count() == 1
    finally:
        db.close()


def test_chat_does_not_return_stale_reply_when_action_is_blocked(monkeypatch):
    client.post("/api/demo/reset")

    first = client.post(
        "/api/chat/m_rahul/message",
        json={"text": "Soundbox fees kya hain?"},
    )
    assert first.status_code == 200
    assert first.json()["reply"]

    monkeypatch.setattr("agent.settings.MAX_MESSAGES_PER_DAY", 0)
    blocked = client.post(
        "/api/chat/m_rahul/message",
        json={"text": "Soundbox fees kitne hain?"},
    )

    assert blocked.status_code == 200
    assert blocked.json()["action"]["status"] == "blocked"
    assert blocked.json()["reply"] == ""


def test_agent_batch_and_human_approval_are_integrated():
    from server.db.models import AgentAction, Merchant
    from server.db.session import SessionLocal
    from server.db.repo import PlatformRepo

    client.post("/api/demo/reset")
    db = SessionLocal()
    try:
        repo = PlatformRepo(db)
        new_leads, _ = repo.list_merchants(state="NEW", limit=1)
        assert new_leads
        new_leads[0].preferred_channel = "simulator"
        db.commit()
        batch = client.post("/api/agent/run-batch?limit=1")
        assert batch.status_code == 200
        assert batch.json()["leads_evaluated"] == 1
        assert batch.json()["newly_contacted"] == 1

        pending = repo.save_action(
            merchant_id=new_leads[0].id,
            action_type="SEND_INTRO",
            params={},
            reasoning="Approval integration test",
            confidence=0.9,
            source="rule",
            autonomy_level="L2",
            status="pending_approval",
        )
        approved = client.post(f"/api/actions/{pending.id}/approve", json={"by": "manager"})
        assert approved.status_code == 200
        assert approved.json()["reply_sent"] is True
        db.refresh(pending)
        assert pending.status == "executed"

        rejected = repo.save_action(
            merchant_id=new_leads[0].id,
            action_type="SEND_INTRO",
            params={},
            reasoning="Rejection integration test",
            confidence=0.9,
            source="rule",
            autonomy_level="L2",
            status="pending_approval",
        )
        rejection = client.post(
            f"/api/actions/{rejected.id}/reject",
            json={"by": "manager", "reason_code": "not_needed"},
        )
        assert rejection.status_code == 200
        db.refresh(rejected)
        assert rejected.status == "rejected"

        preview = client.get(f"/api/merchants/{new_leads[0].id}/next-action")
        assert preview.status_code == 200
        assert preview.json()["action_type"]
    finally:
        db.close()
