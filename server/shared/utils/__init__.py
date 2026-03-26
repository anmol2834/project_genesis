"""Shared utilities module"""

from .http_client import (
    get_http_client,
    close_http_client,
    ServiceClient,
    get_service_client
)

__all__ = [
    "get_http_client",
    "close_http_client",
    "ServiceClient",
    "get_service_client",
]
