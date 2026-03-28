"""User service Celery tasks"""

from .embedding_tasks import update_user_embedding

__all__ = ["update_user_embedding"]
