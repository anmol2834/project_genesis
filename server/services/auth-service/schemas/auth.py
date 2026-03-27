"""
Authentication Schemas
Pydantic models for all auth request/response validation
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional


# ── Shared ───────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ── OTP ──────────────────────────────────────────────────────────────────────

class SendOtpRequest(BaseModel):
    email: EmailStr

    @validator("email")
    def normalize_email(cls, v):
        return v.lower().strip()


class SendOtpResponse(BaseModel):
    success: bool = True
    message: str


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)

    @validator("email")
    def normalize_email(cls, v):
        return v.lower().strip()


class VerifyOtpResponse(BaseModel):
    success: bool = True
    message: str


# ── Signup ────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    business_name: str = Field(..., min_length=2, max_length=255)
    business_type: str = Field(..., max_length=100)
    industries: Optional[List[str]] = Field(default=[])
    country: str = Field(..., max_length=100)
    timezone: str = Field(..., max_length=100)
    business_description: str = Field(..., min_length=10, max_length=500)
    target_audience: Optional[str] = Field(default="", max_length=300)
    communication_tone: str = Field(..., max_length=50)
    use_cases: List[str] = Field(..., min_items=1)

    @validator("email")
    def normalize_email(cls, v):
        return v.lower().strip()

    @validator("use_cases")
    def require_use_cases(cls, v):
        if not v:
            raise ValueError("At least one use case is required")
        return v


class SignupResponse(BaseModel):
    success: bool = True
    message: str
    user_id: str
    email: str
    tokens: TokenResponse


# ── Login ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)

    @validator("email")
    def normalize_email(cls, v):
        return v.lower().strip()


class LoginResponse(BaseModel):
    success: bool = True
    message: str
    user_id: str
    email: str
    full_name: str
    tokens: TokenResponse


# ── Refresh ──────────────────────────────────────────────────────────────────

class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ── Me ───────────────────────────────────────────────────────────────────────

class MeResponse(BaseModel):
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

    class Config:
        from_attributes = True


# ── Verify Token ─────────────────────────────────────────────────────────────

class VerifyTokenResponse(BaseModel):
    valid: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
