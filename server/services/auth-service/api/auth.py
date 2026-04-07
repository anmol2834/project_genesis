"""
Authentication API Endpoints
Covers: signup, login, logout, token refresh, /me, verify-token, OTP

Redis removed — OTP, rate limiting, and token blacklisting are backed by
the auth_store PostgreSQL table (utils/db_store.py).
Embedding generation runs in a background thread (no Celery broker needed).
"""
from __future__ import annotations

import time
import asyncio
import concurrent.futures
import sys
import os

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from shared.database import get_db_session
from shared.logger import get_logger
from shared.config import get_config

from schemas.auth import (
    SignupRequest, SignupResponse, LoginRequest, LoginResponse,
    RefreshRequest, RefreshResponse, TokenResponse, MeResponse, VerifyTokenResponse,
    SendOtpRequest, SendOtpResponse, VerifyOtpRequest, VerifyOtpResponse,
)
from models.user import User
from models.user_settings import UserSettings
from utils.password import hash_password, verify_password
from utils.jwt import create_access_token, create_refresh_token, decode_token
from utils.db_store import (
    store_set, store_get, store_delete,
    store_increment, store_exists,
)

logger = get_logger(__name__)
config = get_config()

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer()

# ── Constants ─────────────────────────────────────────────────────────────────
LOGIN_RATE_LIMIT  = 5
LOGIN_RATE_WINDOW = 300          # 5 minutes
TOKEN_BLACKLIST_TTL = config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
DEV_OTP  = "000000"
OTP_TTL  = 600                   # 10 minutes

# Thread pool for synchronous embedding work
_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="embed")


# ── Rate limiting (DB-backed) ─────────────────────────────────────────────────

async def _check_login_rate_limit(identifier: str) -> None:
    try:
        key = f"login_attempts:{identifier}"
        val = await store_get(key)
        if val and int(val) >= LOGIN_RATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again in 5 minutes.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Rate limit check failed: %s", e)


async def _record_login_attempt(identifier: str) -> None:
    try:
        await store_increment(f"login_attempts:{identifier}", LOGIN_RATE_WINDOW)
    except Exception as e:
        logger.error("Failed to record login attempt: %s", e)


async def _clear_login_attempts(identifier: str) -> None:
    try:
        await store_delete(f"login_attempts:{identifier}")
    except Exception as e:
        logger.error("Failed to clear login attempts: %s", e)


# ── Token blacklist (DB-backed) ───────────────────────────────────────────────

async def _blacklist_token(jti: str, ttl: int) -> None:
    try:
        await store_set(f"blacklist:{jti}", "1", max(ttl, 1))
    except Exception as e:
        logger.error("Failed to blacklist token: %s", e)


async def _is_token_blacklisted(jti: str) -> bool:
    try:
        return await store_exists(f"blacklist:{jti}")
    except Exception as e:
        logger.error("Failed to check token blacklist: %s", e)
        return False   # fail open


# ── Auth dependency ───────────────────────────────────────────────────────────

async def _get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
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


# ── Embedding (background thread, no Celery/Redis) ────────────────────────────

def _run_embedding_sync(user_id: str) -> None:
    """
    Synchronous embedding generation — runs in a thread pool worker.
    Fetches user from DB, generates vectors, stores in Qdrant.
    No Celery, no Redis broker needed.
    """
    try:
        from sqlalchemy import create_engine, text as sa_text
        from sqlalchemy.pool import NullPool
        from shared.config import get_config as _cfg
        from services.embedding_service import generate_user_embeddings

        cfg = _cfg()
        sync_url = cfg.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        connect_args = {"sslmode": "require"} if "rds.amazonaws.com" in sync_url else {}
        engine = create_engine(sync_url, connect_args=connect_args, poolclass=NullPool)

        with engine.connect() as conn:
            row = conn.execute(
                sa_text("""
                    SELECT id, business_name, business_type, industry,
                           country, business_description, target_audience,
                           communication_tone, use_cases, created_at
                    FROM users WHERE id = :uid
                """),
                {"uid": user_id},
            ).fetchone()

        if row is None:
            logger.error("Embedding: user %s not found in DB", user_id)
            return

        user_data = {
            "user_id":              user_id,
            "business_name":        row.business_name or "",
            "business_type":        row.business_type or "",
            "industries":           row.industry or [],
            "country":              row.country or "",
            "business_description": row.business_description or "",
            "target_audience":      row.target_audience or "",
            "communication_tone":   row.communication_tone or "professional",
            "use_cases":            row.use_cases or [],
            "created_at":           row.created_at.isoformat() if row.created_at else "",
        }

        success = generate_user_embeddings(user_id, user_data)
        if success:
            logger.info("Embeddings created for user %s", user_id)
        else:
            logger.error("Embedding generation returned False for user %s", user_id)

    except Exception as exc:
        logger.error("Embedding thread error for user %s: %s", user_id, exc)


async def _queue_embedding(user_id: str) -> None:
    """Submit embedding work to the thread pool (fire-and-forget)."""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_thread_pool, _run_embedding_sync, user_id)


# ── OTP endpoints ─────────────────────────────────────────────────────────────

