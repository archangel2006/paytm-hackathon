from fastapi import APIRouter, Query

import agent

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/run-batch")
def run_overnight_batch(limit: int = Query(120, ge=1, le=300)):
    """Run the agent's guarded outreach over the highest-scoring new leads."""
    results = agent.run_batch(limit=limit)
    contacted = sum(
        result.reply_sent and result.state_after.value == "CONTACTED"
        for result in results
    )
    failed = sum(
        any(action.status.value == "failed" for action in result.actions)
        for result in results
    )
    return {
        "status": "completed" if failed == 0 else "partial",
        "leads_evaluated": len(results),
        "newly_contacted": contacted,
        "failed": failed,
        "message": (
            f"Overnight batch completed for {len(results)} new leads; "
            f"{contacted} were contacted and {failed} actions failed."
        ),
    }
