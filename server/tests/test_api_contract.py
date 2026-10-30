import os
import json
import pytest
from fastapi.testclient import TestClient
from server.main import app
from server.db.seed import seed_database
from server.events.bus import event_bus

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_seed():
    seed_database()

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

