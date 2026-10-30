import json
import os
import random
import shutil
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from server.db.models import (
    Base, FSE, Merchant, Message, Document, Visit, Device, Transaction,
    Settlement, Ticket, AgentAction, Handoff, AutonomyConfig, AuditLog,
    ScheduledJob, DemoState
)
from server.db.session import engine, init_db, SessionLocal
from server.settings import settings

CLUSTERS = [
    {"name": "Rohini", "city": "Delhi", "lat": 28.7041, "lng": 77.1025, "fse_id": "fse_1"},
    {"name": "Pitampura", "city": "Delhi", "lat": 28.6990, "lng": 77.1384, "fse_id": "fse_1"},
    {"name": "Connaught Place", "city": "Delhi", "lat": 28.6315, "lng": 77.2167, "fse_id": "fse_2"},
    {"name": "Lajpat Nagar", "city": "Delhi", "lat": 28.5677, "lng": 77.2433, "fse_id": "fse_2"},
    {"name": "Saket", "city": "Delhi", "lat": 28.5244, "lng": 77.2100, "fse_id": "fse_2"},
    {"name": "Sector 18", "city": "Noida", "lat": 28.5700, "lng": 77.3200, "fse_id": "fse_3"},
    {"name": "Sector 62", "city": "Noida", "lat": 28.6270, "lng": 77.3620, "fse_id": "fse_3"},
    {"name": "Indirapuram", "city": "Ghaziabad", "lat": 28.6415, "lng": 77.3714, "fse_id": "fse_3"},
    {"name": "Sector 14", "city": "Gurugram", "lat": 28.4595, "lng": 77.0266, "fse_id": "fse_4"},
    {"name": "Cyber City", "city": "Gurugram", "lat": 28.4950, "lng": 77.0890, "fse_id": "fse_4"}
]

CATEGORIES = [
    ("kirana", 0.40),
    ("chai stall", 0.15),
    ("salon", 0.10),
    ("pharmacy", 0.10),
    ("mobile repair", 0.10),
    ("sweet shop", 0.05),
    ("restaurant", 0.05),
    ("clothing", 0.05)
]

LANGUAGES = [
    ("hindi", 0.55),
    ("hinglish", 0.30),
    ("english", 0.15)
]

SHOP_PREFIXES = ["Apna", "Shree", "New", "Royal", "Gupta", "Sharma", "Super", "Om", "Jai", "Balaji"]
OWNER_FIRST_NAMES = ["Ramesh", "Suresh", "Manoj", "Ajay", "Vijay", "Anil", "Deepak", "Rajesh", "Sunita", "Anita", "Geeta"]
OWNER_LAST_NAMES = ["Sharma", "Verma", "Gupta", "Singh", "Yadav", "Kumar", "Mishra", "Patel", "Jain", "Chauhan"]

def weighted_choice(choices):
    r = random.random()
    upto = 0.0
    for c, w in choices:
        if upto + w >= r:
            return c
        upto += w
    return choices[-1][0]

