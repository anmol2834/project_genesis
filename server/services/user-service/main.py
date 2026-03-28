"""
User Service - User Management
Handles user profiles, settings, preferences
Port: 8002
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.config import get_config
from shared.logger import setup_logging, set_request_id, clear_request_id
from shared.database import init_database, close_database, check_database_health
from shared.cache import init_redis, close_redis, check_redis_health
from api import settings_router, profile_router
from models import User, UserSettings  # Import models to register with SQLAlchemy

logger = setup_logging("user-service")
config = get_config()

# Health check cache
_health_cache = {"status": None, "timestamp": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("User Service starting up...")
    await init_database()
    await init_redis()
    logger.info("User Service started successfully")
    yield
    logger.info("User Service shutting down...")
    await close_database()
    await close_redis()
    logger.info("User Service shut down successfully")


app = FastAPI(
    title="User Service",
    description="User Management Service",
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

# Include routers
app.include_router(settings_router)
app.include_router(profile_router)


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
    # Use cached health status if available and fresh (< 10 seconds old)
    if _health_cache["status"] and _health_cache["timestamp"]:
        age = (datetime.utcnow() - _health_cache["timestamp"]).total_seconds()
        if age < 10:
            return _health_cache["status"]
    
    # Perform actual health check
    db_healthy = await check_database_health()
    redis_healthy = await check_redis_health()
    healthy = db_healthy and redis_healthy
    
    response = JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "service": "user-service",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": "healthy" if db_healthy else "unhealthy",
                "redis": "healthy" if redis_healthy else "unhealthy",
            }
        }
    )
    
    # Cache the result
    _health_cache["status"] = response
    _health_cache["timestamp"] = datetime.utcnow()
    
    return response


@app.get("/")
async def root():
    return {
        "service": "user-service",
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8002, 
        reload=False,  # Disabled to prevent Windows socket exhaustion
        workers=1,  # Single worker for Windows
        access_log=False,  # Disable access logs (200 OK, etc.)
        timeout_keep_alive=5,  # Reduce keep-alive timeout
    )
