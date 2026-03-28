"""
User Profile Update Schemas
Pydantic models for profile update request/response validation
Supports partial updates (PATCH style) — all fields optional
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional


# ── Update Profile Request ──────────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    """
    Partial update request — only include fields that changed.
    All fields are optional to support granular updates.
    """
    # Profile fields
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    profile_pic: Optional[str] = Field(None, max_length=500)
    
    # Business information
    business_name: Optional[str] = Field(None, min_length=2, max_length=255)
    business_type: Optional[str] = Field(None, max_length=100)
    industries: Optional[List[str]] = None
    country: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = Field(None, max_length=100)
    
    # AI Context fields (these trigger vector updates)
    business_description: Optional[str] = Field(None, min_length=10, max_length=500)
    target_audience: Optional[str] = Field(None, max_length=300)
    communication_tone: Optional[str] = Field(None, max_length=50)
    use_cases: Optional[List[str]] = None
    
    @validator("use_cases")
    def validate_use_cases(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("use_cases cannot be empty if provided")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "business_description": "We help startups scale their outbound sales with AI",
                "communication_tone": "Friendly"
            }
        }


# ── Update Profile Response ─────────────────────────────────────────────────

class UpdateProfileResponse(BaseModel):
    """
    Response after successful profile update.
    Returns updated user data + metadata about the update.
    """
    success: bool = True
    message: str
    user_id: str
    email: str
    full_name: str
    profile_pic: Optional[str]
    business_name: str
    business_type: str
    industries: List[str]
    country: str
    timezone: str
    business_description: Optional[str]
    target_audience: Optional[str]
    communication_tone: Optional[str]
    use_cases: List[str]
    updated_at: str
    
    # Metadata
    fields_updated: List[str]  # List of field names that were changed
    vector_update_triggered: bool  # Whether AI context update was queued
    
    class Config:
        from_attributes = True


# ── Get Profile Response ────────────────────────────────────────────────────

class GetProfileResponse(BaseModel):
    """
    Full user profile response for GET /users/profile
    """
    user_id: str
    email: str
    full_name: str
    profile_pic: Optional[str]
    business_name: str
    business_type: str
    industries: List[str]
    country: str
    timezone: str
    business_description: Optional[str]
    target_audience: Optional[str]
    communication_tone: Optional[str]
    use_cases: List[str]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True
