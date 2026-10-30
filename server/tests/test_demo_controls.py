import time
import pytest
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)

def test_pl11_demo_reset_speed():
    t_start = time.time()
    r = client.post("/api/demo/reset")
    t_elapsed = time.time() - t_start

    assert r.status_code == 200
    assert r.json()["status"] == "reset_complete"
    assert t_elapsed < 3.0, f"Reset took {t_elapsed:.2f}s, must be under 3.0s"

def test_pl12_device_events_lifecycle():
    client.post("/api/demo/reset")

    # Pick a fresh merchant or hero
    mid = "m_pooja"

    # 1. Device installed event
    r_inst = client.post("/api/demo/device-event", json={"merchant_id": mid, "event": "installed"})
    assert r_inst.status_code == 200
    assert r_inst.json()["device_status"] == "installed"
    assert r_inst.json()["merchant_state"] == "ACTIVATING"

    # 2. Add 5 transactions
    r_tx1 = client.post("/api/demo/device-event", json={"merchant_id": mid, "event": "transaction", "count": 5})
    assert r_tx1.status_code == 200
    assert r_tx1.json()["total_transactions"] == 5
    assert r_tx1.json()["merchant_state"] == "ACTIVATING"

    # 3. Add 5 more transactions (total = 10) -> state moves to ACTIVATED
    r_tx2 = client.post("/api/demo/device-event", json={"merchant_id": mid, "event": "transaction", "count": 5})
    assert r_tx2.status_code == 200
    assert r_tx2.json()["total_transactions"] == 10
    assert r_tx2.json()["merchant_state"] == "ACTIVATED"

