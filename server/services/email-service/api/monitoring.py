"""
Monitoring API
Health checks and statistics for the provider source layer.
"""

from fastapi import APIRouter

from shared.logger import get_logger
from provider.scheduler.background_tasks import get_task_manager
from provider.scheduler.subscription_scheduler import SubscriptionScheduler
from provider.filters.email_filter import EmailFilter
from provider.deduplicator.event_deduplicator import EventDeduplicator

logger = get_logger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health")
async def system_health():
    """
    Comprehensive system health check.
    """
    task_manager = get_task_manager()
    scheduler = SubscriptionScheduler()
    
    # Get task status
    task_status = task_manager.get_status()
    
    # Get subscription health
    try:
        subscription_health = await scheduler.check_subscription_health()
    except Exception as e:
        logger.error(f"Failed to check subscription health: {e}")
        subscription_health = {"error": str(e)}
    
    # Overall health
    all_healthy = (
        task_status["subscription_scheduler"]["running"] and
        task_status["smtp_poller"]["running"]
    )
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "background_tasks": task_status,
        "subscriptions": subscription_health
    }


@router.get("/stats")
async def system_stats():
    """
    Get system statistics.
    """
    email_filter = EmailFilter()
    deduplicator = EventDeduplicator()
    
    try:
        filter_stats = await email_filter.get_filter_stats()
        dedup_stats = await deduplicator.get_stats()
        
        return {
            "status": "success",
            "filtering": filter_stats,
            "deduplication": dedup_stats
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/subscriptions/summary")
async def subscriptions_summary():
    """
    Get subscription summary.
    """
    scheduler = SubscriptionScheduler()
    
    try:
        health = await scheduler.check_subscription_health()
        return {
            "status": "success",
            "summary": health
        }
    except Exception as e:
        logger.error(f"Failed to get subscription summary: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
