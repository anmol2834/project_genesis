"""
Integrations - Base Contracts
==============================
Base classes and contracts for all external integrations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Generic, TypeVar
from enum import Enum
from app.core.exceptions import RetryableException, NonRetryableException

T = TypeVar('T')


class ProviderStatus(str, Enum):
    """Provider health status"""
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class IntegrationException(Exception):
    """Base exception for integration errors"""
    def __init__(self, message: str, provider: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.details = details or {}


class ProviderUnavailableError(IntegrationException, RetryableException):
    """Provider is temporarily unavailable"""
    pass


class ProviderTimeoutError(IntegrationException, RetryableException):
    """Provider request timeout"""
    pass


class ProviderRateLimitError(IntegrationException, RetryableException):
    """Provider rate limit exceeded"""
    pass


class ProviderAuthenticationError(IntegrationException, NonRetryableException):
    """Provider authentication failed"""
    pass


class ProviderValidationError(IntegrationException, NonRetryableException):
    """Provider input validation failed"""
    pass


class BaseProvider(ABC, Generic[T]):
    """
    Base class for all external providers.
    Provides common functionality for retry, telemetry, and error handling.
    """
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self._status = ProviderStatus.UNKNOWN
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize provider connection"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider health"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close provider connection"""
        pass
    
    def get_status(self) -> ProviderStatus:
        """Get current provider status"""
        return self._status
    
    def set_status(self, status: ProviderStatus) -> None:
        """Update provider status"""
        self._status = status


class BaseAPIClient(BaseProvider[T]):
    """Base class for HTTP API clients"""
    
    def __init__(self, provider_name: str, base_url: str, timeout: int = 30):
        super().__init__(provider_name)
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[Any] = None
    
    async def initialize(self) -> None:
        """Initialize HTTP client"""
        import httpx
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True
        )
    
    async def close(self) -> None:
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None


class BaseVectorDBClient(BaseProvider[T]):
    """Base class for vector database clients"""
    
    def __init__(self, provider_name: str):
        super().__init__(provider_name)
    
    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int,
        filter: Optional[Dict[str, Any]] = None
    ) -> list[Dict[str, Any]]:
        """Search vector database"""
        pass
    
    @abstractmethod
    async def upsert(
        self,
        collection: str,
        points: list[Dict[str, Any]]
    ) -> None:
        """Insert or update vectors"""
        pass


class BaseLLMProvider(BaseProvider[T]):
    """Base class for LLM providers"""
    
    def __init__(self, provider_name: str, model: str):
        super().__init__(provider_name)
        self.model = model
    
    @abstractmethod
    async def generate(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate LLM completion"""
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """Generate streaming LLM completion"""
        pass


class BaseEmbeddingProvider(BaseProvider[T]):
    """Base class for embedding providers"""
    
    def __init__(self, provider_name: str, model: str):
        super().__init__(provider_name)
        self.model = model
    
    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        batch_size: int = 100
    ) -> list[list[float]]:
        """Generate embeddings for texts"""
        pass


class BaseRerankerProvider(BaseProvider[T]):
    """Base class for reranker providers"""
    
    def __init__(self, provider_name: str, model: str):
        super().__init__(provider_name)
        self.model = model
    
    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10
    ) -> list[Dict[str, Any]]:
        """Rerank documents by relevance"""
        pass


__all__ = [
    "ProviderStatus",
    "IntegrationException",
    "ProviderUnavailableError",
    "ProviderTimeoutError",
    "ProviderRateLimitError",
    "ProviderAuthenticationError",
    "ProviderValidationError",
    "BaseProvider",
    "BaseAPIClient",
    "BaseVectorDBClient",
    "BaseLLMProvider",
    "BaseEmbeddingProvider",
    "BaseRerankerProvider",
]
