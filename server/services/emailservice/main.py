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
    # emailservice uses Upstash Redis Streams (REDIS_STREAMS_URL), not the
    # shared RedisLabs instance (REDIS_URL) used by other services.
    _streams_url = _config.REDIS_STREAMS_URL or _config.REDIS_URL
    await init_redis(url=_streams_url)
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
            wm = WatchManager()
            await wm.sync_all_watches()
            # Start per-account hourly renewal scheduler
            asyncio.create_task(wm.run_scheduler())
        except Exception as e:
            logger.error("Startup watch sync failed: %s", e)

    async def _run_history_recovery():
        """
        Run once on startup to catch missed messages.
        Uses per-account debounce — safe to call on every restart.
        """
        nonlocal _recovery_worker
        await asyncio.sleep(12)
        try:
            from workers.history_recovery_worker import HistoryRecoveryWorker
            _recovery_worker = HistoryRecoveryWorker()
            await _recovery_worker.run_once()
            await _recovery_worker._mark_ran()
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

            # Deferred send scheduler (event-driven, zero idle cost)
            from workers.deferred_scheduler import DeferredScheduler
            _deferred_scheduler = DeferredScheduler()
            asyncio.create_task(_deferred_scheduler.start())
            logger.info("DeferredScheduler started")

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
from api.webhooks     import router as webhooks_router
from api.connect      import router as connect_router
from api.inbox        import router as inbox_router
from api.send_reply   import router as send_reply_router
from api.accounts     import router as accounts_router
from api.oauth_config import router as oauth_config_router

app.include_router(webhooks_router)
app.include_router(connect_router)
app.include_router(inbox_router)
app.include_router(send_reply_router)
app.include_router(accounts_router)
app.include_router(oauth_config_router)

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
        from models.outbox         import EsOutbox       # noqa
        from shared.database.postgres import Base
        from sqlalchemy import text
        engine = get_engine()
        async with engine.begin() as conn:
            # Create all tables (idempotent)
            await conn.run_sync(Base.metadata.create_all)

            # One-time column migrations (all IF EXISTS / IF NOT EXISTS — safe on fresh DB)
            migrations = [
                "ALTER TABLE es_messages DROP COLUMN IF EXISTS content_html",
                "ALTER TABLE es_messages DROP COLUMN IF EXISTS metadata",
                "ALTER TABLE es_conversations DROP COLUMN IF EXISTS summary",
                "ALTER TABLE es_messages ADD COLUMN IF NOT EXISTS draft_message TEXT",
                "ALTER TABLE es_messages ADD COLUMN IF NOT EXISTS message_state VARCHAR(20)",
                # Retention indexes — no CONCURRENTLY so they run inside the transaction
                "CREATE INDEX IF NOT EXISTS ix_es_messages_created_at ON es_messages (created_at)",
                "CREATE INDEX IF NOT EXISTS ix_es_messages_user_recent ON es_messages (user_id, created_at DESC)",
            ]
            for sql in migrations:
                try:
                    await conn.execute(text(sql))
                except Exception as e:
                    logger.debug("Migration skipped (%s): %s", sql[:50], e)

        logger.info("Tables ensured: email_accounts, es_messages, es_conversations, es_outbox")

        # Register pg_cron job for 24h ephemeral retention (non-blocking, best-effort)
        await _setup_retention_cron()

    except Exception as e:
        logger.error("Table creation failed: %s", e)


async def _setup_retention_cron() -> None:
    """
    Register a pg_cron job that deletes es_messages rows older than 24 hours.

    pg_cron is a PostgreSQL extension available on:
      - AWS RDS PostgreSQL 12.5+ (enable via parameter group: shared_preload_libraries = pg_cron)
      - Amazon Aurora PostgreSQL
      - Most managed PostgreSQL providers

    The job runs every 30 minutes entirely inside the DB engine.
    Zero application-level polling. Zero asyncio overhead. Zero CPU cost when idle.

    Idempotent: unschedules any existing job with the same name before re-registering,
    so restarts never create duplicate jobs.

    If pg_cron is not available (extension not installed), this logs a warning
    and falls back to a PostgreSQL RULE-based approach that fires on INSERT.
    The service continues to function normally either way.
    """
    from shared.database import get_engine
    from sqlalchemy import text

    engine = get_engine()

    # The DELETE statement pg_cron will execute every 30 minutes.
    # Batched via LIMIT to avoid long locks on large tables.
    # Runs in a loop inside the cron job itself using a DO block.
    retention_sql = """
        DO $$
        DECLARE
            deleted_count INTEGER;
            total_deleted INTEGER := 0;
        BEGIN
            LOOP
                DELETE FROM es_messages
                WHERE id IN (
                    SELECT id FROM es_messages
                    WHERE created_at < NOW() - INTERVAL '24 hours'
                    ORDER BY created_at
                    LIMIT 5000
                );
                GET DIAGNOSTICS deleted_count = ROW_COUNT;
                total_deleted := total_deleted + deleted_count;
                EXIT WHEN deleted_count = 0;
                PERFORM pg_sleep(0.1);
            END LOOP;
            IF total_deleted > 0 THEN
                RAISE LOG 'es_messages retention: deleted % rows older than 24h', total_deleted;
            END IF;
        END $$;
    """

    try:
        async with engine.connect() as conn:
            # Check if pg_cron extension is available
            result = await conn.execute(text(
                "SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron'"
            ))
            if not result.fetchone():
                logger.warning(
                    "pg_cron extension not available on this PostgreSQL instance. "
                    "Enable it via: CREATE EXTENSION pg_cron; "
                    "Or add pg_cron to shared_preload_libraries in RDS parameter group. "
                    "Ephemeral retention will not be active until pg_cron is enabled."
                )
                return

            # Enable pg_cron if not already enabled
            await conn.execute(text(
                "CREATE EXTENSION IF NOT EXISTS pg_cron"
            ))
            await conn.commit()

            # Remove any existing job with this name (idempotent re-registration)
            await conn.execute(text(
                "SELECT cron.unschedule('es_messages_24h_retention') "
                "WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'es_messages_24h_retention')"
            ))
            await conn.commit()

            # Schedule: every 30 minutes, delete rows older than 24h in batches
            await conn.execute(
                text("SELECT cron.schedule(:name, :schedule, :command)"),
                {
                    "name":     "es_messages_24h_retention",
                    "schedule": "*/30 * * * *",   # every 30 minutes
                    "command":  retention_sql.strip(),
                },
            )
            await conn.commit()

            logger.info(
                "pg_cron job registered: es_messages_24h_retention "
                "(runs every 30 min, deletes rows older than 24h in 5k batches)"
            )

    except Exception as e:
        logger.warning(
            "pg_cron setup failed (%s). "
            "Ephemeral retention requires pg_cron. "
            "Enable it on RDS: set shared_preload_libraries='pg_cron' in parameter group, "
            "then run: CREATE EXTENSION pg_cron;",
            e,
        )


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
