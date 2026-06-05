"""
Core Configuration Module
==========================
Centralized configuration management for the automation service.
Integrates with shared config while allowing service-specific overrides.
"""

from dataclasses import dataclass
from typing import Optional
import sys
import os

# Add server root to path for shared imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from shared.config import get_config as get_shared_config


@dataclass
class AutomationServiceConfig:
    """Service-specific configuration"""
    
    # Service Identity
    service_name: str = "automation-service"
    service_port: int = 8009
    version: str = "2.0.0"
    
    # Event Streams
    event_stream_name: str = "automation_events"
    dlq_stream_name: str = "automation_dlq"
    consumer_group_name: str = "automation_group"
    
    # Worker Configuration
    worker_concurrency: int = 16
    batch_size: int = 50
    max_retries: int = 3
    retry_base_delay: float = 1.0
    
    # Performance Tuning
    max_slow_path_concurrent: int = 32
    embed_batch_max_size: int = 32
    embed_batch_timeout_ms: int = 50
    
    # Confidence Thresholds
    confidence_send_threshold: float = 0.55
    confidence_skip_threshold: float = 0.25
    
    # Cache TTLs
    response_cache_ttl: int = 300
    intent_cache_ttl: int = 600
    embed_cache_ttl: int = 86400
    
    # Retrieval Configuration
    retrieval_top_k: int = 8
    retrieval_score_threshold: float = 0.30
    reranker_top_n: int = 5
    
    # Memory Configuration
    max_context_chars: int = 2000
    max_history_messages: int = 6
    max_chunk_chars: int = 400
    

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
        """Get Redis connection URL"""
        return self._shared_config.REDIS_URL
    
    def get_postgres_url(self) -> str:
        """Get PostgreSQL connection URL"""
        return self._shared_config.DATABASE_URL
    
    def get_qdrant_url(self) -> str:
        """Get Qdrant connection URL"""
        return self._shared_config.QDRANT_URL
    
    def get_openai_api_key(self) -> str:
        """Get OpenAI API key"""
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
