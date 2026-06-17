def get_qdrant_repository():
    from app.core.resource_management import get_resource_manager
    return get_resource_manager().get_qdrant_repository()

def get_qdrant_client():
    from app.core.resource_management import get_resource_manager
    return get_resource_manager().get_qdrant()

__all__ = ['get_qdrant_repository', 'get_qdrant_client']
