"""
Core - Dependency Injection
============================
Enterprise DI container with lifecycle management.
"""
import asyncio
from typing import Dict, Any, Optional, Callable, Type, TypeVar, Generic
from enum import Enum
from app.core.exceptions import ConfigurationError
from app.observability import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class ServiceScope(str, Enum):
    """Service lifecycle scope"""
    SINGLETON = "singleton"      # Single instance for lifetime
    SCOPED = "scoped"            # Instance per request/workflow
    TRANSIENT = "transient"      # New instance every time


class ServiceDescriptor:
    """Service registration descriptor"""
    def __init__(
        self,
        service_type: Type,
        factory: Callable,
        scope: ServiceScope = ServiceScope.SINGLETON
    ):
        self.service_type = service_type
        self.factory = factory
        self.scope = scope
        self.instance: Optional[Any] = None
        self.is_async = asyncio.iscoroutinefunction(factory)


class DIContainer:
    """Enterprise dependency injection container"""
    
    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._initialized = False
    
    def register_singleton(
        self,
        service_type: Type[T],
        factory: Callable[[], T]
    ) -> None:
        """Register singleton service"""
        if service_type in self._services:
            logger.warning(f"Service {service_type.__name__} already registered, overwriting")
        
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            scope=ServiceScope.SINGLETON
        )
        logger.debug(f"Registered singleton: {service_type.__name__}")
    
    def register_scoped(
        self,
        service_type: Type[T],
        factory: Callable[[], T]
    ) -> None:
        """Register scoped service"""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            scope=ServiceScope.SCOPED
        )
        logger.debug(f"Registered scoped: {service_type.__name__}")
    
    def register_transient(
        self,
        service_type: Type[T],
        factory: Callable[[], T]
    ) -> None:
        """Register transient service"""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            scope=ServiceScope.TRANSIENT
        )
        logger.debug(f"Registered transient: {service_type.__name__}")
    
    async def resolve(self, service_type: Type[T]) -> T:
        """Resolve service instance"""
        if service_type not in self._services:
            raise ConfigurationError(
                f"Service {service_type.__name__} not registered in DI container"
            )
        
        descriptor = self._services[service_type]
        
        # Return singleton instance if exists
        if descriptor.scope == ServiceScope.SINGLETON and descriptor.instance:
            return descriptor.instance
        
        # Create new instance
        if descriptor.is_async:
            instance = await descriptor.factory()
        else:
            instance = descriptor.factory()
        
        # Cache singleton
        if descriptor.scope == ServiceScope.SINGLETON:
            descriptor.instance = instance
        
        return instance
    
    def resolve_sync(self, service_type: Type[T]) -> T:
        """Synchronous resolve for non-async factories"""
        if service_type not in self._services:
            raise ConfigurationError(
                f"Service {service_type.__name__} not registered"
            )
        
        descriptor = self._services[service_type]
        
        if descriptor.is_async:
            raise ConfigurationError(
                f"Service {service_type.__name__} requires async resolution"
            )
        
        if descriptor.scope == ServiceScope.SINGLETON and descriptor.instance:
            return descriptor.instance
        
        instance = descriptor.factory()
        
        if descriptor.scope == ServiceScope.SINGLETON:
            descriptor.instance = instance
        
        return instance
    
    async def initialize_all(self) -> None:
        """Initialize all singleton services"""
        logger.info("Initializing DI container services")
        
        for service_type, descriptor in self._services.items():
            if descriptor.scope == ServiceScope.SINGLETON and not descriptor.instance:
                try:
                    if descriptor.is_async:
                        descriptor.instance = await descriptor.factory()
                    else:
                        descriptor.instance = descriptor.factory()
                    logger.info(f"Initialized: {service_type.__name__}")
                except Exception as e:
                    logger.error(f"Failed to initialize {service_type.__name__}: {e}")
                    raise
        
        self._initialized = True
        logger.info(f"DI container initialized ({len(self._services)} services)")
    
    async def shutdown_all(self) -> None:
        """Shutdown all services with cleanup"""
        logger.info("Shutting down DI container")
        
        for service_type, descriptor in self._services.items():
            if descriptor.instance and hasattr(descriptor.instance, 'close'):
                try:
                    if asyncio.iscoroutinefunction(descriptor.instance.close):
                        await descriptor.instance.close()
                    else:
                        descriptor.instance.close()
                    logger.debug(f"Closed: {service_type.__name__}")
                except Exception as e:
                    logger.warning(f"Error closing {service_type.__name__}: {e}")
        
        logger.info("DI container shutdown complete")
    
    def get_registered_services(self) -> list[str]:
        """Get list of registered service names"""
        return [s.__name__ for s in self._services.keys()]


# Global container instance
_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """Get global DI container"""
    global _container
    if _container is None:
        _container = DIContainer()
    return _container


def reset_container() -> None:
    """Reset container (testing only)"""
    global _container
    _container = None


__all__ = [
    "DIContainer",
    "ServiceScope",
    "ServiceDescriptor",
    "get_container",
    "reset_container",
]
