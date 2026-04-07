"""
emailservice — Email Accounts CRUD API (standalone)
"""
from __future__ import annotations
import logging
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from shared.database import get_db_session
from models.email_account import EmailAccount
from dependencies import get_current_user

logger = logging.getLogger("emailservice.accounts")
router = APIRouter(prefix="/email", tags=["email-accounts"])


class AccountResponse(BaseModel):
    id: UUID
    email_address: str
    provider: str
    connection_status: str
    is_active: bool
    daily_send_limit: int
    daily_sent_count: int
    automation_enabled: bool

    class Config:
        from_attributes = True


@router.get("/accounts")
async def list_accounts(current_user: dict = Depends(get_current_user)):
    user_id = UUID(str(current_user["user_id"]))
    async with get_db_session() as db:
        result = await db.execute(
            select(EmailAccount)
            .where(EmailAccount.user_id == user_id)
            .order_by(EmailAccount.is_primary.desc(), EmailAccount.created_at.desc())
        )
        accounts = result.scalars().all()
    return [
        {
            "id": str(a.id), "email_address": a.email_address,
            "provider": a.provider.value, "connection_status": a.connection_status.value,
            "is_active": a.is_active, "daily_send_limit": a.daily_send_limit,
            "daily_sent_count": a.daily_sent_count, "automation_enabled": a.automation_enabled,
        }
        for a in accounts
    ]


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(account_id: UUID, current_user: dict = Depends(get_current_user)):
    user_id = UUID(str(current_user["user_id"]))
    async with get_db_session() as db:
        result = await db.execute(
            select(EmailAccount).where(EmailAccount.id == account_id, EmailAccount.user_id == user_id)
        )
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        await db.delete(account)
        await db.commit()
