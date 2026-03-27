"""
Celery Worker for Auth Service
Handles background tasks like embedding generation
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.celery import get_celery_app
from shared.logger import setup_logging

# Setup logging
logger = setup_logging("auth-celery-worker")

# Get Celery app
celery_app = get_celery_app()

# Import tasks to register them
from tasks import embedding_tasks

logger.info("Auth service Celery worker initialized")
logger.info(f"Registered tasks: {list(celery_app.tasks.keys())}")

if __name__ == '__main__':
    celery_app.start()
