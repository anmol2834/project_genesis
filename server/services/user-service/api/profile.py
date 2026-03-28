"""
User Profile API Endpoints
Handles user profile management with smart AI context updates
"""

from fastapi import APIRouter, HTTPException, status, Depends, Header, BackgroundTasks
from sqlalchemy import select
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from shared.database import get_db_session
from shared.logger import get_logger
from schemas.profile import UpdateProfileRequest, UpdateProfileResponse, GetProfileResponse
from models.user import User

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["User Profile"])


async def verify_token(authorization: str = Header(...)) -> str:
    """
    Verify JWT token and extract user_id.
    Calls auth-service /verify-token endpoint.
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


# AI context fields that trigger vector updates
AI_CONTEXT_FIELDS = {
    "business_name", "business_type", "industries",
    "business_description", "target_audience", "communication_tone", "use_cases"
}


@router.get("/profile", response_model=GetProfileResponse)
async def get_profile(user_id: str = Depends(verify_token)):
    """
    Get current user's profile.
    Returns all profile fields including AI context.
    """
    try:
        async with get_db_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            return GetProfileResponse(
                user_id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                profile_pic=user.profile_pic,
                business_name=user.business_name,
                business_type=user.business_type,
                industries=user.industry or [],
                country=user.country,
                timezone=user.timezone,
                business_description=user.business_description,
                target_audience=user.target_audience,
                communication_tone=user.communication_tone,
                use_cases=user.use_cases or [],
                created_at=user.created_at.isoformat(),
                updated_at=user.updated_at.isoformat(),
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get profile error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profile"
        )


@router.patch("/update-profile", response_model=UpdateProfileResponse)
async def update_profile(
    request: UpdateProfileRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(verify_token)
):
    """
    Update user profile with smart diff detection.
    
    Flow:
        1. Fetch existing user data
        2. Compare with incoming data to detect changes
        3. Update PostgreSQL with ONLY changed fields
        4. If AI context fields changed, trigger async vector update
        5. Return updated profile + metadata
    
    Performance: <200ms (vector update happens in background)
    """
    try:
        async with get_db_session() as session:
            # Step 1: Fetch existing user
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Step 2: Detect changed fields
            update_data = request.model_dump(exclude_unset=True)
            
            if not update_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields provided for update"
                )
            
            changed_fields = []
            
            for field, new_value in update_data.items():
                # Map schema field names to model attribute names
                model_field = field
                if field == "industries":
                    model_field = "industry"
                
                old_value = getattr(user, model_field, None)
                
                # Compare values (handle lists specially)
                if isinstance(new_value, list):
                    if old_value != new_value:
                        changed_fields.append(field)
                        setattr(user, model_field, new_value)
                else:
                    if old_value != new_value:
                        changed_fields.append(field)
                        setattr(user, model_field, new_value)
            
            if not changed_fields:
                logger.info(f"No actual changes detected for user {user_id}")
                # Return current data without DB write
                return UpdateProfileResponse(
                    success=True,
                    message="No changes detected",
                    user_id=str(user.id),
                    email=user.email,
                    full_name=user.full_name,
                    profile_pic=user.profile_pic,
                    business_name=user.business_name,
                    business_type=user.business_type,
                    industries=user.industry or [],
                    country=user.country,
                    timezone=user.timezone,
                    business_description=user.business_description,
                    target_audience=user.target_audience,
                    communication_tone=user.communication_tone,
                    use_cases=user.use_cases or [],
                    updated_at=user.updated_at.isoformat(),
                    fields_updated=[],
                    vector_update_triggered=False,
                )
            
            # Step 3: Persist to PostgreSQL
            user.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(user)
            
            logger.info(f"Profile updated for {user_id}, fields: {changed_fields}")
            
            # Step 4: Check if AI context fields changed
            ai_fields_changed = [f for f in changed_fields if f in AI_CONTEXT_FIELDS]
            vector_update_triggered = False
            
            if ai_fields_changed:
                try:
                    # Run embedding update in FastAPI background task (no Redis/Celery needed)
                    # This runs in a thread pool after the response is sent — zero latency impact
                    from tasks.embedding_tasks import run_embedding_update_sync
                    background_tasks.add_task(run_embedding_update_sync, user_id, ai_fields_changed)
                    vector_update_triggered = True
                    logger.info(f"Vector update scheduled for {user_id}, AI fields: {ai_fields_changed}")
                except Exception as e:
                    logger.error(f"Failed to schedule vector update: {e}", exc_info=True)
            
            # Step 5: Return updated profile
            return UpdateProfileResponse(
                success=True,
                message="Profile updated successfully",
                user_id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                profile_pic=user.profile_pic,
                business_name=user.business_name,
                business_type=user.business_type,
                industries=user.industry or [],
                country=user.country,
                timezone=user.timezone,
                business_description=user.business_description,
                target_audience=user.target_audience,
                communication_tone=user.communication_tone,
                use_cases=user.use_cases or [],
                updated_at=user.updated_at.isoformat(),
                fields_updated=changed_fields,
                vector_update_triggered=vector_update_triggered,
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update profile error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )
