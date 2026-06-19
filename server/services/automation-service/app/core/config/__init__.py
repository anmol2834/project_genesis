"""
Core Configuration Module
==========================
Centralized configuration management for the automation service.
Integrates with shared config while allowing service-specific overrides.

All tuneable values are read from environment variables so that the service
can be configured without code changes across any deployment (dev, staging,
production, any business tenant scale).
"""

import os
from dataclasses import dataclass, field
from typing import Optional
import sys

# Add server root to path for shared imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from shared.config import get_config as get_shared_config


def _env_int(name: str, default: int) -> int:
    """Read an integer from an environment variable, falling back to `default`."""
    try:
        return int(os.getenv(name, str(default)))
    except (ValueError, TypeError):
        return default


def _env_float(name: str, default: float) -> float:
    """Read a float from an environment variable, falling back to `default`."""
    try:
        return float(os.getenv(name, str(default)))
    except (ValueError, TypeError):
        return default


def _env_str(name: str, default: str) -> str:
    """Read a string from an environment variable, falling back to `default`."""
    return os.getenv(name, default)


@dataclass
class AutomationServiceConfig:
    """
    Service-specific configuration.

    Every value is driven by an environment variable so the service can be
    tuned for any business scale without a code change or redeploy.

    Environment variable  →  field name  →  description
    ─────────────────────────────────────────────────────
    AUTOMATION_SERVICE_NAME     → service_name
    AUTOMATION_SERVICE_PORT     → service_port
    AUTOMATION_VERSION          → version
    AUTOMATION_EVENT_STREAM     → event_stream_name
    AUTOMATION_DLQ_STREAM       → dlq_stream_name
    AUTOMATION_CONSUMER_GROUP   → consumer_group_name
    AUTOMATION_WORKER_CONCURRENCY → worker_concurrency (also used by WorkerRuntime)
    AUTOMATION_BATCH_SIZE       → batch_size
    AUTOMATION_MAX_RETRIES      → max_retries
    AUTOMATION_RETRY_BASE_DELAY → retry_base_delay
    AUTOMATION_CONFIDENCE_SEND  → confidence_send_threshold
    AUTOMATION_CONFIDENCE_SKIP  → confidence_skip_threshold
    AUTOMATION_RESPONSE_CACHE_TTL → response_cache_ttl
    AUTOMATION_INTENT_CACHE_TTL → intent_cache_ttl
    AUTOMATION_EMBED_CACHE_TTL  → embed_cache_ttl
    AUTOMATION_RETRIEVAL_TOP_K  → retrieval_top_k
    AUTOMATION_SCORE_THRESHOLD  → retrieval_score_threshold
    AUTOMATION_RERANKER_TOP_N   → reranker_top_n
    AUTOMATION_MAX_CONTEXT_CHARS → max_context_chars
    AUTOMATION_MAX_HISTORY_MSGS → max_history_messages
    AUTOMATION_MAX_CHUNK_CHARS  → max_chunk_chars
    """

    # Service Identity
    service_name: str = field(
        default_factory=lambda: _env_str("AUTOMATION_SERVICE_NAME", "automation-service")
    )
    service_port: int = field(
        default_factory=lambda: _env_int("AUTOMATION_SERVICE_PORT", 8009)
    )
    version: str = field(
        default_factory=lambda: _env_str("AUTOMATION_VERSION", "2.0.0")
    )

    # Event Streams
    event_stream_name: str = field(
        default_factory=lambda: _env_str("AUTOMATION_EVENT_STREAM", "automation_events")
    )
    dlq_stream_name: str = field(
        default_factory=lambda: _env_str("AUTOMATION_DLQ_STREAM", "automation_dlq")
    )
    consumer_group_name: str = field(
        default_factory=lambda: _env_str("AUTOMATION_CONSUMER_GROUP", "automation_group")
    )

    # Worker Configuration
    worker_concurrency: int = field(
        default_factory=lambda: _env_int("AUTOMATION_WORKER_CONCURRENCY", 1)
    )
    batch_size: int = field(
        default_factory=lambda: _env_int("AUTOMATION_BATCH_SIZE", 50)
    )
    max_retries: int = field(
        default_factory=lambda: _env_int("AUTOMATION_MAX_RETRIES", 3)
    )
    retry_base_delay: float = field(
        default_factory=lambda: _env_float("AUTOMATION_RETRY_BASE_DELAY", 1.0)
    )

    # Performance Tuning
    max_slow_path_concurrent: int = field(
        default_factory=lambda: _env_int("AUTOMATION_MAX_SLOW_PATH_CONCURRENT", 32)
    )
    embed_batch_max_size: int = field(
        default_factory=lambda: _env_int("AUTOMATION_EMBED_BATCH_MAX_SIZE", 32)
    )
    embed_batch_timeout_ms: int = field(
        default_factory=lambda: _env_int("AUTOMATION_EMBED_BATCH_TIMEOUT_MS", 50)
    )

    # Confidence Thresholds
    confidence_send_threshold: float = field(
        default_factory=lambda: _env_float("AUTOMATION_CONFIDENCE_SEND", 0.55)
    )
    confidence_skip_threshold: float = field(
        default_factory=lambda: _env_float("AUTOMATION_CONFIDENCE_SKIP", 0.25)
    )

    # Cache TTLs (seconds)
    response_cache_ttl: int = field(
        default_factory=lambda: _env_int("AUTOMATION_RESPONSE_CACHE_TTL", 300)
    )
    intent_cache_ttl: int = field(
        default_factory=lambda: _env_int("AUTOMATION_INTENT_CACHE_TTL", 600)
    )
    embed_cache_ttl: int = field(
        default_factory=lambda: _env_int("AUTOMATION_EMBED_CACHE_TTL", 86400)
    )

    # Retrieval Configuration
    retrieval_top_k: int = field(
        default_factory=lambda: _env_int("AUTOMATION_RETRIEVAL_TOP_K", 8)
    )
    retrieval_score_threshold: float = field(
        default_factory=lambda: _env_float("AUTOMATION_SCORE_THRESHOLD", 0.30)
    )
    reranker_top_n: int = field(
        default_factory=lambda: _env_int("AUTOMATION_RERANKER_TOP_N", 5)
    )

    # Memory Configuration
    max_context_chars: int = field(
        default_factory=lambda: _env_int("AUTOMATION_MAX_CONTEXT_CHARS", 2000)
    )
    max_history_messages: int = field(
        default_factory=lambda: _env_int("AUTOMATION_MAX_HISTORY_MSGS", 6)
    )
    max_chunk_chars: int = field(
        default_factory=lambda: _env_int("AUTOMATION_MAX_CHUNK_CHARS", 400)
    )


class ConfigurationManager:
    """Manages configuration for the automation service"""

    def __init__(self):
        self._shared_config = get_shared_config()
        self._service_config = AutomationServiceConfig()

    @property
    def shared(self):
        """Access shared infrastructure configuration"""
        return self._shared_config

    @property
    def service(self):
        """Access service-specific configuration"""
        return self._service_config

    def get_redis_url(self) -> str:
        return self._shared_config.REDIS_URL

    def get_postgres_url(self) -> str:
        return self._shared_config.DATABASE_URL

    def get_qdrant_url(self) -> str:
        return self._shared_config.QDRANT_URL

    def get_openai_api_key(self) -> str:
        return self._shared_config.OPENAI_API_KEY


# Global configuration instance
_config_manager: Optional[ConfigurationManager] = None


def get_config() -> ConfigurationManager:
    """Get global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


def initialize_config() -> ConfigurationManager:
    """Initialize configuration on service startup"""
    return get_config()
