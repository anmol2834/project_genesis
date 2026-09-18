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
    code: Optional[str] = Field(default="000000", max_length=10)

    @validator("email")
    def normalize_email(cls, v):
        return v.lower().strip()

    @validator("code", pre=True, always=True)
    def default_dev_code(cls, v):
        if not v or str(v).strip() == "":
            return "000000"
        return str(v).strip()


class VerifyOtpResponse(BaseModel):
    success: bool = True
    message: str


# ── Signup ────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    business_name: str = Field(..., min_length=1, max_length=255)
    business_type: str = Field(default="General", max_length=100)
    industries: Optional[List[str]] = Field(default=[])
    country: str = Field(default="India", max_length=100)
    timezone: str = Field(default="UTC", max_length=100)
    business_description: str = Field(default="AI Email Automation", max_length=500)
    target_audience: Optional[str] = Field(default="", max_length=300)
    communication_tone: Optional[str] = Field(default="professional", max_length=50)
    use_cases: Optional[List[str]] = Field(default=["support"])

    @validator("email")
    def normalize_email(cls, v):
        return v.lower().strip()

    @validator("communication_tone", pre=True, always=True)
    def default_tone(cls, v):
        return v if v else "professional"

    @validator("use_cases", pre=True, always=True)
    def default_use_cases(cls, v):
        return v if (v and len(v) > 0) else ["support"]


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
