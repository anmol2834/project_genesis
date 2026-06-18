"""
automationservice — Main Entry Point & Redis Notify Loop
=========================================================
Port: 8010

Architecture:
  emailservice ai_handoff_worker publishes:
    1. XADD  automation_events  {data: <json payload>}   (one entry per email)
    2. LPUSH automation_notify  <batch_count>             (wake signal, O(1))

  This service runs a background notify loop that:
    1. BLPOP automation_notify     → zero-cost sleep until signal arrives
    2. Parse batch_count from notification value
    3. XRANGE automation_events    → drain up to batch_count entries
    4. XDEL all drained entries    → at-most-once, prevents double-processing
    5. process_event() each entry  → pipeline steps 1-2
    6. After batch: check stream length
       → still has messages → process immediately (no signal needed, no polling)
       → empty             → go back to BLPOP

sys.path note:
  This file lives at: server/services/automationservice/main.py
  server/ is 3 levels up:
    dirname(__file__)   = .../automationservice
    up 1                = .../services
    up 2                = .../server   ← correct
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

# ── sys.path: resolve server/ root ────────────────────────────────────────────
_SVC_DIR      = os.path.dirname(os.path.abspath(__file__))   # .../automationservice
_SERVICES_DIR = os.path.dirname(_SVC_DIR)                    # .../services
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)               # .../server  ← shared/ is here

for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Shared imports (resolve after sys.path is set) ────────────────────────────
from shared.config import get_config
from shared.logger import setup_logging

# ── Service-local imports ─────────────────────────────────────────────────────
from core.config import (
    SERVICE_PORT, SERVICE_NAME,
    AUTOMATION_STREAM, AUTOMATION_NOTIFY,
    NOTIFY_BLPOP_TIMEOUT, MAX_EVENTS_PER_CYCLE,
    PROCESSED_DEDUP_TTL,
)
from core.database import close_db
from api.router import router, process_event

# ── Logging — use shared setup_logging() exactly like emailservice does ───────
logger = setup_logging(SERVICE_NAME)

# ── Module-level state ────────────────────────────────────────────────────────
_redis:       aioredis.Redis | None = None
_notify_task: asyncio.Task   | None = None


# ── Redis client ───────────────────────────────────────────────────────────────

async def _get_redis() -> aioredis.Redis:
    """
    Singleton Redis client.
    Always reads REDIS_URL from shared config — single source of truth.
    The .env REDIS_URL is Upstash TLS (rediss://) — redis-py handles SSL
    automatically from the URL scheme.
    """
    global _redis
    if _redis is None:
        cfg = get_config()
        _redis = aioredis.from_url(
            cfg.REDIS_URL,                 # rediss:// from .env — same as emailservice
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


# ── Redis Notify Loop ──────────────────────────────────────────────────────────

async def _notify_loop() -> None:
    """
    Event-driven core loop — zero idle Redis cost.

    Phases:
      A. BLPOP automation_notify  — sleep until emailservice pushes a signal
      B. Drain + process          — XRANGE → XDEL → process_event() per entry
      C. Backlog check            — while stream non-empty, keep processing
         (handles burst: multiple emails arrive while we were processing one)
    """
    logger.info("[notify_loop] started | stream=%s notify=%s", AUTOMATION_STREAM, AUTOMATION_NOTIFY)
    print(f"\n[AUTOMATIONSERVICE] 🟢 Redis notify loop STARTED")
    print(f"  stream       : {AUTOMATION_STREAM}")
    print(f"  notify list  : {AUTOMATION_NOTIFY}")
    print(f"  blpop timeout: {NOTIFY_BLPOP_TIMEOUT}s")
    print(f"  max per cycle: {MAX_EVENTS_PER_CYCLE}")

    while True:
        try:
            redis = await _get_redis()

            # ── Phase A: Sleep until signal ────────────────────────────────────
            print(f"\n[AUTOMATIONSERVICE] 💤 BLPOP '{AUTOMATION_NOTIFY}' (timeout={NOTIFY_BLPOP_TIMEOUT}s)...")
            result = await redis.blpop(AUTOMATION_NOTIFY, timeout=NOTIFY_BLPOP_TIMEOUT)

            if result is None:
                # Timeout — no signal received. Check for residual backlog.
                backlog = await redis.xlen(AUTOMATION_STREAM)
                if backlog > 0:
                    print(f"[AUTOMATIONSERVICE] 🔄 BLPOP timeout | backlog={backlog} — draining")
                    logger.info("[notify_loop] BLPOP timeout, draining backlog=%d", backlog)
                    await _drain_and_process(redis)
                else:
                    print(f"[AUTOMATIONSERVICE] 💤 BLPOP timeout | stream empty — back to sleep")
                continue

            # ── Phase B: Signal received ───────────────────────────────────────
            _, notify_value = result
            try:
                notified_count = int(notify_value)
            except (ValueError, TypeError):
                notified_count = 1

            print(f"\n[AUTOMATIONSERVICE] 🔔 SIGNAL RECEIVED")
            print(f"  notify_value  : '{notify_value}' → batch_count={notified_count}")
            print(f"  timestamp     : {datetime.utcnow().isoformat()}")
            logger.info("[notify_loop] signal received | batch_count=%d", notified_count)

            pull_count = min(notified_count, MAX_EVENTS_PER_CYCLE)
            await _drain_and_process(redis, pull_count=pull_count)

            # ── Phase C: Backlog check — drain all queued emails without polling ─
            while True:
                remaining_tokens = await redis.llen(AUTOMATION_NOTIFY)
                stream_len       = await redis.xlen(AUTOMATION_STREAM)

                print(f"\n[AUTOMATIONSERVICE] 🔁 BACKLOG CHECK")
                print(f"  notify tokens pending : {remaining_tokens}")
                print(f"  stream messages left  : {stream_len}")

                if stream_len == 0:
                    print(f"[AUTOMATIONSERVICE] ✅ Stream fully drained — back to BLPOP")
                    break

                # Consume all pending notify tokens so they don't cause redundant wakes
                if remaining_tokens > 0:
                    token_vals  = await redis.lrange(AUTOMATION_NOTIFY, 0, remaining_tokens - 1)
                    await redis.ltrim(AUTOMATION_NOTIFY, remaining_tokens, -1)
                    extra_count = sum(int(v) for v in token_vals if v and str(v).isdigit())
                    print(f"[AUTOMATIONSERVICE] 📊 Consumed {remaining_tokens} tokens (extra_count={extra_count})")
                    logger.info("[notify_loop] consumed %d pending tokens (extra=%d)", remaining_tokens, extra_count)

                pull_next = min(stream_len, MAX_EVENTS_PER_CYCLE)
                print(f"[AUTOMATIONSERVICE] ⬇️  Processing next backlog batch: pull={pull_next}")
                await _drain_and_process(redis, pull_count=pull_next)

        except asyncio.CancelledError:
            logger.info("[notify_loop] cancelled — shutting down")
            print(f"\n[AUTOMATIONSERVICE] 🔴 Notify loop CANCELLED")
            break
        except Exception as e:
            logger.error("[notify_loop] unexpected error: %s", e, exc_info=True)
            print(f"\n[AUTOMATIONSERVICE] ❌ Notify loop ERROR: {e}")
            await asyncio.sleep(2)   # brief back-off before retrying


async def _drain_and_process(redis: aioredis.Redis, pull_count: int = MAX_EVENTS_PER_CYCLE) -> None:
    """
    XRANGE up to pull_count entries → XDEL all → dedup check → process_event() each.

    Delivery guarantee: at-most-once.
    XDEL happens BEFORE processing so a crash between XDEL and process_event
    does not cause double-processing. The 1h Redis dedup key is a second safety net.
    """
    t0 = time.monotonic()

    try:
        messages = await redis.xrange(AUTOMATION_STREAM, "-", "+", count=pull_count)
    except Exception as e:
        logger.error("[drain] XRANGE failed: %s", e)
        print(f"[AUTOMATIONSERVICE] ❌ XRANGE error: {e}")
        return

    if not messages:
        print(f"[AUTOMATIONSERVICE] ℹ️  XRANGE returned 0 messages (stream empty or raced)")
        return

    print(f"\n[AUTOMATIONSERVICE] 📦 DRAINING {len(messages)} event(s) from '{AUTOMATION_STREAM}'")
    logger.info("[drain] draining %d events", len(messages))

    # ── XDEL all in one pipeline (before processing) ─────────────────────────
    pipe = redis.pipeline(transaction=False)
    for mid, _ in messages:
        pipe.xdel(AUTOMATION_STREAM, mid)
    try:
        await pipe.execute(raise_on_error=False)
    except Exception as e:
        logger.warning("[drain] XDEL pipeline warning (non-fatal): %s", e)

    processed = 0
    skipped   = 0

    for idx, (stream_id, fields) in enumerate(messages, start=1):
        raw = fields.get("data", "{}")
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("[drain] JSON parse error | stream_id=%s: %s", stream_id, e)
            print(f"[AUTOMATIONSERVICE] ❌ JSON parse error | stream_id={stream_id}: {e}")
            skipped += 1
            continue

        message_id = event.get("message_id", "")

        # ── Redis-based dedup (survives service restarts) ─────────────────────
        if message_id:
            dedup_key = f"as:processed:{message_id}"
            acquired  = await redis.set(dedup_key, "1", nx=True, ex=PROCESSED_DEDUP_TTL)
            if not acquired:
                logger.debug("[drain] dedup skip | message_id=%s", message_id)
                print(f"[AUTOMATIONSERVICE] ⏭️  DEDUP SKIP [{idx}/{len(messages)}] "
                      f"message_id={message_id[:20]}...")
                skipped += 1
                continue

        print(f"\n[AUTOMATIONSERVICE] ▶️  PROCESSING EVENT [{idx}/{len(messages)}]")
        print(f"  stream_id  : {stream_id}")
        print(f"  message_id : {message_id}")
        print(f"  user_id    : {event.get('user_id', '?')}")
        print(f"  from_email : {event.get('from_email', '?')}")
        print(f"  subject    : {event.get('subject', '?')}")
        print(f"  provider   : {event.get('provider', '?')}")

        try:
            result = await process_event(event)
            processed += 1

            status    = result.get("status", "?")
            elapsed   = result.get("elapsed_ms")
            elapsed_s = f"{elapsed:.1f}ms" if isinstance(elapsed, float) else str(elapsed)
            print(f"\n[AUTOMATIONSERVICE] 📊 EVENT RESULT [{idx}/{len(messages)}]")
            print(f"  status       : {status}")
            print(f"  fetch_count  : {result.get('fetch_count', 'n/a')}")
            print(f"  fetch_reason : {result.get('fetch_reason', 'n/a')}")
            print(f"  elapsed_ms   : {elapsed_s}")

        except Exception as e:
            logger.error("[drain] process_event error | message_id=%s: %s", message_id, e, exc_info=True)
            print(f"[AUTOMATIONSERVICE] ❌ PROCESS ERROR | message_id={message_id}: {e}")
            skipped += 1

    elapsed_ms = (time.monotonic() - t0) * 1000
    print(f"\n[AUTOMATIONSERVICE] 📊 BATCH SUMMARY")
    print(f"  total     : {len(messages)}")
    print(f"  processed : {processed}")
    print(f"  skipped   : {skipped}")
    print(f"  elapsed   : {elapsed_ms:.1f}ms")
    logger.info(
        "[drain] batch complete | total=%d processed=%d skipped=%d elapsed=%.0fms",
        len(messages), processed, skipped, elapsed_ms,
    )


# ── FastAPI Lifespan ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _notify_task

    cfg = get_config()

    logger.info("%s starting on port %d | env=%s", SERVICE_NAME, SERVICE_PORT, cfg.ENVIRONMENT)
    print(f"\n{'='*70}")
    print(f"[AUTOMATIONSERVICE] 🚀 SERVICE STARTING")
    print(f"  port        : {SERVICE_PORT}")
    print(f"  service     : {SERVICE_NAME}")
    print(f"  environment : {cfg.ENVIRONMENT}")
    print(f"  redis_url   : {cfg.REDIS_URL[:50]}...")
    print(f"  db_url      : {cfg.DATABASE_URL[:60]}...")
    print(f"{'='*70}\n")

    # ── Verify Redis connectivity ──────────────────────────────────────────────
    try:
        redis = await _get_redis()
        await redis.ping()
        stream_len = await redis.xlen(AUTOMATION_STREAM)
        notify_len = await redis.llen(AUTOMATION_NOTIFY)
        logger.info("Redis connected | stream_backlog=%d notify_queue=%d", stream_len, notify_len)
        print(f"[AUTOMATIONSERVICE] ✅ Redis connected")
        print(f"  {AUTOMATION_STREAM} backlog : {stream_len}")
        print(f"  {AUTOMATION_NOTIFY} queue  : {notify_len}")
        if stream_len > 0:
            print(f"[AUTOMATIONSERVICE] ⚠️  Startup backlog detected ({stream_len} events) — will drain on first wake")
    except Exception as e:
        logger.error("Redis connection FAILED: %s", e)
        print(f"[AUTOMATIONSERVICE] ❌ Redis connection FAILED: {e}")

    # ── Verify DB connectivity ─────────────────────────────────────────────────
    try:
        from core.database import _get_engine
        from sqlalchemy import text as _text
        engine = _get_engine()
        async with engine.begin() as conn:
            await conn.execute(_text("SELECT 1"))
        logger.info("Database connected")
        print(f"[AUTOMATIONSERVICE] ✅ Database connected")
    except Exception as e:
        logger.error("Database connection FAILED: %s", e)
        print(f"[AUTOMATIONSERVICE] ❌ Database connection FAILED: {e}")

    # ── Start notify loop ──────────────────────────────────────────────────────
    _notify_task = asyncio.create_task(_notify_loop())
    logger.info("Redis notify loop task started")
    print(f"[AUTOMATIONSERVICE] ✅ Notify loop task started\n")

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("%s shutting down...", SERVICE_NAME)
    print(f"\n[AUTOMATIONSERVICE] 🔴 SERVICE SHUTTING DOWN")

    if _notify_task and not _notify_task.done():
        _notify_task.cancel()
        try:
            await _notify_task
        except asyncio.CancelledError:
            pass

    await _close_redis()
    await close_db()

    logger.info("%s stopped", SERVICE_NAME)
    print(f"[AUTOMATIONSERVICE] ✅ Shutdown complete")


# ── FastAPI app ────────────────────────────────────────────────────────────────

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
    return {
        "service": SERVICE_NAME,
        "version": "1.0.0",
        "status":  "running",
        "port":    SERVICE_PORT,
    }


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
