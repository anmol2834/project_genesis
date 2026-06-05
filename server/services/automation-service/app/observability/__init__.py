"""
Observability Package
=====================
Enterprise observability system for automation-service.
"""
from app.observability.tracing.tracer import get_tracer, tracer
from app.observability.structured_logs.logger import get_logger
from app.observability.metrics.collector import get_metrics_collector, metrics_collector
from app.observability.performance.monitor import get_performance_monitor, performance_monitor

__all__ = [
    "get_tracer",
    "tracer",
    "get_logger",
    "get_metrics_collector",
    "metrics_collector",
    "get_performance_monitor",
    "performance_monitor",
]