def seed_database(target_db_url: str = None) -> None:
    random.seed(42)
    now = datetime.now(timezone.utc)

    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    seed_copy_path = db_path.replace(".db", ".seed.db")

    # Recreate tables
    init_db()
    db = SessionLocal()

    try:
        # Clear existing data
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()

        # 1. Seed FSEs
        fse_file = os.path.join(os.path.dirname(__file__), "..", "seed_data", "fses.json")
        with open(fse_file, "r", encoding="utf-8") as f:
            fses_data = json.load(f)

        fses = []
        for d in fses_data:
            fse = FSE(
                id=d["id"],
                name=d["name"],
                zone=d["zone"],
                start_lat=d["start_lat"],
                start_lng=d["start_lng"]
            )
            fses.append(fse)
            db.add(fse)
        db.commit()

        # 2. Seed Hero Merchants
        heroes_file = os.path.join(os.path.dirname(__file__), "..", "seed_data", "heroes.json")
        with open(heroes_file, "r", encoding="utf-8") as f:
            heroes_data = json.load(f)

        for h in heroes_data:
            # Overwrite phone if present in settings
            phone_key = f"HERO_PHONE_{h['id'].replace('m_', '').upper()}"
            phone = getattr(settings, phone_key, h["phone_e164"])

            merchant = Merchant(
                id=h["id"],
                shop_name=h["shop_name"],
                owner_name=h["owner_name"],
                category=h["category"],
                city=h["city"],
                area=h["area"],
                pincode=h["pincode"],
                lat=h["lat"],
                lng=h["lng"],
                language=h["language"],
                phone_e164=phone,
                preferred_channel=h["preferred_channel"],
                consent=h["consent"],
                footfall_score=h["footfall_score"],
                lead_score=h["lead_score"],
                score_explanation=h["score_explanation"],
                state=h["state"],
                state_updated_at=now,
                fse_id=h["fse_id"],
                created_at=now - timedelta(days=2)
            )
            db.add(merchant)

            # Hero specific attachments
            if h["id"] == "m_rahul":
                # Contacted action
                action = AgentAction(
                    id="act_hero_rahul_intro",
                    merchant_id="m_rahul",
                    action_type="SEND_INTRO",
                    params={"template_id": "saathi_intro_hi"},
                    reasoning="High value lead in Rohini cluster. Reached out in Hindi.",
                    confidence=0.95,
                    autonomy_level="L3",
                    status="executed",
                    created_at=now - timedelta(hours=3),
                    executed_at=now - timedelta(hours=3)
                )
                db.add(action)
            elif h["id"] == "m_sunil":
                device = Device(
                    id="dev_m_sunil",
                    merchant_id="m_sunil",
                    status="installed",
                    installed_at=now
                )
                db.add(device)
                # Pending activation check at +24h
                job = ScheduledJob(
                    id="job_sunil_act_check",
                    merchant_id="m_sunil",
                    reason="activation_check",
                    run_at=now + timedelta(hours=24),
                    status="pending"
                )
                db.add(job)
            elif h["id"] == "m_farida":
                for doc_type in ("pan", "address_proof"):
                    document = Document(
                        id=f"doc_m_farida_{doc_type}",
                        merchant_id="m_farida",
                        doc_type=doc_type,
                        file_path=f"synthetic://demo/m_farida/{doc_type}",
                        quality="ok",
                        precheck_passed=True,
                        kyc_status="approved",
                        kyc_reference=f"DEMO-KYC-FARIDA-{doc_type.upper()}",
                        created_at=now - timedelta(days=16)
                    )
                    db.add(document)
                visit = Visit(
                    id="visit_m_farida_completed",
                    merchant_id="m_farida",
                    fse_id="fse_3",
                    slot_start=now - timedelta(days=15),
                    status="done",
                    created_at=now - timedelta(days=16)
                )
                db.add(visit)
                device = Device(
                    id="dev_m_farida",
                    merchant_id="m_farida",
                    status="active",
                    installed_at=now - timedelta(days=15),
                    first_txn_at=now - timedelta(days=14)
                )
                db.add(device)
                # 42 transactions
                for i in range(42):
                    t = Transaction(
                        id=f"txn_farida_{i}",
                        merchant_id="m_farida",
                        amount=round(random.uniform(50, 400), 2),
                        status="success",
                        created_at=now - timedelta(days=random.randint(1, 14))
                    )
                    db.add(t)
                # Delayed settlement
                st = Settlement(
                    id="set_m_farida_1",
                    merchant_id="m_farida",
                    amount=4820.0,
                    expected_date=now + timedelta(days=1),
                    status="delayed",
                    delay_reason="bank holiday"
                )
                db.add(st)
            elif h["id"] == "m_vikram":
                msg = Message(
                    id="msg_hero_vikram_obj",
                    merchant_id="m_vikram",
                    direction="in",
                    channel="whatsapp",
                    kind="text",
                    text="Fees zyada hai, kuch discount mil sakta hai kya?",
                    intent="ask_discount",
                    sentiment=-0.2,
                    created_at=now - timedelta(hours=1)
                )
                db.add(msg)
            elif h["id"] == "m_meena":
                doc = Document(
                    id="doc_m_meena_1",
                    merchant_id="m_meena",
                    doc_type="pan",
                    file_path="./uploads/meena_pan_sample.jpg",
                    quality="pending",
                    attempts=0,
                    created_at=now - timedelta(hours=2)
                )
                db.add(doc)

        db.commit()

        # 3. Seed 3 nearby DOCS_VERIFIED leads for Rahul (Rohini)
        # to ensure cluster_size is at least 4 when visit is scheduled
        rahul_lat, rahul_lng = 28.7041, 77.1025
        for i in range(1, 4):
            lead_id = f"m_rahul_cluster_{i}"
            lead = Merchant(
                id=lead_id,
                shop_name=f"Rohini Store {i}",
                owner_name=f"Partner {i}",
                category="kirana",
                city="Delhi",
                area="Rohini",
                pincode="110085",
                lat=rahul_lat + (i * 0.003),
                lng=rahul_lng + (i * 0.003),
                language="hindi",
                phone_e164=f"+91900000010{i}",
                preferred_channel="whatsapp",
                consent=True,
                footfall_score=0.80,
                lead_score=85.0,
                score_explanation="Nearby Rohini merchant with verified documents",
                state="DOCS_VERIFIED",
                fse_id="fse_1",
                created_at=now - timedelta(days=1)
            )
            db.add(lead)
        db.commit()

        # 4. Seed remaining ~297 synthetic merchants to reach exactly 306 merchants
        # States distribution: ~60% NEW, 15% CONTACTED/ENGAGED, 10% DOCS, 8% ACTIVATING, 7% ACTIVATED
        existing_count = db.query(Merchant).count()
        needed = 306 - existing_count

        state_pool = (
            ["NEW"] * int(needed * 0.60) +
            ["CONTACTED"] * int(needed * 0.10) +
            ["ENGAGED"] * int(needed * 0.05) +
            ["DOCS_PENDING"] * int(needed * 0.05) +
            ["DOCS_VERIFIED"] * int(needed * 0.05) +
            ["ACTIVATING"] * int(needed * 0.08) +
            ["ACTIVATED"] * int(needed * 0.07)
        )
        while len(state_pool) < needed:
            state_pool.append("NEW")
        random.shuffle(state_pool)

        phone_counter = 110
        for i in range(needed):
            st = state_pool[i]
            cluster = random.choice(CLUSTERS)
            cat = weighted_choice(CATEGORIES)
            lang = weighted_choice(LANGUAGES)
            owner = f"{random.choice(OWNER_FIRST_NAMES)} {random.choice(OWNER_LAST_NAMES)}"
            shop = f"{random.choice(SHOP_PREFIXES)} {cat.capitalize()} Center"
            mid = f"m_syn_{i+1:03d}"
            phone = f"+91900000{phone_counter:04d}"
            phone_counter += 1

            # Scatter jitter within ~1-2km of cluster
            lat = cluster["lat"] + random.uniform(-0.012, 0.012)
            lng = cluster["lng"] + random.uniform(-0.012, 0.012)
            footfall = round(random.uniform(0.3, 0.95), 2)
            lead_score = round(footfall * 50 + random.uniform(20, 50), 1)

            merchant = Merchant(
                id=mid,
                shop_name=shop,
                owner_name=owner,
                category=cat,
                city=cluster["city"],
                area=cluster["name"],
                pincode="110001",
                lat=lat,
                lng=lng,
                language=lang,
                phone_e164=phone,
                preferred_channel="whatsapp",
                consent=True,
                footfall_score=footfall,
                lead_score=lead_score,
                score_explanation=f"High footfall {cat} in {cluster['name']}, nearby density",
                state=st,
                fse_id=cluster["fse_id"],
                created_at=now - timedelta(days=random.randint(1, 10))
            )
            db.add(merchant)

            # If ACTIVATING or ACTIVATED, add device and transactions
            if st in ("ACTIVATING", "ACTIVATED"):
                dev_status = "active" if st == "ACTIVATED" else "installed"
                dev = Device(
                    id=f"dev_{mid}",
                    merchant_id=mid,
                    status=dev_status,
                    installed_at=now - timedelta(days=random.randint(2, 8)),
                    first_txn_at=now - timedelta(days=1) if st == "ACTIVATED" else None
                )
                db.add(dev)

                txn_count = random.randint(10, 30) if st == "ACTIVATED" else random.randint(0, 5)
                for tx_i in range(txn_count):
                    txn = Transaction(
                        id=f"txn_{mid}_{tx_i}",
                        merchant_id=mid,
                        amount=round(random.uniform(40, 500), 2),
                        status="success",
                        created_at=now - timedelta(hours=random.randint(1, 72))
                    )
                    db.add(txn)

                if st == "ACTIVATED":
                    delayed = random.random() < 0.10
                    settlement = Settlement(
                        id=f"set_{mid}",
                        merchant_id=mid,
                        amount=round(random.uniform(1000, 8000), 2),
                        expected_date=now + timedelta(days=1) if delayed else now - timedelta(hours=6),
                        status="delayed" if delayed else "paid",
                        delay_reason="bank holiday" if delayed else None
                    )
                    db.add(settlement)

        db.commit()

        # 5. Seed Autonomy Config Defaults
        autonomy_defaults = [
            ("SEND_INTRO", "L3"),
            ("ANSWER_QUERY", "L3"),
            ("REQUEST_DOCS", "L3"),
            ("REREQUEST_DOC", "L3"),
            ("SCHEDULE_VISIT", "L3"),
            ("SEND_ACTIVATION_NUDGE", "L3"),
            ("EXPLAIN_SETTLEMENT", "L3"),
            ("WAIT", "L3"),
            ("ESCALATE", "L3"),
            ("CLOSE_LEAD", "L1"),
            ("OFFER_DISCOUNT", "L2")
        ]
        for action_type, lvl in autonomy_defaults:
            ac = AutonomyConfig(
                action_type=action_type,
                level=lvl,
                updated_by="system",
                updated_at=now
            )
            db.add(ac)

        # 6. Seed Demo State
        db.add(DemoState(key="clock_offset_seconds", value="0"))
        db.add(DemoState(key="slow_mode", value="false"))

        db.commit()

        total = db.query(Merchant).count()
        print(f"Database seeded successfully with {total} merchants and 4 FSEs.")

    finally:
        db.close()

    # Create pristine copy for instantaneous /demo/reset
    if "sqlite" in settings.DATABASE_URL:
        db_file = settings.DATABASE_URL.replace("sqlite:///", "")
        if os.path.exists(db_file):
            shutil.copy2(db_file, seed_copy_path)
            print(f"Pristine database snapshot created at {seed_copy_path}")

if __name__ == "__main__":
    seed_database()
