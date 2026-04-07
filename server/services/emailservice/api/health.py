"""emailservice — Health check endpoint."""
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from shared.database import check_database_health
from shared.cache import check_redis_health

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    db_ok    = await check_database_health()
    redis_ok = await check_redis_health()
    ok = db_ok and redis_ok
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status":    "healthy" if ok else "unhealthy",
            "service":   "emailservice",
            "timestamp": datetime.utcnow().isoformat(),
            "checks":    {"database": "healthy" if db_ok else "unhealthy",
                          "redis":    "healthy" if redis_ok else "unhealthy"},
        },
    )


@router.get("/")
async def root():
    return {"service": "emailservice", "version": "2.0.0", "status": "running"}
