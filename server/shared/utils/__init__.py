"""Shared utilities module"""

from .http_client import (
    get_http_client,
    close_http_client,
    ServiceClient,
    get_service_client
)
from .security import mask_url_credentials

__all__ = [
    "get_http_client",
    "close_http_client",
    "ServiceClient",
    "get_service_client",
    "mask_url_credentials",
]

