"""
User Settings API Endpoints
Handles user preferences and settings management
"""

from fastapi import APIRouter, HTTPException, status, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from shared.database import get_db_session
from shared.logger import get_logger
from schemas.settings import UserSettingsResponse, UpdateUserSettingsRequest
from models.user_settings import UserSettings

logger = get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["User Settings"])


async def verify_token(authorization: str = Header(...)) -> str:
    """
    Verify JWT token and extract user_id
    Calls auth-service /verify-token endpoint
    """
    import httpx
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8001/auth/verify-token",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            
            data = response.json()
            if not data.get("valid"):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            
            return data["user_id"]
    except httpx.RequestError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth service unavailable")


@router.get("", response_model=UserSettingsResponse)
async def get_user_settings(user_id: str = Depends(verify_token)):
    """
    Get current user's settings
    Returns all settings with current values
    Auto-creates settings if they don't exist (for existing users)
    """
    try:
        async with get_db_session() as session:
            # First, verify the user exists
            from models.user import User
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                logger.error(f"User not found in database: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found. Please login again."
                )
            
            # Now check for settings
            result = await session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            
            if not settings:
                # Auto-create default settings for existing users
                logger.info(f"Creating default settings for existing user: {user_id}")
                settings = UserSettings.create_default_settings(user_id)
                session.add(settings)
                await session.commit()
                await session.refresh(settings)
            
            return UserSettingsResponse.model_validate(settings)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get settings error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve settings"
        )


@router.patch("", response_model=UserSettingsResponse)
async def update_user_settings(
    request: UpdateUserSettingsRequest,
    user_id: str = Depends(verify_token)
):
    """
    Update user settings with optimized transaction handling
    Only updates fields that are provided (partial update)
    Handles rapid updates gracefully
    """
    try:
        # Add small delay to allow request deduplication at gateway
        await asyncio.sleep(0.05)
        
        async with get_db_session() as session:
            # Use SELECT FOR UPDATE to prevent race conditions
            result = await session.execute(
                select(UserSettings)
                .where(UserSettings.user_id == user_id)
                .with_for_update()
            )
            settings = result.scalar_one_or_none()
            
            if not settings:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Settings not found"
                )
            
            # Update only provided fields
            update_data = request.model_dump(exclude_unset=True)
            
            if not update_data:
                # No fields to update, return current settings
                return UserSettingsResponse.model_validate(settings)
            
            for field, value in update_data.items():
                setattr(settings, field, value)
            
            # Commit with retry on deadlock
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await session.commit()
                    break
                except Exception as e:
                    if attempt < max_retries - 1 and "deadlock" in str(e).lower():
                        logger.warning(f"Deadlock detected, retrying... (attempt {attempt + 1})")
                        await asyncio.sleep(0.1 * (attempt + 1))
                        await session.rollback()
                    else:
                        raise
            
            await session.refresh(settings)
            
            logger.info(f"Settings updated for user: {user_id} - fields: {list(update_data.keys())}")
            
            return UserSettingsResponse.model_validate(settings)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update settings error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update settings"
        )


@router.post("/reset", response_model=UserSettingsResponse)
async def reset_user_settings(user_id: str = Depends(verify_token)):
    """
    Reset all settings to default values
    """
    try:
        async with get_db_session() as session:
            result = await session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            
            if not settings:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Settings not found"
                )
            
            # Reset to defaults
            settings.auto_sync_replies = True
            settings.sync_sent_folder = True
            settings.sync_frequency = '5m'
            settings.automation_level = 'assist'
            settings.learn_from_edits = True
            settings.personalize_per_lead = True
            settings.avoid_repetition = True
            settings.max_reply_length = 'medium'
            settings.automation_enabled = True
            settings.pause_on_weekends = True
            settings.respect_sending_hours = True
            settings.delay_between_steps = '3d'
            settings.stop_on_reply = True
            settings.max_emails_per_lead = 5
            settings.email_new_reply = True
            settings.email_campaign_complete = True
            settings.email_lead_status = False
            settings.email_weekly_digest = True
            settings.inapp_realtime_replies = True
            settings.inapp_ai_actions = True
            settings.inapp_team_activity = False
            settings.inapp_system_alerts = True
            settings.notification_batching = 'instant'
            settings.two_factor_enabled = False
            settings.require_2fa_for_team = False
            settings.default_member_role = 'member'
            settings.invite_by_domain = False
            settings.require_admin_approval = True
            settings.analytics_improvement = True
            settings.personalization_data = True
            settings.third_party_integrations = False
            
            await session.commit()
            await session.refresh(settings)
            
            logger.info(f"Settings reset to defaults for user: {user_id}")
            
            return UserSettingsResponse.model_validate(settings)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset settings error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset settings"
        )
