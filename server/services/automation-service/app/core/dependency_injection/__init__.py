"""
Core — Dependency Injection (canonical implementation)
=======================================================
This package __init__.py contains the FULL enterprise DI implementation.

Background: Python always resolves `app.core.dependency_injection` to this
package directory (not the sibling dependency_injection.py) when both exist.
The original stub in this file exposed a weaker DIContainer (no ServiceDescriptor,
no async resolve, no ServiceScope as str Enum) which caused silent failures in
app/core/__init__.py and app/core/runtime.py.

Solution: move the canonical implementation here so both import paths resolve
to the same, correct code:
  from app.core.dependency_injection import DIContainer   ← package __init__
  from app.core import DIContainer                        ← re-exported

The sibling dependency_injection.py is now a thin shim that imports from here,
preserving any bytecode-cached or direct-file imports.
"""
import asyncio
from typing import Dict, Any, Optional, Callable, Type, TypeVar

from enum import Enum

T = TypeVar("T")


class ServiceScope(str, Enum):
    """Service lifecycle scope"""
    SINGLETON = "singleton"   # Single instance for the process lifetime
    SCOPED    = "scoped"      # New instance per request / workflow execution
    TRANSIENT = "transient"   # New instance on every resolve call


class ServiceDescriptor:
    """Describes a registered service: its factory, scope, and cached instance."""

    def __init__(
        self,
        service_type: Type,
        factory: Callable,
        scope: ServiceScope = ServiceScope.SINGLETON,
    ):
        self.service_type = service_type
        self.factory      = factory
        self.scope        = scope
        self.instance: Optional[Any] = None
        self.is_async     = asyncio.iscoroutinefunction(factory)


class DIContainer:
    """
    Enterprise dependency injection container.

    Supports singleton, scoped, and transient lifecycles.
    Async factories are fully supported via `resolve()`.
    Sync factories are supported via `resolve_sync()`.
    """

    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._initialized = False

    # ── Registration ──────────────────────────────────────────────────────

    def register_singleton(
        self,
        service_type: Type[T],
        factory: Callable[[], T],
    ) -> None:
        """Register a service with SINGLETON scope."""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            scope=ServiceScope.SINGLETON,
        )

    def register_scoped(
        self,
        service_type: Type[T],
        factory: Callable[[], T],
    ) -> None:
        """Register a service with SCOPED scope."""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            scope=ServiceScope.SCOPED,
        )

    def register_transient(
        self,
        service_type: Type[T],
        factory: Callable[[], T],
    ) -> None:
        """Register a service with TRANSIENT scope."""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            scope=ServiceScope.TRANSIENT,
        )

    # Backward-compat alias used by the old stub API
    def register(
        self,
        name: str,
        instance: Any,
        scope: str = "singleton",
    ) -> None:
        """
        Backward-compatible register(name, instance) from the old stub.
        Stores by a sentinel class keyed on the name string.
        """
        # Create a dynamic type key so string-named services can coexist
        key = type(f"_Named_{name}", (), {})
        desc = ServiceDescriptor(
            service_type=key,
            factory=lambda: instance,
            scope=ServiceScope.SINGLETON,
        )
        desc.instance = instance
        self._services[key] = desc

    # ── Resolution ────────────────────────────────────────────────────────

    async def resolve(self, service_type: Type[T]) -> T:
        """Resolve a registered service (supports async factories)."""
        if service_type not in self._services:
            raise RuntimeError(
                f"Service {getattr(service_type, '__name__', service_type)} "
                "not registered in DI container"
            )

        descriptor = self._services[service_type]

        if descriptor.scope == ServiceScope.SINGLETON and descriptor.instance is not None:
            return descriptor.instance

        instance = (
            await descriptor.factory()
            if descriptor.is_async
            else descriptor.factory()
        )

        if descriptor.scope == ServiceScope.SINGLETON:
            descriptor.instance = instance

        return instance

    def resolve_sync(self, service_type: Type[T]) -> T:
        """Resolve a registered service synchronously (async factories raise)."""
        if service_type not in self._services:
            raise RuntimeError(
                f"Service {getattr(service_type, '__name__', service_type)} "
                "not registered in DI container"
            )

        descriptor = self._services[service_type]

        if descriptor.is_async:
            raise RuntimeError(
                f"Service {getattr(service_type, '__name__', service_type)} "
                "requires async resolution — use await container.resolve()"
            )

        if descriptor.scope == ServiceScope.SINGLETON and descriptor.instance is not None:
            return descriptor.instance

        instance = descriptor.factory()

        if descriptor.scope == ServiceScope.SINGLETON:
            descriptor.instance = instance

        return instance

    # Backward-compat alias from old stub
    def get(self, name: str) -> Optional[Any]:
        """Backward-compat: get a string-named service registered via register()."""
        key_name = f"_Named_{name}"
        for stype, desc in self._services.items():
            if getattr(stype, "__name__", "") == key_name:
                return desc.instance
        return None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def initialize_all(self) -> None:
        """Pre-initialize all singleton services."""
        for service_type, descriptor in self._services.items():
            if descriptor.scope == ServiceScope.SINGLETON and descriptor.instance is None:
                descriptor.instance = (
                    await descriptor.factory()
                    if descriptor.is_async
                    else descriptor.factory()
                )
        self._initialized = True

    async def shutdown_all(self) -> None:
        """Shutdown all services that expose a close() method."""
        for descriptor in self._services.values():
            if descriptor.instance and hasattr(descriptor.instance, "close"):
                try:
                    if asyncio.iscoroutinefunction(descriptor.instance.close):
                        await descriptor.instance.close()
                    else:
                        descriptor.instance.close()
                except Exception:
                    pass

    def get_registered_services(self) -> list:
        """Return names of all registered service types."""
        return [
            getattr(s, "__name__", str(s))
            for s in self._services
        ]


# Backward-compat alias from old stub
ServiceContainer = DIContainer


# ── Global singleton ──────────────────────────────────────────────────────────

_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """Return the global DI container, creating it on first call."""
    global _container
    if _container is None:
        _container = DIContainer()
    return _container


def reset_container() -> None:
    """Reset the global container. Intended for use in tests only."""
    global _container
    _container = None


__all__ = [
    "DIContainer",
    "ServiceContainer",
    "ServiceDescriptor",
    "ServiceScope",
    "get_container",
    "reset_container",
]
