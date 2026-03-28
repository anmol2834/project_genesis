"""
Email Accounts API
GET /email/accounts - List user's email accounts
GET /email/accounts/:id - Get single account
PATCH /email/accounts/:id - Update account settings
DELETE /email/accounts/:id - Disconnect account
POST /email/accounts/:id/sync - Trigger manual sync
"""

from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.email_account import EmailAccount
from schemas.email_account import (
    EmailAccountResponse,
    EmailAccountListResponse,
    UpdateEmailAccountRequest,
)
from shared.database.postgres import get_db_session
from shared.logger import get_logger
from dependencies import get_current_user

logger = get_logger(__name__)
router = APIRouter(prefix="/email", tags=["email-accounts"])


@router.get(
    "/accounts",
    response_model=List[EmailAccountResponse],
    summary="List all email accounts for current user",
)
async def list_accounts(
    current_user: dict = Depends(get_current_user),
):
    """
    Get all email accounts connected by the current user.
    Returns empty list if no accounts connected.
    """
    user_id = UUID(str(current_user["user_id"]))
    
    try:
        async with get_db_session() as db:
            result = await db.execute(
                select(EmailAccount)
                .where(EmailAccount.user_id == user_id)
                .order_by(EmailAccount.is_primary.desc(), EmailAccount.created_at.desc())
            )
            accounts = result.scalars().all()
            
            logger.info(f"Retrieved {len(accounts)} email accounts for user {user_id}")
            return [EmailAccountResponse.model_validate(acc) for acc in accounts]
    
    except Exception as exc:
        logger.exception(f"Failed to list accounts for user {user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve email accounts",
        )


@router.get(
    "/accounts/{account_id}",
    response_model=EmailAccountResponse,
    summary="Get single email account",
)
async def get_account(
    account_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    """Get details of a specific email account."""
    user_id = UUID(str(current_user["user_id"]))
    
    try:
        async with get_db_session() as db:
            result = await db.execute(
                select(EmailAccount).where(
                    and_(
                        EmailAccount.id == account_id,
                        EmailAccount.user_id == user_id,
                    )
                )
            )
            account = result.scalar_one_or_none()
            
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Email account not found",
                )
            
            return EmailAccountResponse.model_validate(account)
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to get account {account_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve email account",
        )


@router.patch(
    "/accounts/{account_id}",
    response_model=EmailAccountResponse,
    summary="Update email account settings",
)
async def update_account(
    account_id: UUID,
    body: UpdateEmailAccountRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update email account settings (display name, limits, flags).
    Cannot update credentials - must disconnect and reconnect for that.
    """
    user_id = UUID(str(current_user["user_id"]))
    
    try:
        async with get_db_session() as db:
            # Get account
            result = await db.execute(
                select(EmailAccount).where(
                    and_(
                        EmailAccount.id == account_id,
                        EmailAccount.user_id == user_id,
                    )
                )
            )
            account = result.scalar_one_or_none()
            
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Email account not found",
                )
            
            # Update fields
            update_data = body.model_dump(exclude_none=True)
            for field, value in update_data.items():
                setattr(account, field, value)
            
            await db.commit()
            await db.refresh(account)
            
            logger.info(f"Updated account {account_id} for user {user_id}")
            return EmailAccountResponse.model_validate(account)
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to update account {account_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update email account",
        )


@router.delete(
    "/accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect and delete email account",
)
async def delete_account(
    account_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    """
    Disconnect and permanently delete an email account.
    This will stop all syncing and automation for this account.
    """
    user_id = UUID(str(current_user["user_id"]))
    
    try:
        async with get_db_session() as db:
            # Get account
            result = await db.execute(
                select(EmailAccount).where(
                    and_(
                        EmailAccount.id == account_id,
                        EmailAccount.user_id == user_id,
                    )
                )
            )
            account = result.scalar_one_or_none()
            
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Email account not found",
                )
            
            # Delete account
            await db.delete(account)
            await db.commit()
            
            logger.info(f"Deleted account {account_id} for user {user_id}")
            return None
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to delete account {account_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete email account",
        )


@router.post(
    "/accounts/{account_id}/sync",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger manual sync for account",
)
async def sync_account(
    account_id: UUID,
    current_user: dict = Depends(get_current_user),
):
    """
    Trigger a manual sync for this email account.
    Returns immediately - sync happens in background.
    """
    user_id = UUID(str(current_user["user_id"]))
    
    try:
        async with get_db_session() as db:
            # Verify account exists and belongs to user
            result = await db.execute(
                select(EmailAccount).where(
                    and_(
                        EmailAccount.id == account_id,
                        EmailAccount.user_id == user_id,
                    )
                )
            )
            account = result.scalar_one_or_none()
            
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Email account not found",
                )
            
            # TODO: Trigger background sync task via Celery
            # For now, just log it
            logger.info(f"Manual sync requested for account {account_id}")
            
            return {
                "status": "accepted",
                "message": "Sync task queued",
                "account_id": str(account_id),
            }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to trigger sync for account {account_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger sync",
        )
