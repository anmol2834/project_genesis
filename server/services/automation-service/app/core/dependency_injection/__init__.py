"""
Dependency Injection Container
"""

class ServiceScope:
    """Service scope for DI"""
    SINGLETON = "singleton"
    TRANSIENT = "transient"

class DIContainer:
    """Dependency injection container"""
    
    def __init__(self):
        self._services = {}
    
    def register(self, name: str, instance, scope: str = ServiceScope.SINGLETON):
        self._services[name] = {"instance": instance, "scope": scope}
    
    def get(self, name: str):
        return self._services.get(name, {}).get("instance")
    
    def resolve(self, name: str):
        return self.get(name)

class ServiceContainer(DIContainer):
    """Alias for backward compatibility"""
    pass

_container = DIContainer()

def get_container() -> DIContainer:
    return _container

def reset_container():
    global _container
    _container = DIContainer()

__all__ = ["DIContainer", "ServiceContainer", "ServiceScope", "get_container", "reset_container"]
