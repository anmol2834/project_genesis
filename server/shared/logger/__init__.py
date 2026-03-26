"""Shared logger module"""

from .logging_config import (
    setup_logging,
    get_logger,
    set_request_id,
    get_request_id,
    clear_request_id,
    get_logger_with_context,
    JSONFormatter,
    LoggerAdapter
)

__all__ = [
    "setup_logging",
    "get_logger",
    "set_request_id",
    "get_request_id",
    "clear_request_id",
    "get_logger_with_context",
    "JSONFormatter",
    "LoggerAdapter",
]
