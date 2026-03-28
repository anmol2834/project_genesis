"""
Celery Worker for User Service
Handles background tasks like embedding updates
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.celery import get_celery_app
from shared.logger import setup_logging

logger = setup_logging("user-celery-worker")

celery_app = get_celery_app()

# Import tasks to register them
from tasks import embedding_tasks

print("\n" + "="*60)
print("  USER SERVICE - CELERY WORKER")
print("="*60)
print(f"  Queue: user_queue")
print(f"  Task: user.update_user_embedding")
print(f"  Purpose: Partial embedding updates (AI fields only)")
print("="*60 + "\n")

logger.info("User service Celery worker initialized")
logger.info(f"Listening to queue: user_queue")
logger.info(f"Registered tasks: {list(celery_app.tasks.keys())}")

if __name__ == '__main__':
    celery_app.start()
