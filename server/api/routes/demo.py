import os
import shutil
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from server.api.deps import get_repo, APIError
from server.db.repo import PlatformRepo
from server.adapters.clock import clock
from server.scheduler.loop import scheduler
from server.settings import settings

router = APIRouter(prefix="/demo", tags=["demo"])

class AdvanceRequest(BaseModel):
    hours: float = 24.0

class DemoStateRequest(BaseModel):
    enabled: bool = True

class DeviceEventRequest(BaseModel):
    merchant_id: str
    event: str  # installed, transaction
    count: Optional[int] = 1
    amount: Optional[float] = 150.0

@router.get("/state")
def get_demo_state(repo: PlatformRepo = Depends(get_repo)):
    state = {
        "clock_offset_seconds": float(repo.get_demo_state("clock_offset_seconds", clock.offset_seconds)),
        "slow_mode": bool(repo.get_demo_state("slow_mode", False)),
        "upload_dir": settings.UPLOAD_DIR,
    }
    return state

@router.post("/slow-mode")
def set_slow_mode(req: DemoStateRequest, repo: PlatformRepo = Depends(get_repo)):
    repo.set_demo_state("slow_mode", str(bool(req.enabled)).lower())
    return get_demo_state(repo=repo)

@router.post("/reset")
def reset_demo(repo: PlatformRepo = Depends(get_repo)):
    """
    Restores pristine seed database snapshot in under 3 seconds, clears uploads, resets clock.
    """
    clock.reset()
    repo.set_demo_state("clock_offset_seconds", 0)
    repo.set_demo_state("slow_mode", "false")
    repo.clear_uploads(settings.UPLOAD_DIR)

    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    seed_copy_path = db_path.replace(".db", ".seed.db")

    if os.path.exists(seed_copy_path):
        shutil.copy2(seed_copy_path, db_path)
    else:
        from server.db.seed import seed_database
        seed_database()

    return {
        "status": "reset_complete",
        "clock_now": clock.now().isoformat(),
        "clock_offset_seconds": 0,
        "slow_mode": False,
        "message": "Demo state restored to clean seed snapshot."
    }

@router.post("/advance")
def advance_clock(req: AdvanceRequest, repo: PlatformRepo = Depends(get_repo)):
    """
    Advances clock by N hours and executes due background jobs.
    """
    new_time = clock.advance(hours=req.hours)
    repo.set_demo_state("clock_offset_seconds", float(clock.offset_seconds))
    # Run due jobs immediately
    ran_jobs = scheduler.run_due_jobs_once(db=repo.db)

    return {
        "status": "clock_advanced",
        "advanced_hours": req.hours,
        "new_clock_time": new_time.isoformat(),
        "clock_offset_seconds": float(clock.offset_seconds),
        "jobs_executed": ran_jobs
    }

@router.post("/trigger/{scenario}")
def trigger_scenario(scenario: str, repo: PlatformRepo = Depends(get_repo)):
    sc = scenario.lower()
    hero_map = {
        "rahul": ("m_rahul", "CONTACTED"),
        "meena": ("m_meena", "DOCS_PENDING"),
        "sunil": ("m_sunil", "INSTALLED"),
        "farida": ("m_farida", "ACTIVATED"),
        "vikram": ("m_vikram", "ENGAGED"),
        "pooja": ("m_pooja", "NEW")
    }

    if sc not in hero_map:
        raise APIError("NOT_FOUND", f"Scenario {scenario} not found. Must be one of {list(hero_map.keys())}", status_code=404)

    mid, target_state = hero_map[sc]
    m = repo.get_merchant(mid)
    if not m:
        raise APIError("NOT_FOUND", f"Hero merchant {mid} not found in database", status_code=404)

    m.state = target_state
    m.state_updated_at = clock.now()
    repo.db.commit()

    return {
        "scenario": sc,
        "merchant_id": mid,
        "state": target_state,
        "message": f"Scenario {sc} initialized for merchant {m.shop_name}."
    }

@router.post("/device-event")
def handle_device_event(req: DeviceEventRequest, repo: PlatformRepo = Depends(get_repo)):
    """
    Simulates physical device installation or customer transactions.
    """
    m = repo.get_merchant(req.merchant_id)
    if not m:
        raise APIError("NOT_FOUND", f"Merchant {req.merchant_id} not found", status_code=404)

    if req.event == "installed":
        dev = repo.record_device_installed(req.merchant_id)
        return {
            "status": "device_installed",
            "merchant_id": req.merchant_id,
            "device_status": dev.status,
            "merchant_state": repo.get_merchant(req.merchant_id).state
        }
    elif req.event == "transaction":
        total_txns = repo.record_transactions(
            merchant_id=req.merchant_id,
            count=req.count or 1,
            amount_per_txn=req.amount or 150.0
        )
        return {
            "status": "transaction_recorded",
            "merchant_id": req.merchant_id,
            "added": req.count or 1,
            "total_transactions": total_txns,
            "merchant_state": repo.get_merchant(req.merchant_id).state
        }
    else:
        raise APIError("VALIDATION_ERROR", f"Unknown device event '{req.event}'. Must be 'installed' or 'transaction'.", status_code=400)

