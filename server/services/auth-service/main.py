"""
Auth Service - Authentication & Authorization
Handles JWT tokens, OAuth, user authentication
Port: 8001
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
from shared.database import init_database, close_database, check_database_health, get_engine
from shared.cache import init_redis, close_redis, check_redis_health

from models.user import Base
from api.auth import router as auth_router

logger = setup_logging("auth-service")
config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[STARTUP] Initializing database...")
    await init_database()
    print("[STARTUP] Initializing Redis...")
    await init_redis()
    
    # Create database tables
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[STARTUP] Database tables verified")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
    
    print("[STARTUP] ✓ Auth Service Ready\n")
    yield
    print("\n[SHUTDOWN] Closing connections...")
    await close_database()
    await close_redis()
    print("[SHUTDOWN] ✓ Auth Service Stopped")


app = FastAPI(
    title="Auth Service",
    description="Authentication & Authorization Service",
    version="1.0.0",
    lifespan=lifespan
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
    redis_healthy = await check_redis_health()
    healthy = db_healthy and redis_healthy
    
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "service": "auth-service",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": "healthy" if db_healthy else "unhealthy",
                "redis": "healthy" if redis_healthy else "unhealthy",
            }
        }
    )


@app.get("/")
async def root():
    return {
        "service": "auth-service",
        "version": "1.0.0",
        "status": "running"
    }


# Include routers
app.include_router(auth_router)


if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("  AUTH SERVICE - PRODUCTION MODE")
    print("="*60)
    print(f"  Port: 8001")
    print(f"  Environment: {config.ENVIRONMENT}")
    print(f"  Debug: {config.DEBUG}")
    print("="*60 + "\n")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=config.DEBUG,
        access_log=False,
        log_level="warning"
    )
