"""
emailservice — Main Application
Port: 8004 (replaces email-service)
Gateway prefix: /email-service (same as email-service in gateway registry)

Completely standalone — zero imports from email-service folder.
"""
from __future__ import annotations
import asyncio, sys, os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.config import get_config
from shared.logger import setup_logging, set_request_id, clear_request_id
from shared.database import init_database, close_database, check_database_health
from shared.cache import init_redis, close_redis, check_redis_health

import config as cfg
from kafka_client import ensure_topics, close_producer

logger = setup_logging("emailservice")
_config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("emailservice starting on port %d...", cfg.SERVICE_PORT)
    await init_database()
    await init_redis()
    await _create_tables()
    try:
        await ensure_topics()
        logger.info("Redis Streams ready")
    except Exception as e:
        logger.warning("Stream setup warning: %s", e)

    # Keep a reference to the recovery worker so we can close its httpx client on shutdown
    _recovery_worker = None

    async def _run_watch_sync():
        await asyncio.sleep(3)
        try:
            from workers.watch_manager import WatchManager
            await WatchManager().sync_all_watches()
        except Exception as e:
            logger.error("Startup watch sync failed: %s", e)

    async def _run_history_recovery():
        """
        Run once on startup to catch missed messages, then schedule
        the 6-day periodic check via run_forever().
        """
        nonlocal _recovery_worker
        await asyncio.sleep(12)
        try:
            from workers.history_recovery_worker import HistoryRecoveryWorker
            _recovery_worker = HistoryRecoveryWorker()
            # Startup: run once immediately (catches downtime gaps)
            await _recovery_worker.run_once()
            await _recovery_worker._mark_ran()
            # Then schedule every 6 days (non-blocking — runs in background)
            asyncio.create_task(_recovery_worker.run_forever())
        except Exception as e:
            logger.error("Startup history recovery failed: %s", e)

    asyncio.create_task(_run_watch_sync())
    asyncio.create_task(_run_history_recovery())

    # ── Start stream workers ──────────────────────────────────────────────────
    _pipeline_workers = []
    _imap_manager     = None
    _watch_manager_instance = None

    async def _start_workers():
        nonlocal _imap_manager, _watch_manager_instance
        await asyncio.sleep(2)
        try:
            from workers.gmail_fetch_worker import GmailFetchWorker
            from workers.storage_worker import StorageWorker
            from workers.ai_handoff_worker import AIHandoffWorker
            from workers.smtp_fetch_worker import ImapIdleManager
            from workers.watch_manager import WatchManager

            workers_to_start = [
                GmailFetchWorker(),   # gmail_events → pipeline → store_ready
                StorageWorker(),      # store_ready  → DB (with retry)
                AIHandoffWorker(),    # ai_events    → automation-service
            ]
            _pipeline_workers.extend(workers_to_start)
            for w in workers_to_start:
                asyncio.create_task(w.start())
                logger.info("Worker started: %s", w.__class__.__name__)

            # IMAP IDLE manager (replaces SmtpPoller — push-based, no polling)
            _imap_manager = ImapIdleManager()
            asyncio.create_task(_imap_manager.start())
            logger.info("ImapIdleManager started")

            # Heartbeat watchdog (dual-layer watch protection)
            _watch_manager_instance = WatchManager()
            asyncio.create_task(_watch_manager_instance.run_watchdog())
            logger.info("Watch heartbeat watchdog started")

            # Drain webhook fallback queue periodically
            asyncio.create_task(_drain_webhook_fallback())

        except Exception as e:
            logger.error("Worker startup failed: %s", e, exc_info=True)

    asyncio.create_task(_start_workers())

    # ── Start recovery worker ─────────────────────────────────────────────────
    _recovery_worker_instance = None

    async def _start_recovery_worker():
        nonlocal _recovery_worker_instance
        await asyncio.sleep(2)
        try:
            from workers.recovery_worker import RecoveryWorker
            _recovery_worker_instance = RecoveryWorker()
            asyncio.create_task(_recovery_worker_instance.start())
            logger.info("RecoveryWorker started")
        except Exception as e:
            logger.error("RecoveryWorker startup failed: %s", e, exc_info=True)

    asyncio.create_task(_start_recovery_worker())

    async def _drain_webhook_fallback():
        """Periodically retry events that failed XADD in the webhook handler."""
        while True:
            await asyncio.sleep(30)
            try:
                from api.webhooks import drain_fallback_queue
                await drain_fallback_queue()
            except Exception as e:
                logger.debug("Fallback drain error: %s", e)

    logger.info("emailservice ready on port %d", cfg.SERVICE_PORT)
    yield

    logger.info("emailservice shutting down...")
    for w in _pipeline_workers:
        try:
            await w.stop()
        except Exception as e:
            logger.warning("Worker stop error (%s): %s", w.__class__.__name__, e)
    if _imap_manager:
        await _imap_manager.stop()
    if _recovery_worker_instance:
        await _recovery_worker_instance.stop()
    from pipeline import close_http_client
    await close_http_client()
    if _recovery_worker:
        await _recovery_worker.close()
    await close_producer()
    await close_database()
    await close_redis()


