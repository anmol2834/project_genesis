"""
Automation Service - Automation & Workflows
Port: 8009
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.config import get_config
from shared.logger import setup_logging, set_request_id, clear_request_id
from shared.database import init_database, close_database, check_database_health

logger = setup_logging("automation-service")
config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Automation Service starting up...")
    await init_database()

    # Ensure learning engine tables exist
    try:
        from shared.database import get_db_session
        from learning_engine.repository import create_tables
        async with get_db_session() as session:
            await create_tables(session)
        logger.info("Learning engine tables ready.")
    except Exception as exc:
        logger.warning("Learning engine table init failed (non-fatal): %s", exc)

    # Register Celery Beat schedule for learning jobs
    try:
        from learning_engine.scheduler import register_beat_schedule
        register_beat_schedule()
    except Exception as exc:
        logger.warning("Learning engine scheduler registration failed (non-fatal): %s", exc)

    logger.info("Automation Service started successfully")

    # ── Warm up AI models at startup (eliminates first-request latency) ──
    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def _warmup():
            from ai_engine.intent_engine.utils import get_embedding_model, get_anchor_vectors
            from ai_engine.intent_engine.classifier import get_zero_shot_classifier
            get_embedding_model()
            get_anchor_vectors()
            get_zero_shot_classifier()

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            await loop.run_in_executor(pool, _warmup)
        logger.info("AI models warmed up — zero first-request latency.")
    except Exception as exc:
        logger.warning("AI model warmup failed (non-fatal, will load on first request): %s", exc)

    yield
    logger.info("Automation Service shutting down...")
    await close_database()


app = FastAPI(title="Automation Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register AI process router
from api.ai_process import router as ai_router
app.include_router(ai_router)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = set_request_id()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        clear_request_id()


@app.get("/health")
async def health_check():
    db_healthy = await check_database_health()
    return JSONResponse(
        status_code=200 if db_healthy else 503,
        content={
            "status": "healthy" if db_healthy else "unhealthy",
            "service": "automation-service",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": "healthy" if db_healthy else "unhealthy",
            },
        },
    )


@app.get("/")
async def root():
    return {"service": "automation-service", "version": "1.0.0", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8009, reload=config.DEBUG)
