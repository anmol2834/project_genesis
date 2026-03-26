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
from shared.database import init_database, close_database, check_database_health
from shared.cache import init_redis, close_redis, check_redis_health

logger = setup_logging("auth-service")
config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Auth Service starting up...")
    await init_database()
    await init_redis()
    logger.info("Auth Service started successfully")
    yield
    logger.info("Auth Service shutting down...")
    await close_database()
    await close_redis()
    logger.info("Auth Service shut down successfully")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=config.DEBUG)