app = FastAPI(
    title="emailservice",
    version="2.0.0",
    description="Enterprise email service — Redis Streams pipeline, 1M users",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = set_request_id()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        clear_request_id()


app.add_middleware(
    CORSMiddleware,
    allow_origins=_config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from api.webhooks   import router as webhooks_router
from api.connect    import router as connect_router
from api.inbox      import router as inbox_router
from api.send_reply import router as send_reply_router
from api.accounts   import router as accounts_router

app.include_router(webhooks_router)
app.include_router(connect_router)
app.include_router(inbox_router)
app.include_router(send_reply_router)
app.include_router(accounts_router)


# ── Health + Stats ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    db_ok    = await check_database_health()
    redis_ok = await check_redis_health()
    ok = db_ok and redis_ok
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status":    "healthy" if ok else "unhealthy",
            "service":   "emailservice",
            "version":   "2.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": "healthy" if db_ok else "unhealthy",
                "redis":    "healthy" if redis_ok else "unhealthy",
            },
        },
    )


@app.get("/stats")
async def stats():
    """Live pipeline stats."""
    from shared.cache import get_redis
    from shared.database import get_db_session
    from sqlalchemy import text
    from stream_client import get_stream_lag
    import config as cfg

    streams = [
        cfg.TOPIC_GMAIL_RAW, cfg.TOPIC_FETCH_RESULTS,
        cfg.TOPIC_STORE_READY, cfg.TOPIC_AI_EVENTS, cfg.TOPIC_DLQ,
    ]
    stream_stats = {}
    try:
        redis = await get_redis()
        for s in streams:
            try:
                length  = await redis.xlen(s)
                pending = await get_stream_lag(s, "")
                stream_stats[s] = {"length": length, "pending": pending}
            except Exception:
                stream_stats[s] = {"length": 0, "pending": 0}
    except Exception as e:
        stream_stats = {"error": str(e)}

    db_stats = {}
    try:
        async with get_db_session() as session:
            for table in ("es_messages", "es_conversations", "email_accounts"):
                try:
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    db_stats[table] = result.scalar()
                except Exception:
                    db_stats[table] = "n/a"
    except Exception as e:
        db_stats = {"error": str(e)}

    return {
        "service":   "emailservice",
        "timestamp": datetime.utcnow().isoformat(),
        "streams":   stream_stats,
        "db":        db_stats,
    }


@app.get("/")
async def root():
    return {"service": "emailservice", "version": "2.0.0", "status": "running", "port": cfg.SERVICE_PORT}


# ── Startup helpers ───────────────────────────────────────────────────────────

async def _create_tables() -> None:
    try:
        from shared.database import get_engine
        from models.email_account  import EmailAccount   # noqa
        from models.messages       import EmailMessage   # noqa
        from models.conversations  import EmailConversation  # noqa
        from shared.database.postgres import Base
        from sqlalchemy import text
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Drop content_html column if it still exists (one-time migration)
            try:
                await conn.execute(text(
                    "ALTER TABLE es_messages DROP COLUMN IF EXISTS content_html"
                ))
                logger.info("Dropped content_html column (if existed)")
            except Exception:
                pass
        logger.info("Tables ensured: email_accounts, es_messages, es_conversations")
    except Exception as e:
        logger.error("Table creation failed: %s", e)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=cfg.SERVICE_PORT,
        reload=False,
        workers=1,
        timeout_keep_alive=5,
        access_log=False,
    )
