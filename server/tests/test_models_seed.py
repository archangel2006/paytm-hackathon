import pytest
from server.db.seed import seed_database
from server.db.session import SessionLocal
from server.db.models import Merchant, FSE, Base
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

