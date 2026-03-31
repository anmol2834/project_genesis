"""
Enterprise Logging System
Structured JSON logging with request ID support
"""

import logging
import sys
import json
from datetime import datetime
from typing import Optional
import uuid
from contextvars import ContextVar

from shared.config import get_config

# Context variable for request ID
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON
        """
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add request ID if available
        request_id = request_id_var.get()
        if request_id:
            log_data['request_id'] = request_id
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        
        return json.dumps(log_data)


def setup_logging(service_name: str = "mailautomation"):
    """
    Setup logging configuration for a service.
    Configures both the named service logger AND the root logger so that
    all module-level loggers (e.g. ai_engine.*, learning_engine.*) inherit
    the correct level and handler.
    """
    config = get_config()
    log_level = getattr(logging, config.LOG_LEVEL, logging.INFO)

    # ── Formatter ─────────────────────────────────────────────────────────
    if config.ENVIRONMENT == "production":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # ── Named service logger (e.g. "automation-service") ──────────────────
    service_logger = logging.getLogger(service_name)
    service_logger.setLevel(log_level)
    service_logger.handlers.clear()
    service_logger.addHandler(console_handler)
    service_logger.propagate = False

    # ── Root logger — catches all module loggers (ai_engine.*, etc.) ──────
    # IMPORTANT: Uvicorn may have already attached its own handlers to root.
    # We must REPLACE them (not skip) so ai_engine.* logs reach our handler.
    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(console_handler)

    # ── Silence noisy third-party loggers ─────────────────────────────────
    for noisy in ("uvicorn.access", "httpx", "httpcore", "hpack",
                  "huggingface_hub", "filelock", "transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return service_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_request_id(request_id: Optional[str] = None):
    """
    Set request ID for current context
    
    Args:
        request_id: Request ID (auto-generated if not provided)
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    
    request_id_var.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """
    Get request ID from current context
    """
    return request_id_var.get()


def clear_request_id():
    """
    Clear request ID from current context
    """
    request_id_var.set(None)


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter with extra context
    """
    
    def process(self, msg, kwargs):
        """
        Add extra context to log messages
        """
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        
        # Add request ID
        request_id = get_request_id()
        if request_id:
            kwargs['extra']['request_id'] = request_id
        
        return msg, kwargs


def get_logger_with_context(name: str, **context) -> LoggerAdapter:
    """
    Get logger with additional context
    
    Args:
        name: Logger name
        **context: Additional context to include in logs
    
    Returns:
        LoggerAdapter instance
    """
    logger = get_logger(name)
    return LoggerAdapter(logger, context)
