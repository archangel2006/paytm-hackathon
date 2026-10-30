from fastapi import APIRouter, Depends, Query
from server.api.deps import get_repo
from server.db.repo import PlatformRepo

router = APIRouter(prefix="/agent", tags=["agent"])

@router.post("/run-batch")
def run_overnight_batch(limit: int = Query(120, ge=1, le=300), repo: PlatformRepo = Depends(get_repo)):
    """
    Simulates the overnight batch run over top ranked leads.
    """
    leads, _ = repo.list_merchants(sort_by="score", limit=limit)
    processed = 0
    contacted = 0

    for lead in leads:
        processed += 1
        if lead.state == "NEW":
            lead.state = "CONTACTED"
            contacted += 1
            repo.save_action(
                merchant_id=lead.id,
                action_type="SEND_INTRO",
                params={"template": "saathi_intro_hi" if lead.language == "hindi" else "saathi_intro_en"},
                reasoning=f"Overnight automated outreach for ranked lead #{processed} ({lead.shop_name})",
                confidence=0.92,
                autonomy_level="L3",
                status="executed"
            )

    repo.db.commit()

    return {
        "status": "completed",
        "leads_evaluated": processed,
        "newly_contacted": contacted,
        "message": f"Overnight batch executed successfully over {processed} leads."
    }

