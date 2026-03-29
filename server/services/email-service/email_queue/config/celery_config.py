"""
Celery Configuration for Email Service Queue System
Enterprise-grade queue configuration with retry, DLQ, and monitoring.
"""

from celery import Celery
from kombu import Exchange, Queue
import logging

from shared.config import get_config

logger = logging.getLogger(__name__)

# Queue names
EMAIL_EVENTS_QUEUE = "email_events_queue"
EMAIL_RETRY_QUEUE = "email_retry_queue"
EMAIL_DLQ = "email_dlq"

# Exchange names
EMAIL_EXCHANGE = "email_exchange"
EMAIL_RETRY_EXCHANGE = "email_retry_exchange"
EMAIL_DLQ_EXCHANGE = "email_dlq_exchange"


def create_email_celery_app() -> Celery:
    """
    Create Celery app specifically for email service queues.
    """
    config = get_config()
    
    app = Celery(
        "email_service",
        broker=config.CELERY_BROKER_URL,
        backend=config.CELERY_RESULT_BACKEND,
        # Tell Celery exactly which modules contain tasks.
        # Without this the worker starts with an empty [tasks] list
        # and rejects every incoming message as "unregistered".
        include=[
            "email_queue.tasks.email_tasks",
            "email_queue.tasks.scheduled_tasks",
        ],
    )
    
    # Define exchanges
    email_exchange = Exchange(
        EMAIL_EXCHANGE,
        type="direct",
        durable=True
    )
    
    retry_exchange = Exchange(
        EMAIL_RETRY_EXCHANGE,
        type="direct",
        durable=True
    )
    
    dlq_exchange = Exchange(
        EMAIL_DLQ_EXCHANGE,
        type="direct",
        durable=True
    )
    
    # Define queues
    app.conf.task_queues = (
        # Main email events queue
        Queue(
            EMAIL_EVENTS_QUEUE,
            exchange=email_exchange,
            routing_key="email.event",
            queue_arguments={
                "x-max-priority": 10,  # Priority support
                "x-message-ttl": 86400000,  # 24 hours TTL
            }
        ),
        
        # Retry queue
        Queue(
            EMAIL_RETRY_QUEUE,
            exchange=retry_exchange,
            routing_key="email.retry",
            queue_arguments={
                "x-message-ttl": 3600000,  # 1 hour TTL
            }
        ),
        
        # Dead Letter Queue
        Queue(
            EMAIL_DLQ,
            exchange=dlq_exchange,
            routing_key="email.dlq",
            queue_arguments={
                "x-message-ttl": 604800000,  # 7 days TTL
            }
        ),
    )
    
    # Task routing
    app.conf.task_routes = {
        "email_queue.tasks.email_tasks.process_email_event": {
            "queue": EMAIL_EVENTS_QUEUE,
            "routing_key": "email.event"
        },
        "email_queue.tasks.email_tasks.retry_email_event": {
            "queue": EMAIL_RETRY_QUEUE,
            "routing_key": "email.retry"
        },
        "email_queue.tasks.email_tasks.handle_dlq_event": {
            "queue": EMAIL_DLQ,
            "routing_key": "email.dlq"
        },
    }
    
    # Celery configuration
    app.conf.update(
        # Serialization
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        
        # Timezone
        timezone="UTC",
        enable_utc=True,
        
        # Task execution
        task_acks_late=True,  # Acknowledge after task completion
        task_reject_on_worker_lost=True,  # Reject if worker dies
        task_time_limit=300,  # 5 minutes hard limit
        task_soft_time_limit=240,  # 4 minutes soft limit
        
        # Retry configuration
        task_autoretry_for=(Exception,),
        task_retry_kwargs={
            "max_retries": 3,
            "countdown": 10  # Initial retry delay
        },
        task_retry_backoff=True,  # Exponential backoff
        task_retry_backoff_max=600,  # Max 10 minutes
        task_retry_jitter=True,  # Add jitter to prevent thundering herd
        
        # Worker configuration
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        worker_disable_rate_limits=True,
        
        # Result backend
        result_expires=3600,
        result_persistent=False,
        task_ignore_result=True,   # don't store results — saves Redis connections

        # Broker — tight pool for free-tier Redis
        broker_connection_retry_on_startup=True,
        broker_connection_max_retries=10,
        broker_pool_limit=2,
        broker_transport_options={
            "visibility_timeout": 3600,
            "max_connections": 3,
            "socket_keepalive": True,
            "socket_timeout": 30,
        },

        # Result backend — minimal
        result_backend_transport_options={
            "retry_on_timeout": True,
            "max_connections": 2,
        },
        
        # Task default queue
        task_default_queue=EMAIL_EVENTS_QUEUE,
        task_default_exchange=EMAIL_EXCHANGE,
        task_default_routing_key="email.event",

        # ── Celery Beat schedule ──────────────────────────────────────────────
        # These periodic tasks keep the system healthy and guarantee no data loss.
        beat_schedule={
            # Renew Gmail/Outlook subscriptions every hour
            "subscription-refresh": {
                "task":     "email_queue.tasks.scheduled_tasks.subscription_refresh_task",
                "schedule": 3600,  # every 1 hour
                "options":  {"queue": EMAIL_EVENTS_QUEUE},
            },
            # Recover missed emails via Gmail History API every 30 minutes
            "history-sync": {
                "task":     "email_queue.tasks.scheduled_tasks.history_sync_task",
                "schedule": 1800,  # every 30 minutes
                "options":  {"queue": EMAIL_EVENTS_QUEUE},
            },
            # Clean up unknown Gmail watches every 24 hours
            "watch-cleanup": {
                "task":     "email_queue.tasks.scheduled_tasks.cleanup_task",
                "schedule": 86400,  # every 24 hours
                "options":  {"queue": EMAIL_EVENTS_QUEUE},
            },
        },
        beat_scheduler="celery.beat:PersistentScheduler",
    )
    
    logger.info("Email service Celery app configured")
    return app


# Global Celery app instance for email service
email_celery_app = create_email_celery_app()


def get_email_celery_app() -> Celery:
    """Get the email service Celery app."""
    return email_celery_app
