"""
Observability - Structured Logging System
==========================================
Enterprise structured logging with trace context.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.observability import StructuredLog
from app.models.enums import LogLevel

class StructuredLogger:
    """Structured logging with trace context"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
    
    def _create_log(
        self,
        level: LogLevel,
        message: str,
        user_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> StructuredLog:
        """Create structured log entry"""
        return StructuredLog(
            level=level,
            message=message,
            user_id=user_id or "system",
            trace_id=trace_id or "",
            correlation_id=correlation_id,
            logger_name=self.name,
            timestamp=datetime.utcnow(),
            extra=extra or {}
        )
    
    def _safe_extra(self, log) -> Dict[str, Any]:
        """
        Build the extra dict for logging, excluding keys that would conflict
        with LogRecord's reserved attributes (e.g. 'message').
        """
        _RESERVED = {"message", "args", "levelname", "levelno", "pathname",
                     "filename", "module", "exc_info", "exc_text", "stack_info",
                     "lineno", "funcName", "created", "msecs", "relativeCreated",
                     "thread", "threadName", "processName", "process", "name"}
        return {k: v for k, v in log.model_dump().items() if k not in _RESERVED}

    def debug(
        self,
        message: str,
        *args,
        user_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        **kwargs
    ):
        """Debug level log"""
        # If positional args provided, format them into the message
        if args:
            try: message = message % args
            except Exception: message = f"{message} {args}"
        log = self._create_log(LogLevel.DEBUG, message, user_id, trace_id, extra=kwargs)
        self.logger.debug(message, extra=self._safe_extra(log))

    def info(
        self,
        message: str,
        *args,
        user_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        **kwargs
    ):
        """Info level log"""
        if args:
            try: message = message % args
            except Exception: message = f"{message} {args}"
        log = self._create_log(LogLevel.INFO, message, user_id, trace_id, extra=kwargs)
        self.logger.info(message, extra=self._safe_extra(log))

    def warning(
        self,
        message: str,
        *args,
        user_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        **kwargs
    ):
        """Warning level log"""
        if args:
            try: message = message % args
            except Exception: message = f"{message} {args}"
        log = self._create_log(LogLevel.WARNING, message, user_id, trace_id, extra=kwargs)
        self.logger.warning(message, extra=self._safe_extra(log))

    def error(
        self,
        message: str,
        *args,
        user_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        error: Optional[Exception] = None,
        exc_info: bool = False,
        **kwargs
    ):
        """Error level log"""
        if args:
            try: message = message % args
            except Exception: message = f"{message} {args}"
        if error:
            kwargs["error_type"] = type(error).__name__
            kwargs["error_message"] = str(error)
        log = self._create_log(LogLevel.ERROR, message, user_id, trace_id, extra=kwargs)
        self.logger.error(message, extra=self._safe_extra(log), exc_info=error or exc_info)

def get_logger(name: str) -> StructuredLogger:
    """Get structured logger instance"""
    return StructuredLogger(name)

__all__ = ["StructuredLogger", "get_logger"]
