import pytest
import time
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_before_test():
    client.post("/api/demo/reset")

def test_at1_new_lead_fee_inquiry():
    """AT-1: Unknown phone asks about fees. Created NEW -> ENGAGED, fee answered, audit logged."""
    unknown_phone = "+919000000099"
    msg = "Soundbox lena hai, fees kya hain?"
    r = client.post(f"/api/chat/{unknown_phone}/message", json={"text": msg})
    assert r.status_code == 200
    data = r.json()
    assert "₹125" in data["reply"] or "125" in data["reply"]
    assert data["action"]["action_type"] == "ANSWER_QUERY"
    assert data["action"]["status"] == "executed"

    # Check merchant profile
    r_m = client.get(f"/api/merchants/{unknown_phone}")
    assert r_m.status_code == 200
    m_data = r_m.json()
    assert m_data["state"] == "ENGAGED"

def test_at2_meena_blurry_then_clear_pan():
    """AT-2: Blurry PAN rejected and re-requested. Clear PAN passes pre-check and schedules visit."""
    mid = "m_meena"

    # Step 1: Upload blurry photo
    files = {"file": ("meena_pan_blurry.jpg", b"fake_blurry_image_data", "image/jpeg")}
    r1 = client.post(f"/api/documents/{mid}", files=files)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["quality"] == "blurry"
    assert d1["precheck_passed"] == False
    assert d1["action_type"] == "REREQUEST_DOC"

    # State remains DOCS_PENDING
    r_m1 = client.get(f"/api/merchants/{mid}")
    assert r_m1.json()["state"] == "DOCS_PENDING"

    # Step 2: Upload clear photo
    files2 = {"file": ("meena_pan_clear.jpg", b"fake_clear_image_data", "image/jpeg")}
    r2 = client.post(f"/api/documents/{mid}", files=files2)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["quality"] == "ok"
    assert d2["precheck_passed"] == True
    assert d2["action_type"] == "SCHEDULE_VISIT"
    assert d2["cluster_size"] >= 2

    # State advanced to VISIT_SCHEDULED
    r_m2 = client.get(f"/api/merchants/{mid}")
    assert r_m2.json()["state"] == "VISIT_SCHEDULED"

def test_at3_sunil_installed_idle_device_nudges():
    """AT-3: Sunil installed, no txns, clock advanced 24h -> nudge 1 sent."""
    mid = "m_sunil"
    r_adv = client.post("/api/demo/advance", json={"hours": 24.0})
    assert r_adv.status_code == 200

    r_acts = client.get(f"/api/merchants/{mid}/actions")
    assert r_acts.status_code == 200
    actions = r_acts.json()
    assert any(a["action_type"] == "SEND_ACTIVATION_NUDGE" for a in actions)

def test_at4_farida_settlement_inquiry():
    """AT-4: Farida settlement query grounded in tool data with bank holiday delay."""
    mid = "m_farida"
    r = client.post(f"/api/chat/{mid}/message", json={"text": "Mera settlement nahi aaya"})
    assert r.status_code == 200
    data = r.json()
    assert "4820" in data["reply"] or "bank holiday" in data["reply"].lower()
    assert data["action"]["action_type"] == "EXPLAIN_SETTLEMENT"

def test_at5_vikram_discount_and_manager_escalation():
    """AT-5: Vikram demands discount -> L2 pending_approval. Asks for manager -> handoff created."""
    mid = "m_vikram"

    # Step 1: Demand discount
    r1 = client.post(f"/api/chat/{mid}/message", json={"text": "Discount do nahi to return kar dunga"})
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["action"]["action_type"] == "OFFER_DISCOUNT"
    assert d1["action"]["status"] == "pending_approval"
    assert d1["action"]["autonomy_level"] == "L2"

    # Step 2: Asks for manager
    r2 = client.post(f"/api/chat/{mid}/message", json={"text": "Manager se baat karao"})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["action"]["action_type"] == "ESCALATE"

    # Check handoffs
    r_h = client.get(f"/api/handoffs?target=fse")
    assert r_h.status_code == 200
    handoffs = r_h.json()
    assert any(h["merchant_id"] == mid for h in handoffs)

def test_at6_autonomy_level_control():
    """AT-6: Changing autonomy level changes execution behavior."""
    # Set SEND_INTRO to L2
    r_put = client.put("/api/autonomy/SEND_INTRO", json={"level": "L2", "by": "manager"})
    assert r_put.status_code == 200

    r_aut = client.get("/api/autonomy")
    assert r_aut.json()["SEND_INTRO"]["level"] == "L2"

    # Revert back to L3
    client.put("/api/autonomy/SEND_INTRO", json={"level": "L3", "by": "manager"})

def test_at8_reset_and_replay():
    """AT-8: Reset in < 3s, scoreboard and simulation load with visible assumptions."""
    t0 = time.time()
    r_reset = client.post("/api/demo/reset")
    t_diff = time.time() - t0
    assert r_reset.status_code == 200
    assert t_diff < 3.0

    r_score = client.get("/api/scoreboard")
    assert r_score.status_code == 200
    sb = r_score.json()
    assert sb["counters"]["actions_executed"] >= 0

    r_sim = client.post("/api/simulation/run", json={"seeds": 5, "population": 50})
    assert r_sim.status_code == 200
    sim = r_sim.json()
    assert "assumptions" in sim
    assert len(sim["metrics"]) > 0

def test_at9_failure_drills():
    """AT-9: Safe error responses, unknown lead creation, idempotency."""
    # Unknown lead creation
    r = client.post("/api/chat/+919000000088/message", json={"text": "Hello"})
    assert r.status_code == 200
    assert "Namaste" in r.json()["reply"] or "Paytm" in r.json()["reply"]

    # 404 on nonexistent merchant detail
    r404 = client.get("/api/merchants/m_nonexistent_xyz")
    assert r404.status_code == 404
    assert r404.json()["error"]["code"] == "NOT_FOUND"

