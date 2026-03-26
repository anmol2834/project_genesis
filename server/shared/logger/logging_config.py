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
    Setup logging configuration for a service
    
    Args:
        service_name: Name of the service (for logger identification)
    """
    config = get_config()
    
    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # Set formatter based on environment
    if config.ENVIRONMENT == "production":
        # JSON formatter for production
        formatter = JSONFormatter()
    else:
        # Human-readable formatter for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


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
