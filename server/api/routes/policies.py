"""
GET /api/policies/search?q=<query>&top_k=3
Returns the top matching policy document passages for a given query.
Used by the frontend to show which policy passage answered a merchant question.
"""
from fastapi import APIRouter, Query
from server.services.policy_search import policy_search_service

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("/search")
def search_policies(
    q: str = Query(..., description="Search query (Hindi/English/Hinglish)"),
    top_k: int = Query(3, ge=1, le=10, description="Number of passages to return"),
):
    """
    Full-text search over all policy documents in docs/policies/.
    Returns ranked passages with source file and heading.
    """
    results = policy_search_service.search(q, top_k=top_k)
    return {
        "query": q,
        "results": results,
        "total": len(results)
    }

