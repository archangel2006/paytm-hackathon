import os
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from server.db.session import get_db
from server.adapters.clock import clock

router = APIRouter(tags=["health"])

@router.get("/health")
def get_health(db: Session = Depends(get_db)):
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    llm_configured = bool(os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    whatsapp_configured = bool(os.environ.get("WHATSAPP_TOKEN") or os.environ.get("WHATSAPP_PHONE_NUMBER_ID"))

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "llm_configured": llm_configured,
        "whatsapp_configured": whatsapp_configured,
        "clock_simulated_now": clock.now().isoformat(),
        "clock_offset_seconds": clock.offset_seconds
    }

