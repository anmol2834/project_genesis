"""
Authentication API Endpoints - Enterprise Grade
Covers: signup, login, logout, token refresh, /me, verify-token
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from shared.database import get_db_session
from shared.cache import get_redis_client
from shared.logger import get_logger
from shared.config import get_config

from schemas.auth import (
    SignupRequest, SignupResponse, LoginRequest, LoginResponse,
    RefreshRequest, RefreshResponse, TokenResponse, MeResponse, VerifyTokenResponse,
    SendOtpRequest, SendOtpResponse, VerifyOtpRequest, VerifyOtpResponse
)
from models.user import User
from models.user_settings import UserSettings
from utils.password import hash_password, verify_password
from utils.jwt import create_access_token, create_refresh_token, decode_token
from tasks.embedding_tasks import create_user_embedding

logger = get_logger(__name__)
config = get_config()

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer()

# ── Rate limiting constants ──────────────────────────────────────────────────
LOGIN_RATE_LIMIT = 5          # max attempts
LOGIN_RATE_WINDOW = 300       # 5 minutes window (seconds)
TOKEN_BLACKLIST_TTL = config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _check_login_rate_limit(identifier: str):
    """Block brute-force: max 5 login attempts per 5 minutes per IP/email."""
    redis = get_redis_client()
    key = f"login_attempts:{identifier}"
    attempts = await redis.get(key)
    if attempts and int(attempts) >= LOGIN_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again in 5 minutes."
        )


async def _record_login_attempt(identifier: str):
    redis = get_redis_client()
    key = f"login_attempts:{identifier}"
    pipe = redis.pipeline()
    await pipe.incr(key)
    await pipe.expire(key, LOGIN_RATE_WINDOW)
    await pipe.execute()


async def _clear_login_attempts(identifier: str):
    redis = get_redis_client()
    await redis.delete(f"login_attempts:{identifier}")


async def _blacklist_token(jti: str, ttl: int):
    """Add token JTI to Redis blacklist."""
    redis = get_redis_client()
    await redis.setex(f"blacklist:{jti}", ttl, "1")


async def _is_token_blacklisted(jti: str) -> bool:
    redis = get_redis_client()
    return await redis.exists(f"blacklist:{jti}") == 1


async def _get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    """Dependency: validate Bearer token and return payload."""
    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not an access token")

    jti = payload.get("jti")
    if jti and await _is_token_blacklisted(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    return payload


# ── OTP constants ────────────────────────────────────────────────────────────
DEV_OTP = "000000"          # default bypass code — replace with real email send later
OTP_TTL = 600               # 10 minutes


# ── OTP Endpoints ─────────────────────────────────────────────────────────────

@router.post("/send-otp", response_model=SendOtpResponse)
async def send_otp(request: SendOtpRequest):
    """
    Store a dev OTP (000000) in Redis keyed by email.
    In production this would send a real email.
    """
    redis = get_redis_client()
    await redis.setex(f"otp:{request.email.lower().strip()}", OTP_TTL, DEV_OTP)
    return SendOtpResponse(success=True, message="Verification code sent")


@router.post("/verify-otp", response_model=VerifyOtpResponse)
async def verify_otp(request: VerifyOtpRequest):
    """
    Verify the OTP submitted by the user.
    Accepts the stored code OR the hardcoded dev bypass '000000'.
    Deletes the key on success so it cannot be reused.
    """
    redis = get_redis_client()
    key = f"otp:{request.email.lower().strip()}"
    stored = await redis.get(key)

    # Accept dev bypass OR the stored code
    if request.code != DEV_OTP and (stored is None or request.code != stored):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

    await redis.delete(key)
    return VerifyOtpResponse(success=True, message="Email verified")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest):
    """
    Register a new user.
    1. Validate & deduplicate email
    2. Hash password (bcrypt)
    3. Persist to PostgreSQL
    4. Initialize default user settings
    5. Issue JWT access + refresh tokens
    6. Queue Qdrant embedding task (non-blocking)
    """
    try:
        logger.info(f"Signup attempt: {request.email}")

        async with get_db_session() as session:
            existing = (await session.execute(
                select(User).where(User.email == request.email)
            )).scalar_one_or_none()

            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

            # Create new user
            new_user = User(
                email=request.email,
                password_hash=hash_password(request.password),
                full_name=request.full_name,
                profile_pic=f"https://api.dicebear.com/7.x/initials/svg?seed={request.full_name}",
                business_name=request.business_name,
                business_type=request.business_type,
                industry=request.industries,
                country=request.country,
                timezone=request.timezone,
                business_description=request.business_description,
                target_audience=request.target_audience,
                communication_tone=request.communication_tone,
                use_cases=request.use_cases,
            )
            session.add(new_user)
            await session.flush()  # Flush to get user.id before creating settings
            
            user_id = str(new_user.id)
            
            # Initialize default user settings
            default_settings = UserSettings.create_default_settings(user_id)
            # Set workspace name to business name by default
            default_settings.workspace_name = request.business_name
            session.add(default_settings)
            
            await session.commit()
            await session.refresh(new_user)

        access_token = create_access_token(user_id, request.email)
        refresh_token = create_refresh_token(user_id, request.email)

        try:
            create_user_embedding.delay(user_id)
        except Exception as e:
            logger.error(f"Embedding queue failed: {e}")

        logger.info(f"User created successfully: {user_id} with default settings")

        return SignupResponse(
            success=True,
            message="Account created successfully",
            user_id=user_id,
            email=request.email,
            tokens=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )
        )

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    except Exception as e:
        logger.error(f"Signup error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Signup failed")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, req: Request):
    """
    Authenticate user with email + password.
    - Rate limited: 5 attempts / 5 min per IP
    - Returns access + refresh tokens on success
    """
    client_ip = req.client.host if req.client else "unknown"
    rate_key = f"{client_ip}:{request.email}"

    await _check_login_rate_limit(rate_key)

    try:
        async with get_db_session() as session:
            user = (await session.execute(
                select(User).where(User.email == request.email)
            )).scalar_one_or_none()

        if not user or not verify_password(request.password, user.password_hash):
            await _record_login_attempt(rate_key)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Successful login — clear rate limit counter
        await _clear_login_attempts(rate_key)

        user_id = str(user.id)
        access_token = create_access_token(user_id, user.email)
        refresh_token = create_refresh_token(user_id, user.email)

        return LoginResponse(
            success=True,
            message="Login successful",
            user_id=user_id,
            email=user.email,
            full_name=user.full_name,
            tokens=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed")


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(request: RefreshRequest):
    """
    Exchange a valid refresh token for a new access token.
    Refresh token is NOT rotated (stateless design).
    """
    payload = decode_token(request.refresh_token)

    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    jti = payload.get("jti")
    if jti and await _is_token_blacklisted(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    user_id = payload["sub"]
    email = payload["email"]

    new_access_token = create_access_token(user_id, email)

    return RefreshResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: RefreshRequest,
    payload: dict = Depends(_get_current_user)
):
    """
    Logout: blacklist the current access token + the provided refresh token.
    Both tokens are invalidated immediately in Redis.
    """
    # Blacklist access token
    access_jti = payload.get("jti")
    if access_jti:
        exp = payload.get("exp", 0)
        ttl = max(int(exp - time.time()), 1)
        await _blacklist_token(access_jti, ttl)

    # Blacklist refresh token
    refresh_payload = decode_token(request.refresh_token)
    if refresh_payload and refresh_payload.get("type") == "refresh":
        refresh_jti = refresh_payload.get("jti")
        if refresh_jti:
            exp = refresh_payload.get("exp", 0)
            ttl = max(int(exp - time.time()), 1)
            await _blacklist_token(refresh_jti, ttl)

    return {"success": True, "message": "Logged out successfully"}


@router.get("/me", response_model=MeResponse)
async def get_me(payload: dict = Depends(_get_current_user)):
    """
    Return the authenticated user's profile.
    Requires valid Bearer access token.
    """
    user_id = payload["sub"]

    async with get_db_session() as session:
        user = (await session.execute(
            select(User).where(User.id == user_id)
        )).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return MeResponse(
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
    )


@router.post("/verify-token", response_model=VerifyTokenResponse)
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """
    Validate an access token and return its claims.
    Used by other microservices for inter-service auth.
    """
    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        return VerifyTokenResponse(valid=False, user_id=None, email=None)

    if payload.get("type") != "access":
        return VerifyTokenResponse(valid=False, user_id=None, email=None)

    jti = payload.get("jti")
    if jti and await _is_token_blacklisted(jti):
        return VerifyTokenResponse(valid=False, user_id=None, email=None)

    return VerifyTokenResponse(
        valid=True,
        user_id=payload["sub"],
        email=payload["email"],
    )
