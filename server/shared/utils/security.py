"""
Security Utilities
==================
Shared utilities for credential redaction and secret sanitization across services.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit, urlunsplit


def mask_url_credentials(url: str | None) -> str:
    """
    Safely redacts credentials (username, password, auth tokens) from connection URLs.
    
    Examples:
        rediss://default:supersecret@my-host.upstash.io:6379/0
        -> rediss://default:***@my-host.upstash.io:6379/0

        postgresql+asyncpg://user:pass@ep-cool.region.neon.tech/neondb
        -> postgresql+asyncpg://user:***@ep-cool.region.neon.tech/neondb
    """
    if not url:
        return ""
    try:
        url_str = str(url).strip()
        parts = urlsplit(url_str)
        if parts.password or parts.username:
            user_part = parts.username or ""
            pwd_part = ":***" if parts.password else ""
            netloc = f"{user_part}{pwd_part}@{parts.hostname or ''}"
            if parts.port:
                netloc += f":{parts.port}"
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
        return url_str
    except Exception:
        # Fallback regex if urlsplit fails on custom schemas
        try:
            return re.sub(r"://([^:@]+):([^@]+)@", r"://\1:***@", str(url))
        except Exception:
            return "<masked_connection_url>"
