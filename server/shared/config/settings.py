"""
Global Configuration Module
Single source of truth for all microservices configuration
Uses Pydantic Settings for type-safe configuration management
"""

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional
import os


class GlobalConfig(BaseSettings):
    """
    Global configuration class that loads from .env file
    All services MUST use this configuration
    """
    
    # ── Database Configuration ──────────────────────────────────────────────
    DATABASE_URL: str = Field(..., description="PostgreSQL connection URL")
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="password")
    POSTGRES_DB: str = Field(default="mailautomation")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    
    # ── MongoDB Configuration ───────────────────────────────────────────────
    MONGODB_URL: str = Field(..., description="MongoDB connection URL")
    MONGODB_DB: str = Field(default="mailautomation")
    
    # ── Redis Configuration ─────────────────────────────────────────────────
    REDIS_URL: str = Field(..., description="Redis connection URL")
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: Optional[str] = Field(default=None)
    
    # ── Service URLs ────────────────────────────────────────────────────────
    GATEWAY_SERVICE_URL: str = Field(default="http://gateway-service:8000")
    AUTH_SERVICE_URL: str = Field(default="http://auth-service:8000")
    USER_SERVICE_URL: str = Field(default="http://user-service:8000")
    BUSINESS_SERVICE_URL: str = Field(default="http://business-service:8000")
    EMAIL_SERVICE_URL: str = Field(default="http://email-service:8000")
    INBOX_SERVICE_URL: str = Field(default="http://inbox-service:8000")
    CAMPAIGN_SERVICE_URL: str = Field(default="http://campaign-service:8000")
    LEADS_SERVICE_URL: str = Field(default="http://leads-service:8000")
    ANALYTICS_SERVICE_URL: str = Field(default="http://analytics-service:8000")
    AUTOMATION_SERVICE_URL: str = Field(default="http://automation-service:8000")
    RESEARCH_SERVICE_URL: str = Field(default="http://research-service:8000")
    NOTIFICATION_SERVICE_URL: str = Field(default="http://notification-service:8000")
    
    # ── JWT Configuration ───────────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(..., description="JWT secret key")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=43200)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=60)
    
    # ── Encryption Configuration ────────────────────────────────────────────
    ENCRYPTION_KEY: str = Field(..., description="Encryption key for sensitive data")
    
    # ── OAuth Configuration ─────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: Optional[str] = Field(default=None)
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(default=None)
    MICROSOFT_CLIENT_ID: Optional[str] = Field(default=None)
    MICROSOFT_CLIENT_SECRET: Optional[str] = Field(default=None)
    MICROSOFT_TENANT_ID: Optional[str] = Field(default=None)
    MICROSOFT_REDIRECT_URI: Optional[str] = Field(default=None)

    # Email-service specific OAuth (separate credentials for email connection flow)
    GOOGLE_CLIENT_ID_EMAIL: Optional[str] = Field(default=None)
    GOOGLE_CLIENT_SECRET_EMAIL: Optional[str] = Field(default=None)
    GOOGLE_REDIRECT_URI_EMAIL: str = Field(default="http://localhost:3000/oauth/callback")
    
    MICROSOFT_CLIENT_ID_EMAIL: Optional[str] = Field(default=None)
    MICROSOFT_CLIENT_SECRET_EMAIL: Optional[str] = Field(default=None)
    MICROSOFT_TENANT_ID_EMAIL: Optional[str] = Field(default=None)
    MICROSOFT_REDIRECT_URI_EMAIL: str = Field(default="http://localhost:3000/oauth/callback")

    # ── Gmail Pub/Sub Configuration ─────────────────────────────────────────
    GMAIL_PUBSUB_TOPIC: str = Field(
        default="projects/gmail-integration-484614/topics/gmail-notifications",
        description="Google Cloud Pub/Sub topic for Gmail push notifications"
    )
    GMAIL_PUBSUB_SUBSCRIPTION: str = Field(
        default="projects/gmail-integration-484614/subscriptions/gmail-notifications-sub",
        description="Google Cloud Pub/Sub subscription name"
    )

    # ── Public webhook URL (for Outlook Graph subscriptions) ─────────────────
    # In dev: set to your ngrok URL e.g. https://abc123.ngrok-free.app
    # In prod: set to your real domain e.g. https://api.yourdomain.com
    EMAIL_SERVICE_PUBLIC_URL: str = Field(
        default="http://localhost:8004",
        description="Publicly reachable URL for this service (used for webhook registration)"
    )
    
    # ── Celery Configuration ────────────────────────────────────────────────
    CELERY_BROKER_URL: str = Field(..., description="Celery broker URL (Redis)")
    CELERY_RESULT_BACKEND: str = Field(..., description="Celery result backend URL")
    CELERY_TASK_SERIALIZER: str = Field(default="json")
    CELERY_RESULT_SERIALIZER: str = Field(default="json")
    CELERY_ACCEPT_CONTENT: List[str] = Field(default=["json"])
    CELERY_TIMEZONE: str = Field(default="UTC")
    CELERY_ENABLE_UTC: bool = Field(default=True)
    
    # ── Application Configuration ──────────────────────────────────────────
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO")
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"])
    
    # ── Performance Configuration ───────────────────────────────────────────
    DB_POOL_SIZE: int = Field(default=20)
    DB_MAX_OVERFLOW: int = Field(default=10)
    DB_POOL_TIMEOUT: int = Field(default=30)
    REDIS_MAX_CONNECTIONS: int = Field(default=50)
    WORKER_CONCURRENCY: int = Field(default=4)
    
    # ── Rate Limiting ───────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    RATE_LIMIT_BURST: int = Field(default=10)
    
    # ── Qdrant Vector Database Configuration ──────────────────────────────────
    QDRANT_URL: str = Field(default="http://qdrant:6333")
    QDRANT_GRPC_URL: str = Field(default="http://qdrant:6334")
    QDRANT_COLLECTION: str = Field(default="business_context")
    QDRANT_VECTOR_SIZE: int = Field(default=384)
    QDRANT_DISTANCE_METRIC: str = Field(default="Cosine")

    # ── LLM Configuration ──────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key — set in .env")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")
    OPENAI_TIMEOUT_SECONDS: int = Field(default=30)
    OPENAI_MAX_RETRIES: int = Field(default=2)
    
    # ── Health Check Configuration ──────────────────────────────────────────
    HEALTH_CHECK_INTERVAL: int = Field(default=30)
    HEALTH_CHECK_TIMEOUT: int = Field(default=5)
    
    @validator("DATABASE_URL", pre=True)
    def convert_database_url(cls, v):
        """Convert postgresql:// to postgresql+asyncpg://"""
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v
    
    @validator("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", pre=True)
    def convert_redis_url(cls, v):
        """Ensure Redis URL is properly formatted"""
        if isinstance(v, str) and v.startswith("redis://localhost"):
            # Use the main Redis URL if localhost is specified
            return v
        return v
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from JSON array string or comma-separated string."""
        if isinstance(v, str):
            v = v.strip()
            # Handle JSON array format: ["http://localhost:3000","http://localhost:3001"]
            if v.startswith("["):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # Handle comma-separated format
            return [origin.strip().strip('"').strip("'") for origin in v.split(",") if origin.strip()]
        return v

    @validator("CELERY_ACCEPT_CONTENT", pre=True)
    def parse_celery_accept_content(cls, v):
        """Parse CELERY_ACCEPT_CONTENT from JSON array string."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [item.strip().strip('"') for item in v.split(",") if item.strip()]
        return v
    
    class Config:
        # Find .env file in server root directory (2 levels up from shared/config)
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global configuration instance
config = GlobalConfig()


def get_config() -> GlobalConfig:
    """
    Get global configuration instance
    Use this function in all services to access configuration
    """
    return config
