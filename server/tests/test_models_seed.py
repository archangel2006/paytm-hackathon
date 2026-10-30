import pytest
from server.db.seed import seed_database
from server.db.session import SessionLocal
from server.db.models import Merchant, FSE, Base, Document, Visit, Device, Transaction
from server.db.repo import LEGAL_TRANSITIONS

VALID_STATES = set(LEGAL_TRANSITIONS.keys())

def test_pl01_seed_idempotency_and_counts():
    # Run seed twice
    seed_database()
    db = SessionLocal()
    try:
        count_first = db.query(Merchant).count()
        assert count_first == 306, f"Expected 306 merchants, got {count_first}"

        # Re-run seed
        seed_database()
        count_second = db.query(Merchant).count()
        assert count_second == 306, "Seed should be deterministic and idempotent"

        # Unique phone numbers
        phones = [m.phone_e164 for m in db.query(Merchant.phone_e164).all()]
        assert len(phones) == len(set(phones)), "Phone numbers must be unique"

        # Verify 6 heroes
        heroes = {
            "m_rahul": "CONTACTED",
            "m_meena": "DOCS_PENDING",
            "m_sunil": "INSTALLED",
            "m_farida": "ACTIVATED",
            "m_vikram": "ENGAGED",
            "m_pooja": "NEW"
        }
        for hid, expected_state in heroes.items():
            h = db.query(Merchant).filter(Merchant.id == hid).first()
            assert h is not None, f"Hero {hid} missing"
            assert h.state == expected_state, f"Hero {hid} state mismatch: expected {expected_state}, got {h.state}"

        # Check all states are valid
        for m in db.query(Merchant).all():
            assert m.state in VALID_STATES, f"Invalid state {m.state} for merchant {m.id}"

        # Check FSE count
        assert db.query(FSE).count() == 4
    finally:
        db.close()


def test_seed_includes_fully_onboarded_merchant_example():
    from fastapi.testclient import TestClient
    from server.main import app

    seed_database()
    db = SessionLocal()
    try:
        merchant = db.query(Merchant).filter(Merchant.id == "m_farida").one()
        documents = {
            document.doc_type: document
            for document in db.query(Document).filter(Document.merchant_id == merchant.id).all()
        }
        successful_transactions = db.query(Transaction).filter(
            Transaction.merchant_id == merchant.id,
            Transaction.status == "success",
        ).count()

        assert {"pan", "address_proof"} <= documents.keys()
        assert all(
            documents[doc_type].precheck_passed
            and documents[doc_type].kyc_status == "approved"
            for doc_type in ("pan", "address_proof")
        )
        assert db.query(Visit).filter(
            Visit.merchant_id == merchant.id,
            Visit.status == "done",
        ).count() >= 1
        assert merchant.device is not None
        assert merchant.device.status in {"installed", "active"}
        assert successful_transactions >= 10
    finally:
        db.close()

    with TestClient(app) as client:
        portfolio = client.get("/api/merchants?limit=300").json()
    farida = next(item for item in portfolio["items"] if item["id"] == "m_farida")
    assert farida["activation_eligible"] is True
    assert farida["successful_txn_count"] >= 10
