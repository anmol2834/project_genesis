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
from models import EmailAccount, EmailProviderConfig, EmailAccountHealth, EmailSyncLog  # noqa: F401

from api import connect_router, accounts_router, oauth_config_router

logger = setup_logging("email-service")
config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Email Service starting up...")
    await init_database()
    await init_redis()
    
    # Create database tables for email-service models
    try:
        from shared.database import get_engine
        from models.email_account import Base as EmailBase
        
        engine = get_engine()
        async with engine.begin() as conn:
            # Create all tables defined in email-service models
            await conn.run_sync(EmailBase.metadata.create_all)
        logger.info("Email service database tables created/verified")
    except Exception as e:
        logger.error(f"Failed to create email service tables: {e}")
    
    logger.info("Email Service started successfully")
    yield
    logger.info("Email Service shutting down...")
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
        reload=False,  # Disabled to prevent Windows socket exhaustion
        workers=1,  # Single worker for Windows
        timeout_keep_alive=5,  # Reduce keep-alive timeout
    )
