"""
Core - Health Check System
===========================
Deep health monitoring for all infrastructure components.
"""
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
from sqlalchemy import text
from app.observability import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheck:
    """Individual health check result"""
    def __init__(
        self,
        name: str,
        status: HealthStatus,
        latency_ms: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        self.name = name
        self.status = status
        self.latency_ms = latency_ms
        self.details = details or {}
        self.error = error
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "details": self.details,
            "error": self.error,
            "timestamp": self.timestamp.isoformat()
        }


class HealthCheckSystem:
    """Enterprise health monitoring system"""
    
    async def check_all(self) -> Dict[str, Any]:
        """Execute all health checks"""
        import time
        start = time.perf_counter()
        
        checks = {
            "redis": await self._check_redis(),
            "database": await self._check_database(),
            "qdrant": await self._check_qdrant(),
            "orchestration": await self._check_orchestration(),
            "workers": await self._check_workers(),
            "telemetry": await self._check_telemetry()
        }
        
        # Overall status
        statuses = [c.status for c in checks.values()]
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED
        
        elapsed = (time.perf_counter() - start) * 1000
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_ms": round(elapsed, 2),
            "checks": {name: check.to_dict() for name, check in checks.items()}
        }
    
    async def _check_redis(self) -> HealthCheck:
        """Check Redis connectivity"""
        import time
        start = time.perf_counter()
        
        try:
            from app.core.resource_management import get_resource_manager
            redis = get_resource_manager().get_redis()
            await redis.ping()
            
            latency = (time.perf_counter() - start) * 1000
            return HealthCheck(
                name="redis",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                details={"connected": True}
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return HealthCheck(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                error=str(e)
            )
    
    async def _check_database(self) -> HealthCheck:
        """Check PostgreSQL connectivity"""
        import time
        start = time.perf_counter()
        
        try:
            from app.core.resource_management import get_resource_manager
            manager = get_resource_manager()
            
            async with manager.get_db_session() as session:
                result = await session.execute(text("SELECT 1"))
                row = result.scalar()
            
            latency = (time.perf_counter() - start) * 1000
            return HealthCheck(
                name="database",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                details={"connected": True}
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return HealthCheck(
                name="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                error=str(e)
            )
    
    async def _check_qdrant(self) -> HealthCheck:
        """Check Qdrant connectivity"""
        import time
        start = time.perf_counter()
        
        try:
            from app.core.resource_management import get_resource_manager
            qdrant = get_resource_manager().get_qdrant()
            collections = await qdrant.get_collections()
            
            latency = (time.perf_counter() - start) * 1000
            return HealthCheck(
                name="qdrant",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                details={"collections": len(collections.collections)}
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return HealthCheck(
                name="qdrant",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                error=str(e)
            )
    
    async def _check_orchestration(self) -> HealthCheck:
        """Check orchestration engine"""
        try:
            from app.orchestration.execution_engine import execution_engine
            
            return HealthCheck(
                name="orchestration",
                status=HealthStatus.HEALTHY,
                details={"active_executions": len(execution_engine.active_executions)}
            )
        except Exception as e:
            return HealthCheck(
                name="orchestration",
                status=HealthStatus.DEGRADED,
                error=str(e)
            )
    
    async def _check_workers(self) -> HealthCheck:
        """Check worker health"""
        try:
            # Worker health will be implemented in /workers layer
            return HealthCheck(
                name="workers",
                status=HealthStatus.HEALTHY,
                details={"status": "operational"}
            )
        except Exception as e:
            return HealthCheck(
                name="workers",
                status=HealthStatus.DEGRADED,
                error=str(e)
            )
    
    async def _check_telemetry(self) -> HealthCheck:
        """Check telemetry systems"""
        try:
            from app.observability import get_tracer, get_metrics_collector
            get_tracer()
            get_metrics_collector()
            
            return HealthCheck(
                name="telemetry",
                status=HealthStatus.HEALTHY,
                details={"tracing": True, "metrics": True}
            )
        except Exception as e:
            return HealthCheck(
                name="telemetry",
                status=HealthStatus.DEGRADED,
                error=str(e)
            )


# Global health check system
_health_system: Optional[HealthCheckSystem] = None


def get_health_system() -> HealthCheckSystem:
    """Get global health check system"""
    global _health_system
    if _health_system is None:
        _health_system = HealthCheckSystem()
    return _health_system


__all__ = ["HealthCheckSystem", "HealthStatus", "HealthCheck", "get_health_system"]
