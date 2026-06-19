"""
automationservice — Main Entry Point & Redis Notify Loop
Port: 8010
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

_SVC_DIR      = os.path.dirname(os.path.abspath(__file__))
_SERVICES_DIR = os.path.dirname(_SVC_DIR)
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)

for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.config import get_config
from shared.logger import setup_logging
from core.config import (
    SERVICE_PORT, SERVICE_NAME,
    AUTOMATION_STREAM, AUTOMATION_NOTIFY,
    NOTIFY_BLPOP_TIMEOUT, MAX_EVENTS_PER_CYCLE,
    PROCESSED_DEDUP_TTL,
)
from core.database import close_db
from api.router import router, process_event

logger = setup_logging(SERVICE_NAME)

_redis:       aioredis.Redis | None = None
_notify_task: asyncio.Task   | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        cfg = get_config()
        _redis = aioredis.from_url(
            cfg.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            max_connections=10,
        )
    return _redis


async def _close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


async def _notify_loop() -> None:
    logger.info("[notify_loop] started | stream=%s notify=%s blpop_timeout=%ds",
                AUTOMATION_STREAM, AUTOMATION_NOTIFY, NOTIFY_BLPOP_TIMEOUT)

    while True:
        try:
            redis = await _get_redis()

            result = await redis.blpop(AUTOMATION_NOTIFY, timeout=NOTIFY_BLPOP_TIMEOUT)

            if result is None:
                backlog = await redis.xlen(AUTOMATION_STREAM)
                if backlog > 0:
                    logger.info("[notify_loop] BLPOP timeout — draining backlog=%d", backlog)
                    await _drain_and_process(redis)
                continue

            _, notify_value = result
            try:
                notified_count = int(notify_value)
            except (ValueError, TypeError):
                notified_count = 1

            logger.info("[notify_loop] signal received | batch_count=%d", notified_count)

            pull_count = min(notified_count, MAX_EVENTS_PER_CYCLE)
            await _drain_and_process(redis, pull_count=pull_count)

            while True:
                remaining_tokens = await redis.llen(AUTOMATION_NOTIFY)
                stream_len       = await redis.xlen(AUTOMATION_STREAM)

                if stream_len == 0:
                    break

                if remaining_tokens > 0:
                    token_vals  = await redis.lrange(AUTOMATION_NOTIFY, 0, remaining_tokens - 1)
                    await redis.ltrim(AUTOMATION_NOTIFY, remaining_tokens, -1)
                    extra_count = sum(int(v) for v in token_vals if v and str(v).isdigit())
                    logger.info("[notify_loop] consumed %d pending tokens (extra=%d)", remaining_tokens, extra_count)

                pull_next = min(stream_len, MAX_EVENTS_PER_CYCLE)
                await _drain_and_process(redis, pull_count=pull_next)

        except asyncio.CancelledError:
            logger.info("[notify_loop] cancelled")
            break
        except Exception as e:
            logger.error("[notify_loop] error: %s", e, exc_info=True)
            await asyncio.sleep(2)


async def _drain_and_process(redis: aioredis.Redis, pull_count: int = MAX_EVENTS_PER_CYCLE) -> None:
    t0 = time.monotonic()

    try:
        messages = await redis.xrange(AUTOMATION_STREAM, "-", "+", count=pull_count)
    except Exception as e:
        logger.error("[drain] XRANGE failed: %s", e)
        return

    if not messages:
        return

    # XDEL all before processing (at-most-once delivery)
    pipe = redis.pipeline(transaction=False)
    for mid, _ in messages:
        pipe.xdel(AUTOMATION_STREAM, mid)
    try:
        await pipe.execute(raise_on_error=False)
    except Exception as e:
        logger.warning("[drain] XDEL warning: %s", e)

    processed = 0
    skipped   = 0

    for idx, (stream_id, fields) in enumerate(messages, start=1):
        raw = fields.get("data", "{}")
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("[drain] JSON parse error | stream_id=%s: %s", stream_id, e)
            skipped += 1
            continue

        message_id = event.get("message_id", "")

        # Redis-based dedup (survives restarts)
        if message_id:
            dedup_key = f"as:processed:{message_id}"
            acquired  = await redis.set(dedup_key, "1", nx=True, ex=PROCESSED_DEDUP_TTL)
            if not acquired:
                logger.debug("[drain] dedup skip | message_id=%s", message_id)
                skipped += 1
                continue

        try:
            await process_event(event)
            processed += 1
        except Exception as e:
            logger.error("[drain] process_event error | message_id=%s: %s", message_id, e, exc_info=True)
            skipped += 1

    elapsed_ms = (time.monotonic() - t0) * 1000
    logger.info("[drain] batch complete | total=%d processed=%d skipped=%d elapsed=%.0fms",
                len(messages), processed, skipped, elapsed_ms)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _notify_task

    cfg = get_config()

    logger.info("=" * 60)
    logger.info("automationservice starting | port=%d env=%s", SERVICE_PORT, cfg.ENVIRONMENT)
    logger.info("redis_url : %s...", cfg.REDIS_URL[:55])
    logger.info("db_url    : %s...", cfg.DATABASE_URL[:60])
    logger.info("=" * 60)

    # Redis connectivity check
    try:
        redis = await _get_redis()
        await redis.ping()
        stream_backlog = await redis.xlen(AUTOMATION_STREAM)
        notify_queue   = await redis.llen(AUTOMATION_NOTIFY)
        logger.info("Redis connected | stream_backlog=%d notify_queue=%d",
                    stream_backlog, notify_queue)
        if stream_backlog > 0:
            logger.warning("Startup backlog detected: %d events pending in %s",
                           stream_backlog, AUTOMATION_STREAM)
    except Exception as e:
        logger.error("Redis connection FAILED: %s", e)

    # DB connectivity check
    try:
        from core.database import _get_engine
        from sqlalchemy import text as _text
        engine = _get_engine()
        async with engine.begin() as conn:
            await conn.execute(_text("SELECT 1"))
        logger.info("Database connected")
    except Exception as e:
        logger.error("Database connection FAILED: %s", e)

    _notify_task = asyncio.create_task(_notify_loop())
    logger.info("Notify loop started — ready")

    # Pre-warm retrieval engine (BAAI/bge-m3 + Qdrant client)
    # Eliminates ~30s cold-start on first real request
    try:
        from services.qdrant_search import warmup as _qdrant_warmup
        await _qdrant_warmup()
    except Exception as _e:
        logger.warning("Retrieval warmup failed (non-fatal): %s", _e)

    yield

    logger.info("automationservice shutting down...")
    if _notify_task and not _notify_task.done():
        _notify_task.cancel()
        try:
            await _notify_task
        except asyncio.CancelledError:
            pass
    await _close_redis()
    await close_db()
    logger.info("automationservice stopped")


_cfg = get_config()

app = FastAPI(
    title="automationservice",
    version="1.0.0",
    description="Enterprise Automation Service — 2-Call LLM Pipeline",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cfg.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {"service": SERVICE_NAME, "version": "1.0.0", "status": "running", "port": SERVICE_PORT}


@app.get("/stats")
async def stats():
    try:
        redis      = await _get_redis()
        stream_len = await redis.xlen(AUTOMATION_STREAM)
        notify_len = await redis.llen(AUTOMATION_NOTIFY)
        return {
            "service":               SERVICE_NAME,
            "timestamp":             datetime.utcnow().isoformat(),
            "automation_stream_len": stream_len,
            "notify_queue_depth":    notify_len,
            "notify_loop_alive":     _notify_task is not None and not _notify_task.done(),
        }
    except Exception as e:
        return JSONResponse(status_code=503, content={"error": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=False,
        workers=1,
        timeout_keep_alive=5,
        access_log=False,
    )
