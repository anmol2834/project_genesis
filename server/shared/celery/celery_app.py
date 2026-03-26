"""
Celery Application Setup
Uses Redis as broker and result backend
NO TASKS - Only infrastructure setup
"""

from celery import Celery
from celery.schedules import crontab
import logging

from shared.config import get_config

logger = logging.getLogger(__name__)

# Global Celery app instance
_celery_app = None


def get_celery_app() -> Celery:
    """
    Get or create Celery application
    """
    global _celery_app
    
    if _celery_app is None:
        config = get_config()
        
        _celery_app = Celery(
            "mailautomation",
            broker=config.CELERY_BROKER_URL,
            backend=config.CELERY_RESULT_BACKEND,
        )
        
        # Configure Celery
        _celery_app.conf.update(
            task_serializer=config.CELERY_TASK_SERIALIZER,
            result_serializer=config.CELERY_RESULT_SERIALIZER,
            accept_content=config.CELERY_ACCEPT_CONTENT,
            timezone=config.CELERY_TIMEZONE,
            enable_utc=config.CELERY_ENABLE_UTC,
            
            # Worker configuration
            worker_prefetch_multiplier=1,
            worker_max_tasks_per_child=1000,
            worker_disable_rate_limits=False,
            
            # Task configuration
            task_acks_late=True,
            task_reject_on_worker_lost=True,
            task_time_limit=300,  # 5 minutes
            task_soft_time_limit=240,  # 4 minutes
            
            # Result backend configuration
            result_expires=3600,  # 1 hour
            result_persistent=True,
            
            # Broker configuration
            broker_connection_retry_on_startup=True,
            broker_connection_max_retries=10,
        )
        
        logger.info("Celery application created")
    
    return _celery_app


def init_celery():
    """
    Initialize Celery application
    Call this on application startup
    """
    try:
        app = get_celery_app()
        
        # Test broker connection
        app.connection().ensure_connection(max_retries=3)
        
        logger.info("Celery initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Celery initialization failed: {e}")
        return False


def check_celery_health() -> bool:
    """
    Check Celery broker connection health
    """
    try:
        app = get_celery_app()
        app.connection().ensure_connection(max_retries=1)
        return True
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        return False


# Beat schedule configuration (for periodic tasks)
# NO TASKS DEFINED - Only schedule structure
def get_beat_schedule():
    """
    Get Celery Beat schedule configuration
    Tasks will be added by individual services
    """
    return {
        # Example structure (no actual tasks):
        # 'task-name': {
        #     'task': 'module.task_function',
        #     'schedule': crontab(minute='*/5'),
        # },
    }


def configure_beat_schedule():
    """
    Configure Celery Beat schedule
    """
    app = get_celery_app()
    app.conf.beat_schedule = get_beat_schedule()
    logger.info("Celery Beat schedule configured")
