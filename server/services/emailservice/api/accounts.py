"""
emailservice — Email Accounts CRUD API (standalone)
Full field set matching the client's EmailAccountFull interface.
"""
from __future__ import annotations
import logging
from uuid import UUID
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from shared.database import get_db_session
from models.email_account import EmailAccount
from models.messages import EmailMessage
from dependencies import get_current_user

logger = logging.getLogger("emailservice.accounts")
router = APIRouter(prefix="/email", tags=["email-accounts"])

_RETENTION_WINDOW = timedelta(hours=24)

def _cutoff() -> datetime:
    return datetime.utcnow() - _RETENTION_WINDOW


def _fmt_account(a: EmailAccount, emails_processed: int = 0) -> dict:
    """Serialize an EmailAccount to the full shape the client expects."""
    return {
        "id":                  str(a.id),
        "user_id":             str(a.user_id),
        "email_address":       a.email_address,
        "display_name":        a.display_name if hasattr(a, "display_name") else None,
        "provider":            a.provider.value if hasattr(a.provider, "value") else str(a.provider),
        "connection_status":   a.connection_status.value if hasattr(a.connection_status, "value") else str(a.connection_status),
        "sync_status":         "idle",   # emailservice uses event-driven model, not polling
        "daily_send_limit":    a.daily_send_limit,
        "daily_sent_count":    a.daily_sent_count,
        "warmup_enabled":      getattr(a, "warmup_enabled", False),
        "is_active":           a.is_active,
        "is_primary":          getattr(a, "is_primary", False),
        "automation_enabled":  a.automation_enabled,
        "last_synced_at":      a.last_synced_at.isoformat() if getattr(a, "last_synced_at", None) else None,
        "last_error_message":  getattr(a, "last_error_message", None),
        "created_at":          a.created_at.isoformat() if getattr(a, "created_at", None) else None,
        "updated_at":          a.updated_at.isoformat() if getattr(a, "updated_at", None) else None,
        # Computed field: total emails processed (from es_messages table)
        "emails_processed":    emails_processed,
    }


@router.get("/accounts")
async def list_accounts(current_user: dict = Depends(get_current_user)):
    """
    List all email accounts for the authenticated user.
    Returns the full EmailAccountFull shape the client expects.
    """
    user_id = UUID(str(current_user["user_id"]))
    async with get_db_session() as db:
        result = await db.execute(
            select(EmailAccount)
            .where(EmailAccount.user_id == user_id)
            .order_by(
                EmailAccount.is_primary.desc() if hasattr(EmailAccount, "is_primary") else EmailAccount.created_at.desc(),
                EmailAccount.created_at.desc(),
            )
        )
        accounts = result.scalars().all()

        # Count emails processed per account from es_messages
        processed_map: dict[str, int] = {}
        for a in accounts:
            try:
                count_result = await db.execute(
                    select(func.count(EmailMessage.id)).where(
                        EmailMessage.email_account_id == a.id,
                        EmailMessage.created_at >= _cutoff(),
                    )
                )
                processed_map[str(a.id)] = count_result.scalar() or 0
            except Exception:
                processed_map[str(a.id)] = 0

    return [_fmt_account(a, processed_map.get(str(a.id), 0)) for a in accounts]


@router.get("/accounts/{account_id}")
async def get_account(account_id: UUID, current_user: dict = Depends(get_current_user)):
    user_id = UUID(str(current_user["user_id"]))
    async with get_db_session() as db:
        result = await db.execute(
            select(EmailAccount).where(
                EmailAccount.id == account_id,
                EmailAccount.user_id == user_id,
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        try:
            count_result = await db.execute(
                select(func.count(EmailMessage.id)).where(
                    EmailMessage.email_account_id == account.id,
                    EmailMessage.created_at >= _cutoff(),
                )
            )
            emails_processed = count_result.scalar() or 0
        except Exception:
            emails_processed = 0

    return _fmt_account(account, emails_processed)


class AccountUpdatePayload(BaseModel):
    is_active:          Optional[bool]  = None
    automation_enabled: Optional[bool]  = None
    daily_send_limit:   Optional[int]   = None
    display_name:       Optional[str]   = None


@router.patch("/accounts/{account_id}")
async def update_account(
    account_id: UUID,
    body: AccountUpdatePayload,
    current_user: dict = Depends(get_current_user),
):
    """Update account settings (automation, limits, display name)."""
    user_id = UUID(str(current_user["user_id"]))
    async with get_db_session() as db:
        result = await db.execute(
            select(EmailAccount).where(
                EmailAccount.id == account_id,
                EmailAccount.user_id == user_id,
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if body.is_active is not None:
            account.is_active = body.is_active
        if body.automation_enabled is not None:
            account.automation_enabled = body.automation_enabled
        if body.daily_send_limit is not None:
            account.daily_send_limit = body.daily_send_limit
        if body.display_name is not None and hasattr(account, "display_name"):
            account.display_name = body.display_name

        await db.commit()
        await db.refresh(account)

    return _fmt_account(account)


@router.post("/accounts/{account_id}/sync")
async def sync_account(account_id: UUID, current_user: dict = Depends(get_current_user)):
    """Trigger a manual sync for an account (re-registers watch)."""
    user_id = UUID(str(current_user["user_id"]))
    async with get_db_session() as db:
        result = await db.execute(
            select(EmailAccount).where(
                EmailAccount.id == account_id,
                EmailAccount.user_id == user_id,
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

    # Re-register watch in background
    try:
        from workers.watch_manager import WatchManager
        import asyncio
        asyncio.create_task(WatchManager().ensure_watch(account))
    except Exception as e:
        logger.warning("Sync watch re-registration failed: %s", e)

    return {"status": "sync_triggered", "account_id": str(account_id)}


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(account_id: UUID, current_user: dict = Depends(get_current_user)):
    user_id = UUID(str(current_user["user_id"]))
    async with get_db_session() as db:
        result = await db.execute(
            select(EmailAccount).where(
                EmailAccount.id == account_id,
                EmailAccount.user_id == user_id,
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        await db.delete(account)
        await db.commit()

