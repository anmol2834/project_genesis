"""
Celery Worker Configuration
Worker setup and configuration
"""

from celery import Celery
from celery.signals import worker_ready, worker_shutdown
import logging

from shared.config import get_config

logger = logging.getLogger(__name__)


class CeleryWorkerConfig:
    """
    Celery worker configuration class
    """
    
    def __init__(self):
        self.config = get_config()
    
    def get_worker_config(self) -> dict:
        """
        Get worker configuration
        """
        return {
            'concurrency': self.config.WORKER_CONCURRENCY,
            'prefetch_multiplier': 1,
            'max_tasks_per_child': 1000,
            'task_acks_late': True,
            'worker_log_format': '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
            'worker_task_log_format': '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
        }
    
    def get_beat_config(self) -> dict:
        """
        Get beat scheduler configuration
        """
        return {
            'scheduler': 'celery.beat:PersistentScheduler',
            'schedule_filename': '/tmp/celerybeat-schedule',
        }


@worker_ready.connect
def on_worker_ready(**kwargs):
    """
    Called when worker is ready
    """
    logger.info("Celery worker is ready")


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    """
    Called when worker is shutting down
    """
    logger.info("Celery worker is shutting down")


def start_worker(app: Celery, worker_name: str = "worker"):
    """
    Start Celery worker
    
    Usage:
        from shared.celery import get_celery_app, start_worker
        app = get_celery_app()
        start_worker(app, "email-worker")
    """
    config = CeleryWorkerConfig()
    worker_config = config.get_worker_config()
    
    logger.info(f"Starting Celery worker: {worker_name}")
    
    app.worker_main([
        'worker',
        f'--hostname={worker_name}@%h',
        f'--concurrency={worker_config["concurrency"]}',
        '--loglevel=INFO',
    ])


def start_beat(app: Celery):
    """
    Start Celery Beat scheduler
    
    Usage:
        from shared.celery import get_celery_app, start_beat
        app = get_celery_app()
        start_beat(app)
    """
    config = CeleryWorkerConfig()
    beat_config = config.get_beat_config()
    
    logger.info("Starting Celery Beat scheduler")
    
    app.Beat(
        loglevel='INFO',
        scheduler=beat_config['scheduler'],
    ).run()
