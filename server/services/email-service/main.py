"""
Email Service - Email Integration & Processing
Gmail/Outlook integration, webhook handling
Port: 8004
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
from shared.cache import init_redis, close_redis, check_redis_health

# Register ORM models so SQLAlchemy creates tables on startup
from models import (
    EmailAccount,
    EmailProviderConfig,
    EmailAccountHealth,
    EmailSyncLog,
    EmailProviderSubscription
)  # noqa: F401

from api import connect_router, accounts_router, oauth_config_router
from api.webhooks import router as webhooks_router
from api.subscriptions import router as subscriptions_router
from api.monitoring import router as monitoring_router
from api.queue import router as queue_router
from api.inbox import router as inbox_router
from api.send_reply import router as send_reply_router

logger = setup_logging("email-service")
config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Email Service starting up...")
    await init_database()
    await init_redis()
    
    try:
        from shared.database import get_engine
        from models.email_account import Base as EmailBase
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(EmailBase.metadata.create_all)
    except Exception as e:
        logger.error(f"Failed to create email service tables: {e}")

    try:
        from shared.database import get_engine
        from sqlalchemy import text
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE email_accounts ADD COLUMN IF NOT EXISTS last_history_id VARCHAR(64) NULL"))
            await conn.execute(text("ALTER TABLE email_accounts ADD COLUMN IF NOT EXISTS watch_expiry TIMESTAMP WITHOUT TIME ZONE NULL"))
    except Exception as e:
        logger.error(f"Column migration failed: {e}")
    
    try:
        from provider.scheduler.background_tasks import get_task_manager
        task_manager = get_task_manager()
        await task_manager.start_all()
    except Exception as e:
        logger.error(f"Failed to start background tasks: {e}")

    # Auto-sync all connected accounts → register Gmail/Outlook watches
    # Runs in background so startup is not blocked
    import asyncio
    asyncio.create_task(_startup_sync_subscriptions())
    asyncio.create_task(_startup_history_recovery())

    logger.info("Email Service started successfully")
    yield
    
    # Shutdown
    logger.info("Email Service shutting down...")
    
    # Stop background tasks
    try:
        from provider.scheduler.background_tasks import get_task_manager
        task_manager = get_task_manager()
        await task_manager.stop_all()
        logger.info("Background tasks stopped")
    except Exception as e:
        logger.error(f"Error stopping background tasks: {e}")
    
    await close_database()
    await close_redis()


app = FastAPI(title="Email Service", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = set_request_id()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        clear_request_id()


app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(connect_router)
app.include_router(accounts_router)
app.include_router(oauth_config_router)
app.include_router(webhooks_router)
app.include_router(subscriptions_router)
app.include_router(monitoring_router)
app.include_router(queue_router)
app.include_router(inbox_router)
app.include_router(send_reply_router)


async def _startup_sync_subscriptions() -> None:
    """
    On startup: register Gmail/Outlook watches for every connected account.
    Ensures all accounts receive push notifications even after server restart.
    """
    import asyncio
    await asyncio.sleep(2)
    try:
        from provider.manager.subscription_manager import SubscriptionManager
        manager = SubscriptionManager()
        await manager.sync_all_subscriptions()
    except Exception as e:
        logger.error(f"Startup subscription sync failed: {e}", exc_info=True)


async def _startup_history_recovery() -> None:
    """
    On startup: recover any emails missed during downtime via Gmail History API.
    Runs after subscription sync to ensure watches are active first.
    """
    import asyncio
    await asyncio.sleep(10)  # Wait for subscription sync to complete first
    try:
        from recovery.history_sync import get_history_sync
        syncer = get_history_sync()
        await syncer.run_recovery_for_all()
    except Exception as e:
        logger.error(f"Startup history recovery failed: {e}", exc_info=True)


@app.get("/health")
async def health_check():
    db_healthy = await check_database_health()
    redis_healthy = await check_redis_health()
    healthy = db_healthy and redis_healthy
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "service": "email-service",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": "healthy" if db_healthy else "unhealthy",
                "redis": "healthy" if redis_healthy else "unhealthy",
            }
        }
    )


@app.get("/")
async def root():
    return {"service": "email-service", "version": "1.0.0", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=False,
        workers=1,
        timeout_keep_alive=5,
        access_log=False,   # suppress "POST /webhooks/gmail 200 OK" lines
    )
