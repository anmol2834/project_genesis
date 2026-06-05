"""
emailservice — /email/connect (standalone, identical interface to email-service)
"""
from __future__ import annotations
import asyncio, logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from shared.database import get_db_session
from schemas import ConnectEmailRequest, ConnectEmailResponse, ConnectEmailData
from connection_service import EmailConnectionService
from dependencies import get_current_user

logger = logging.getLogger("emailservice.connect")
router = APIRouter(prefix="/email", tags=["email-connection"])
_service = EmailConnectionService()


@router.post("/connect", response_model=ConnectEmailResponse, status_code=200)
async def connect_email(body: ConnectEmailRequest, current_user: dict = Depends(get_current_user)):
    user_id = UUID(str(current_user["user_id"]))
    creds = body.credentials.model_dump(exclude_none=True)
    if body.email:
        creds["email_address"] = str(body.email)
    try:
        async with get_db_session() as db:
            account = await _service.connect_and_save(db=db, user_id=user_id,
                                                       provider=body.provider, credentials=creds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.exception("Email connection failed for user %s: %s", user_id, e)
        raise HTTPException(status_code=500, detail="Email connection failed. Please try again.")

    # Self-healing reconnect: reset account_state to active and is_active to True.
    # This handles the case where the account was previously in token_revoked state
    # (e.g. app was in testing mode, token expired after 7 days, user re-authorized).
    # After reconnect, the full pipeline resumes automatically.
    # CRITICAL: await this synchronously to ensure state is reset before returning
    await _restore_account_on_reconnect(account)
    asyncio.create_task(_register_watch(account))

    return ConnectEmailResponse(
        status="success",
        message="Email account connected successfully",
        data=ConnectEmailData(
            email=account.email_address,
            provider=account.provider.value,
            status=account.connection_status.value,
            account_id=account.id,
        ),
    )


async def _restore_account_on_reconnect(account) -> None:
    """
    Reset account_state to 'active' and is_active to True on reconnect.
    Evicts stale Redis cache so next pipeline call reads fresh state.

    This is the self-healing path: user reconnects via OAuth →
    account_state=active → pipeline resumes → history replay catches missed emails.
    """
    try:
        from models.email_account import EmailAccount
        from sqlalchemy import update as sa_update
        from shared.database import get_db_session
        from token_cache import invalidate

        async with get_db_session() as session:
            await session.execute(
                sa_update(EmailAccount)
                .where(EmailAccount.id == account.id)
                .values(
                    account_state="active",
                    is_active=True,
                    last_error_message=None,
                )
            )
            await session.commit()

        # Evict stale snap from all cache layers
        await invalidate(account.email_address)

        logger.info(
            "Account restored to active state on reconnect | email=%s",
            account.email_address,
        )
    except Exception as e:
        logger.error("Failed to restore account state on reconnect for %s: %s",
                     account.email_address, e)


async def _register_watch(account) -> None:
    try:
        from workers.watch_manager import WatchManager
        await WatchManager().ensure_watch(account)
    except Exception as e:
        logger.error("Watch registration failed for %s: %s", account.email_address, e)
