"""
Observability - Structured Logs Package
========================================
Structured logging with trace context.
"""
from app.observability.structured_logs.logger import get_logger, StructuredLogger

__all__ = ["get_logger", "StructuredLogger"]
