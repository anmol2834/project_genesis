"""
Automation Service - Main Application
======================================
Enterprise FastAPI application with core runtime integration.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import sys
import os

# Add server root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.config import get_config
from app.core import (
    get_runtime,
    create_startup_sequence,
    create_shutdown_sequence,
    get_health_system
)
from app.observability import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.
    Integrates core runtime for enterprise startup/shutdown.
    """
    config = get_config()
    logger.info(
        "automation-service starting | environment=%s",
        config.ENVIRONMENT
    )
    
    # Execute startup sequence
    startup = await create_startup_sequence()
    await startup.execute()
    
    # Start worker runtime in background
    runtime = get_runtime()
    worker_task = asyncio.create_task(runtime.run_workers())
    
    logger.info("automation-service ready")
    
    yield
    
    # Cleanup
    logger.info("automation-service shutting down...")
    
    # Cancel worker task
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    
    # Execute shutdown sequence
    shutdown = await create_shutdown_sequence()
    await shutdown.execute()
    
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    config = get_config()
    
    app = FastAPI(
        title="Automation Service",
        version="2.0.0",
        description="Enterprise AI automation platform with distributed execution",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        """Add request ID to all requests"""
        import uuid
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    
    @app.get("/health")
    async def health():
        """Deep health check endpoint"""
        health_system = get_health_system()
        health_result = await health_system.check_all()
        
        status_code = 200 if health_result["status"] == "healthy" else 503
        
        return JSONResponse(
            status_code=status_code,
            content=health_result
        )
    
    @app.get("/health/live")
    async def liveness():
        """Kubernetes liveness probe"""
        return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}
    
    @app.get("/health/ready")
    async def readiness():
        """Kubernetes readiness probe"""
        from app.core import get_resource_manager
        
        try:
            manager = get_resource_manager()
            health = await manager.health_check()
            
            # Ready if Redis and DB are healthy
            redis_ok = health["redis"]["status"] == "healthy"
            db_ok = health["database"]["status"] == "healthy"
            ready = redis_ok and db_ok
            
            return JSONResponse(
                status_code=200 if ready else 503,
                content={
                    "status": "ready" if ready else "not_ready",
                    "checks": health,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    
    @app.get("/")
    async def root():
        """Root endpoint"""
        runtime = get_runtime()
        uptime = None
        if runtime.started_at:
            uptime = (datetime.utcnow() - runtime.started_at).total_seconds()
        
        return {
            "service": "automation-service",
            "version": "2.0.0",
            "status": "running" if runtime.is_running else "stopped",
            "uptime_seconds": round(uptime, 2) if uptime else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/metrics")
    async def metrics():
        """Metrics endpoint for Prometheus scraping"""
        from app.observability import get_metrics_collector
        
        metrics_collector = get_metrics_collector()
        # TODO: Export metrics in Prometheus format
        return {"status": "metrics_endpoint", "collector": "active"}
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    config = get_config()
    port = int(os.getenv("PORT", "8009"))
    
    logger.info(f"Starting automation-service on port {port}")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        workers=1,  # Single worker with async runtime
        access_log=False,
        timeout_keep_alive=30,
        backlog=2048,
    )
