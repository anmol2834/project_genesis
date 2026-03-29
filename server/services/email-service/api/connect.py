"""
Email Connection API
POST /email/connect  — unified endpoint for Gmail, Outlook, SMTP
Automatically creates Pub/Sub watch subscription after connecting.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from schemas.connect import ConnectEmailRequest, ConnectEmailResponse, ConnectEmailData
from services.email_connection_service import EmailConnectionService
from shared.database.postgres import get_db_session
from shared.logger import get_logger
from dependencies import get_current_user

logger = get_logger(__name__)
router = APIRouter(prefix="/email", tags=["email-connection"])

_service = EmailConnectionService()


@router.post(
    "/connect",
    response_model=ConnectEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Connect an email account (Gmail / Outlook / SMTP)",
)
async def connect_email(
    body: ConnectEmailRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id: UUID = UUID(str(current_user["user_id"]))

    creds = body.credentials.model_dump(exclude_none=True)
    if body.email:
        creds["email_address"] = str(body.email)

    try:
        async with get_db_session() as db:
            account = await _service.connect_and_save(
                db=db,
                user_id=user_id,
                provider=body.provider,
                credentials=creds,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    except Exception as exc:
        logger.exception("Email connection failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email connection failed. Please try again.",
        )

    # ── Auto-register Pub/Sub watch after successful connection ──────────────
    # This is what makes Google actually send push notifications to our webhook.
    # Run in background so it doesn't block the response.
    import asyncio
    asyncio.create_task(_register_watch_subscription(account))

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


async def _register_watch_subscription(account) -> None:
    """
    Background task: register Gmail/Outlook watch subscription after connect.
    Errors are logged but never bubble up to the user.
    """
    try:
        from provider.manager.subscription_manager import SubscriptionManager
        from shared.database import get_db_session

        manager = SubscriptionManager()
        async with get_db_session() as session:
            result = await manager.ensure_subscription(account, session)
            await session.commit()
        logger.info(
            f"Watch subscription {result} for {account.email_address} "
            f"(provider={account.provider})"
        )
    except Exception as e:
        logger.error(
            f"Failed to register watch subscription for {account.email_address}: {e}",
            exc_info=True
        )
