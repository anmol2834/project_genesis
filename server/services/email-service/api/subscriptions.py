"""
Subscription Management API
Endpoints for managing email provider subscriptions.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict

from shared.logger import get_logger
from provider.manager.subscription_manager import SubscriptionManager
from provider.scheduler.subscription_scheduler import SubscriptionScheduler

logger = get_logger(__name__)
router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# Initialize managers
subscription_manager = SubscriptionManager()
subscription_scheduler = SubscriptionScheduler()


@router.post("/sync")
async def sync_all_subscriptions():
    """
    Sync subscriptions for all active email accounts.
    Creates new subscriptions or renews existing ones.
    """
    try:
        stats = await subscription_manager.sync_all_subscriptions()
        return {
            "status": "success",
            "message": "Subscription sync completed",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Subscription sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/account/{account_id}/ensure")
async def ensure_account_subscription(account_id: str):
    """
    Ensure a specific account has an active subscription.
    """
    try:
        from shared.database import get_db_session
        from models.email_account import EmailAccount
        from sqlalchemy import select

        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount).where(EmailAccount.id == account_id)
            )
            account = result.scalar_one_or_none()

            if not account:
                raise HTTPException(status_code=404, detail="Account not found")

            result = await subscription_manager.ensure_subscription(account, session)
            await session.commit()

            return {
                "status": "success",
                "account_id": account_id,
                "result": result
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to ensure subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/account/{account_id}")
async def remove_account_subscription(account_id: str):
    """
    Remove subscription for a specific account.
    """
    try:
        success = await subscription_manager.remove_subscription(account_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Subscription not found")

        return {
            "status": "success",
            "message": "Subscription removed",
            "account_id": account_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def subscription_health():
    """
    Get subscription system health status.
    """
    try:
        health = await subscription_scheduler.check_subscription_health()
        return {
            "status": "healthy",
            "subscriptions": health
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.post("/renew/check")
async def force_renewal_check():
    """Manually trigger subscription renewal check."""
    try:
        await subscription_scheduler.force_renewal_check()
        return {"status": "success", "message": "Renewal check completed"}
    except Exception as e:
        logger.error(f"Renewal check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop-unknown-watch")
async def stop_unknown_watch(body: dict):
    """
    Stop a Gmail watch for an email address NOT in the database.
    Use this to silence old watches from previous projects.

    Body: { "email_address": "old@gmail.com", "access_token": "optional_raw_token" }
    """
    from recovery.watch_cleanup import get_watch_cleanup

    email_address = body.get("email_address")
    if not email_address:
        raise HTTPException(status_code=400, detail="email_address required")

    cleanup = get_watch_cleanup()
    result  = await cleanup.stop_unknown_watch(
        email_address=email_address,
        access_token=body.get("access_token"),
    )
    return {"status": "success", "result": result}


@router.get("/unknown-watches")
async def list_unknown_watches():
    """
    List Gmail addresses that sent Pub/Sub notifications but are NOT in the DB.
    These are candidates for watch cleanup.
    """
    try:
        from shared.cache import get_redis
        redis  = await get_redis()
        emails = await redis.smembers("gmail:unknown:watches")
        return {
            "status": "success",
            "unknown_watches": [
                e if isinstance(e, str) else e.decode() for e in emails
            ],
            "hint": "Call POST /subscriptions/stop-unknown-watch to stop each one",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    """
    Show all subscriptions in the database with their current status.
    Use this to verify Gmail watch was registered after connecting an account.
    """
    try:
        from shared.database import get_db_session
        from models.email_provider_subscription import EmailProviderSubscription
        from models.email_account import EmailAccount
        from sqlalchemy import select

        async with get_db_session() as session:
            result = await session.execute(
                select(EmailProviderSubscription, EmailAccount).join(
                    EmailAccount,
                    EmailAccount.id == EmailProviderSubscription.email_account_id,
                    isouter=True
                )
            )
            rows = result.all()

        subscriptions = []
        for sub, acc in rows:
            subscriptions.append({
                "id":             str(sub.id),
                "email":          acc.email_address if acc else "unknown",
                "provider":       sub.provider,
                "status":         sub.status,
                "subscription_id": sub.subscription_id,
                "expires_at":     sub.expires_at.isoformat() if sub.expires_at else None,
                "last_error":     sub.last_error,
                "error_count":    sub.error_count,
            })

        return {
            "status": "success",
            "total": len(subscriptions),
            "subscriptions": subscriptions
        }
    except Exception as e:
        logger.error(f"Failed to get subscription status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
