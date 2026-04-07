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


async def _register_watch(account) -> None:
    try:
        from workers.watch_manager import WatchManager
        await WatchManager().ensure_watch(account)
    except Exception as e:
        logger.error("Watch registration failed for %s: %s", account.email_address, e)