@router.post("/send-otp", response_model=SendOtpResponse)
async def send_otp(request: SendOtpRequest):
    """Store a dev OTP in the DB. In production, send a real email."""
    try:
        email_key = f"otp:{request.email.lower().strip()}"
        await store_set(email_key, DEV_OTP, OTP_TTL)
    except Exception as e:
        logger.error("Failed to send OTP: %s", e)
    # Always return success — don't reveal internal errors
    return SendOtpResponse(success=True, message="Verification code sent")


@router.post("/verify-otp", response_model=VerifyOtpResponse)
async def verify_otp(request: VerifyOtpRequest):
    """Verify OTP. Accepts dev bypass '000000' or the stored code."""
    try:
        email_key = f"otp:{request.email.lower().strip()}"
        stored = await store_get(email_key)

        if request.code != DEV_OTP and (stored is None or request.code != stored):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code",
            )

        await store_delete(email_key)
        return VerifyOtpResponse(success=True, message="Email verified")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("OTP verification failed: %s", e)
        if request.code == DEV_OTP:
            return VerifyOtpResponse(success=True, message="Email verified")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed",
        )


# ── Auth endpoints ────────────────────────────────────────────────────────────

@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest):
    """
    Register a new user.
    1. Validate & deduplicate email
    2. Hash password (bcrypt)
    3. Persist to PostgreSQL
    4. Initialize default user settings
    5. Issue JWT access + refresh tokens
    6. Queue Qdrant embedding (background thread, non-blocking)
    """
    try:
        email_normalized = request.email.lower().strip()
        logger.info("Signup attempt: %s", email_normalized)

        async with get_db_session() as session:
            existing = (await session.execute(
                select(User).where(User.email == email_normalized)
            )).scalar_one_or_none()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered",
                )

            new_user = User(
                email=email_normalized,
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
            await session.flush()

            user_id = str(new_user.id)

            # Pass the UUID object directly — avoids asyncpg type mismatch
            default_settings = UserSettings.create_default_settings(new_user.id)
            default_settings.workspace_name = request.business_name
            session.add(default_settings)

            await session.commit()
            await session.refresh(new_user)
            logger.info("User + settings saved: user_id=%s", user_id)

        access_token  = create_access_token(user_id, email_normalized)
        refresh_token = create_refresh_token(user_id, email_normalized)

        # Fire-and-forget embedding — never blocks signup
        try:
            await _queue_embedding(user_id)
            logger.info("Embedding queued for user %s", user_id)
        except Exception as e:
            logger.error("Embedding queue failed (non-critical): %s", e)

        logger.info("User created: %s", user_id)
        return SignupResponse(
            success=True,
            message="Account created successfully",
            user_id=user_id,
            email=email_normalized,
            tokens=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            ),
        )

    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    except Exception as e:
        logger.error("Signup error: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Signup failed")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, req: Request):
    """Authenticate user. Rate limited: 5 attempts / 5 min per IP."""
    client_ip = req.client.host if req.client else "unknown"
    rate_key = f"{client_ip}:{request.email}"

    await _check_login_rate_limit(rate_key)

    try:
        email_normalized = request.email.lower().strip()
        async with get_db_session() as session:
            user = (await session.execute(
                select(User).where(User.email == email_normalized)
            )).scalar_one_or_none()

        if not user or not verify_password(request.password, user.password_hash):
            await _record_login_attempt(rate_key)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        await _clear_login_attempts(rate_key)

        user_id = str(user.id)
        access_token  = create_access_token(user_id, user.email)
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
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login error: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed")


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(request: RefreshRequest):
    """Exchange a valid refresh token for a new access token."""
    payload = decode_token(request.refresh_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    jti = payload.get("jti")
    if jti and await _is_token_blacklisted(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    new_access_token = create_access_token(payload["sub"], payload["email"])
    return RefreshResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: RefreshRequest,
    payload: dict = Depends(_get_current_user),
):
    """Blacklist the current access token + the provided refresh token."""
    access_jti = payload.get("jti")
    if access_jti:
        ttl = max(int(payload.get("exp", 0) - time.time()), 1)
        await _blacklist_token(access_jti, ttl)

    refresh_payload = decode_token(request.refresh_token)
    if refresh_payload and refresh_payload.get("type") == "refresh":
        refresh_jti = refresh_payload.get("jti")
        if refresh_jti:
            ttl = max(int(refresh_payload.get("exp", 0) - time.time()), 1)
            await _blacklist_token(refresh_jti, ttl)

    return {"success": True, "message": "Logged out successfully"}


@router.get("/me", response_model=MeResponse)
async def get_me(payload: dict = Depends(_get_current_user)):
    """Return the authenticated user's profile."""
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
    """Validate an access token. Used by other microservices for inter-service auth."""
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        return VerifyTokenResponse(valid=False, user_id=None, email=None)

    jti = payload.get("jti")
    if jti and await _is_token_blacklisted(jti):
        return VerifyTokenResponse(valid=False, user_id=None, email=None)

    return VerifyTokenResponse(valid=True, user_id=payload["sub"], email=payload["email"])
