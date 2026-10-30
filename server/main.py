import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server.settings import settings
from server.db.session import init_db, SessionLocal
from server.api.router import api_router
from server.adapters.clock import clock
from server.adapters.agent_store import AgentStoreAdapter
from server.adapters.integrations_store import IntegrationsStoreAdapter
from server.scheduler.loop import scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist
    init_db()

    # Wire agent and integrations if available
    db = SessionLocal()
    try:
        agent_store = AgentStoreAdapter(db)
        integ_store = IntegrationsStoreAdapter(db)

        try:
            import agent
            import integrations
            from integrations import documents, router
            from integrations.whatsapp import webhook
            agent.configure(
                store=agent_store,
                channel=router,
                documents=documents,
                clock=clock
            )
            integrations.configure(
                store=integ_store,
                on_incoming=agent.handle_incoming,
                clock=clock
            )
            scheduler.set_handler(agent.handle_timer)
            app.include_router(webhook.router)
            logger.info("Agent and Integrations successfully wired.")
        except ImportError:
            logger.exception(
                "Agent and Integrations could not be wired because an import failed."
            )
    finally:
        db.close()

    # Start background scheduler loop
    scheduler_task = asyncio.create_task(scheduler.start())

    yield

    # Shutdown
    scheduler.stop()
    scheduler_task.cancel()

app = FastAPI(
    title="Paytm Saathi Platform API",
    version="0.1.0",
    description="Backend API for Paytm Saathi Autonomous AI Teammate",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR",
                "message": str(exc.detail),
                "details": {}
            }
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()}
            }
        }
    )

# Standardized Error Handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", None)

    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=status_code, content=detail)

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": "INTERNAL_ERROR" if status_code == 500 else "API_ERROR",
                "message": str(exc),
                "details": {}
            }
        }
    )

# Mount REST API
app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
