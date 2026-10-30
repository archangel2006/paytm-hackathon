from fastapi import APIRouter

from server.api.routes import (
    health,
    briefing,
    merchants,
    chat,
    documents,
    actions,
    handoffs,
    autonomy,
    scoreboard,
    simulation,
    audit,
    batch,
    demo,
    stream,
    events,
    policies,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(briefing.router)
api_router.include_router(merchants.router)
api_router.include_router(chat.router)
api_router.include_router(documents.router)
api_router.include_router(actions.router)
api_router.include_router(handoffs.router)
api_router.include_router(autonomy.router)
api_router.include_router(scoreboard.router)
api_router.include_router(simulation.router)
api_router.include_router(audit.router)
api_router.include_router(batch.router)
api_router.include_router(demo.router)
api_router.include_router(stream.router)
api_router.include_router(events.router)
api_router.include_router(policies.router)

