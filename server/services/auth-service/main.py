"""
Auth Service - Authentication & Authorization
Port: 8001
Redis removed — OTP, rate limiting, and token blacklisting use PostgreSQL (auth_store table).
Embedding generation runs in a background thread pool (no Celery broker needed).
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.config import get_config
from shared.logger import setup_logging, set_request_id, clear_request_id
from shared.database import init_database, close_database, check_database_health, get_engine

from models.user import Base
from models.user_settings import UserSettings  # must import to register in Base.metadata
from api.auth import router as auth_router

logger = setup_logging("auth-service")
config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[STARTUP] Initializing database...")
    await init_database()

    # Create ORM tables (users, user_settings)
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[STARTUP] Database tables verified")
    except Exception as e:
        logger.error("Failed to create ORM tables: %s", e)

    # Create auth_store table (OTP / rate limit / token blacklist)
    try:
        from utils.db_store import ensure_table, cleanup_expired
        await ensure_table()
        deleted = await cleanup_expired()
        if deleted:
            logger.info("Cleaned up %d expired auth_store rows", deleted)
        print("[STARTUP] auth_store table ready")
    except Exception as e:
        logger.error("auth_store init failed: %s", e)

    print("[STARTUP] ✓ Auth Service Ready\n")
    yield
    print("\n[SHUTDOWN] Closing connections...")
    await close_database()
    print("[SHUTDOWN] ✓ Auth Service Stopped")


app = FastAPI(
    title="Auth Service",
    description="Authentication & Authorization Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
            "service": "auth-service",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": "healthy" if db_healthy else "unhealthy",
            },
        },
    )


@app.get("/")
async def root():
    return {"service": "auth-service", "version": "1.0.0", "status": "running"}


app.include_router(auth_router)


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("  AUTH SERVICE - PRODUCTION MODE")
    print("=" * 60)
    print(f"  Port: 8001")
    print(f"  Environment: {config.ENVIRONMENT}")
    print(f"  Debug: {config.DEBUG}")
    print("=" * 60 + "\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        workers=1,
        access_log=False,
        log_level="warning",
        timeout_keep_alive=5,
    )
