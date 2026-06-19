"""
Automation Service - Main Application
======================================
FastAPI application with enterprise lifecycle management.
"""

from contextlib import asynccontextmanager
from datetime import datetime
import sys
import os
import asyncio

# ── UTF-8 MUST be enforced before any other import opens a file handle ───────
# This prevents ₹ / € / other non-ASCII from crashing workers, logs, or
# OpenAI response handling.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from app.core.utf8_enforcement import enforce_utf8, validate_utf8_environment
enforce_utf8()
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import initialize_config
from shared.logger import setup_logging, set_request_id, clear_request_id
from shared.database import init_database, close_database, check_database_health
from shared.cache import init_redis, close_redis, check_redis_health


logger = setup_logging("automation-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager"""
    config = initialize_config()
    logger.info(
        "automation-service starting | port=%d version=%s",
        config.service.service_port,
        config.service.version
    )
    
    # Initialize infrastructure
    await init_database()
    await init_redis()
    logger.info("Infrastructure connections established")

    # Pre-load the embedding model at startup (not lazily on first request).
    # This ensures we fail fast on dimension mismatches and avoid cold-start
    # latency hitting the first real email.
    try:
        import asyncio as _asyncio
        from app.retrieval.embeddings import get_embedding_registry
        registry = await _asyncio.to_thread(get_embedding_registry)
        stats = registry.stats
        if registry.is_collection_compatible():
            logger.info(
                "✅ Embedding registry ready | model=%s dim=%d tier=%d load_ms=%.0f",
                stats["model"], stats["dim"], stats["tier"], stats["load_latency_ms"],
            )
        else:
            logger.warning(
                "⚠️  Embedding registry degraded | model=%s dim=%d (collection requires 768) — "
                "semantic search is DISABLED until a collection-compatible model loads.",
                stats["model"], stats["dim"],
            )
    except Exception as e:
        logger.error("Embedding registry startup failed: %s", e)

    # Validate UTF-8 after all streams/handlers are up
    utf8_ok, utf8_issues = validate_utf8_environment()
    if not utf8_ok:
        logger.critical(
            "UTF-8 validation FAILED at startup — %d issue(s). "
            "Non-ASCII characters (₹ € £ etc.) may corrupt logs, DB writes, "
            "and OpenAI responses. Issues: %s",
            len(utf8_issues), utf8_issues
        )
    else:
        logger.info("UTF-8 environment validated ✅")
    
    # Initialize resource pools
    from app.core.resource_management import initialize_resources
    await initialize_resources()
    logger.info("Resource pools initialized")
    
    # Start worker runtime
    from app.workers.runtime import get_worker_runtime
    worker_runtime = get_worker_runtime()
    await worker_runtime.start()
    
    # Create worker task
    worker_task = asyncio.create_task(worker_runtime.run())
    logger.info("✅ Worker runtime started and consuming from automation_events")
    
    logger.info("automation-service ready | port=%d", config.service.service_port)
    yield
    
    # Cleanup
    logger.info("automation-service shutting down...")
    
    # Stop workers first
    await worker_runtime.stop()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        logger.info("Worker task cancelled")
    
    # Shutdown resources
    from app.core.resource_management import shutdown_resources
    await shutdown_resources()
    
    await close_database()
    await close_redis()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    config = initialize_config()
    
    app = FastAPI(
        title="Automation Service",
        version=config.service.version,
        description="Enterprise AI automation platform with near-zero hallucination RAG",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.shared.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API routers (Task 18 / R4) ────────────────────────────────────────
    from app.api.health   import router as health_router
    from app.api.admin    import router as admin_router
    from app.api.internal import router as internal_router
    from app.api.metrics  import router as metrics_router

    app.include_router(health_router,    prefix="/api/health")
    app.include_router(admin_router,     prefix="/api/admin")
    app.include_router(internal_router,  prefix="/api/internal")
    app.include_router(metrics_router,   prefix="/api/metrics")
    
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        """Add request ID to all requests"""
        rid = set_request_id()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            clear_request_id()
    
    @app.get("/health")
    async def health():
        """Health check endpoint"""
        db_ok = await check_database_health()
        redis_ok = await check_redis_health()
        ok = db_ok and redis_ok
        
        return JSONResponse(
            status_code=200 if ok else 503,
            content={
                "status": "healthy" if ok else "unhealthy",
                "service": "automation-service",
                "version": config.service.version,
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {
                    "database": "healthy" if db_ok else "unhealthy",
                    "redis": "healthy" if redis_ok else "unhealthy",
                },
            },
        )
    
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "service": "automation-service",
            "version": config.service.version,
            "status": "running"
        }
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = initialize_config()

    # IMPORTANT — single worker process only.
    #
    # The automation-service uses a Redis Streams consumer (BLPOP + XRANGE) for
    # message processing.  Running multiple uvicorn worker *processes* (workers > 1)
    # causes every process to read the same stream entries simultaneously via XRANGE,
    # creating a race condition where the same email is processed by N processes.
    # The dedup key (automation:processed:{message_id}) with SET NX provides
    # correctness — only one process wins — but the remaining N-1 processes waste
    # an entire AI pipeline call before discovering the dedup hit.
    #
    # The correct pattern for horizontal scaling is:
    #   - Run ONE uvicorn process per container/VM (workers=1)
    #   - Scale horizontally by deploying multiple containers
    #   - Each container owns a separate Redis connection and wins its own BLPOP
    #     tokens; the dedup key still handles the rare race on the same message
    #
    # Async concurrency within the single process handles all I/O parallelism.
    # The worker loop itself supports AUTOMATION_WORKER_CONCURRENCY > 1 for
    # CPU-bound parallelism if needed.
    logger.info("Starting automation-service | workers=1 (single-process async)")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=config.service.service_port,
        reload=False,
        workers=1,          # Always 1 — see comment above
        access_log=False,
        timeout_keep_alive=30,
        backlog=2048,
    )
