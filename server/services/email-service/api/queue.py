"""
Queue API - Monitoring and Management
Endpoints for queue statistics, health checks, and DLQ management.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from shared.logger import get_logger
from email_queue.monitoring.queue_monitor import QueueMonitor

logger = get_logger(__name__)
router = APIRouter(prefix="/queue", tags=["queue"])

# Initialize monitor
queue_monitor = QueueMonitor()


@router.get("/stats")
async def get_queue_stats():
    """
    Get comprehensive queue statistics.
    
    Returns:
        Queue stats including lengths, workers, tasks, and processing rate
    """
    try:
        stats = await queue_monitor.get_queue_stats()
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def check_queue_health():
    """
    Check queue system health.
    
    Returns:
        Health status with warnings and errors
    """
    try:
        health = await queue_monitor.check_queue_health()
        
        # Return appropriate status code
        if health["status"] == "unhealthy":
            return health, 503
        elif health["status"] == "degraded":
            return health, 200
        else:
            return health
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dlq")
async def get_dlq_events(limit: int = 100):
    """
    Get events from Dead Letter Queue.
    
    Args:
        limit: Maximum number of events to retrieve (default: 100)
        
    Returns:
        List of DLQ events
    """
    try:
        if limit > 1000:
            raise HTTPException(
                status_code=400,
                detail="Limit cannot exceed 1000"
            )
        
        events = await queue_monitor.get_dlq_events(limit)
        
        return {
            "status": "success",
            "count": len(events),
            "events": events
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get DLQ events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/processing-rate")
async def get_processing_rate():
    """
    Get current processing rate (events per minute).
    
    Returns:
        Processing rate statistics
    """
    try:
        stats = await queue_monitor.get_queue_stats()
        processing_rate = stats.get("processing_rate", {})
        
        return {
            "status": "success",
            "processing_rate": processing_rate
        }
        
    except Exception as e:
        logger.error(f"Failed to get processing rate: {e}")
        raise HTTPException(status_code=500, detail=str(e))
