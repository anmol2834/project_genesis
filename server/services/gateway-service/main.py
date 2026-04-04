"""
Gateway Service - API Gateway
Entry point for all client requests
Port: 8000
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path for shared imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.config import get_config
from shared.logger import setup_logging, get_logger, set_request_id, clear_request_id
from shared.database import init_database, close_database, check_database_health
from shared.cache import init_redis, close_redis, check_redis_health
from router import route_request, close_http_client

# Initialize logger
logger = setup_logging("gateway-service")
config = get_config()

# Health check cache
_health_cache = {"status": None, "timestamp": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("Gateway Service starting up...")
    
    # Initialize connections
    await init_database()
    await init_redis()
    
    logger.info("Gateway Service started successfully")
    logger.info("Service routing enabled for all microservices")
    
    yield
    
    # Shutdown
    logger.info("Gateway Service shutting down...")
    
    # Close connections
    await close_database()
    await close_redis()
    await close_http_client()
    
    logger.info("Gateway Service shut down successfully")


# Create FastAPI application
app = FastAPI(
    title="Gateway Service",
    description="Enterprise API Gateway with Circuit Breaker, Rate Limiting, and Service Discovery",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """
    Middleware to add request ID to all requests
    """
    # Generate and set request ID
    request_id = set_request_id()
    
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        clear_request_id()


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    Returns service health status
    """
    # Use cached health status if available and fresh (< 10 seconds old)
    if _health_cache["status"] and _health_cache["timestamp"]:
        age = (datetime.utcnow() - _health_cache["timestamp"]).total_seconds()
        if age < 10:
            return _health_cache["status"]
    
    # Check database health
    db_healthy = await check_database_health()
    
    # Check Redis health
    redis_healthy = await check_redis_health()
    
    # Overall health status
    healthy = db_healthy and redis_healthy
    
    response = JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "service": "gateway-service",
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
    """
    Root endpoint
    """
    return {
        "service": "gateway-service",
        "version": "1.0.0",
        "status": "running",
        "features": [
            "Service Discovery",
            "Circuit Breaker",
            "Rate Limiting (60 req/min per endpoint)",
            "Automatic Retry with Exponential Backoff",
            "Request ID Tracking",
            "Connection Pooling"
        ]
    }


# ── Catch-all route for service forwarding ───────────────────────────────────
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def gateway_router(request: Request):
    """
    Main gateway router - forwards all requests to appropriate microservices
    """
    return await route_request(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,
        access_log=False,
        timeout_keep_alive=5,
    )
