"""
emailservice — Token Cache (standalone, no email-service imports)
3-layer cache: L1 in-process → L2 Redis → L3 PostgreSQL

Cache strategy: read-through + write-once
  - L1 (in-process dict, 300s TTL): zero Redis cost on hot path
  - L2 (Redis SETEX, TTL aligned to token expiry): written once on cache miss
  - L3 (PostgreSQL): source of truth, queried only on L1+L2 miss

Key optimizations:
  - No DEL operations during normal operation — keys expire naturally via TTL
  - invalidate() only called when data is known stale (token refresh, watch update)
  - _write_snap_to_redis() uses SET NX-style TTL guard to avoid redundant writes
  - advance_history_cursor() updates L1 in-place instead of invalidating
"""
from __future__ import annotations
import json, time, logging
from datetime import datetime, timedelta
from typing import Optional
import httpx

from shared.cache import get_redis
from shared.database import get_db_session
from encryption import decrypt_token, encrypt_token

logger = logging.getLogger("emailservice.token_cache")

_L1: dict[str, dict] = {}
_L1_TTL = 300

# Track when each key was last written to Redis to avoid redundant SETEX calls
# within the same TTL window. Key: email, Value: monotonic timestamp of last write.
_L2_LAST_WRITE: dict[str, float] = {}
_L2_WRITE_GUARD_S = 60  # don't re-write to Redis if written within last 60s


def _l1_get(email: str) -> Optional[dict]:
    e = _L1.get(email)
    if e and (time.time() - e.get("_ts", 0)) < _L1_TTL:
        return e
    _L1.pop(email, None)
    return None

def _l1_set(email: str, snap: dict) -> None:
    snap["_ts"] = time.time()
    _L1[email] = snap

def _l1_invalidate(email: str) -> None:
    _L1.pop(email, None)
    _L2_LAST_WRITE.pop(email, None)  # reset write guard so next miss re-populates L2


async def _write_snap_to_redis(email: str, snap: dict, ttl: int) -> None:
    """
    Write snap to Redis with TTL guard — avoids redundant SETEX calls.
    Skips the write if we wrote within the last _L2_WRITE_GUARD_S seconds.
    Uses SETEX (overwrite) — never DEL + SET.
    """
    now = time.monotonic()
    last_write = _L2_LAST_WRITE.get(email, 0.0)
    if (now - last_write) < _L2_WRITE_GUARD_S:
        return  # written recently — skip to avoid churn
    try:
        redis = await get_redis()
        await redis.setex(f"es:snap:{email}", max(60, ttl), json.dumps(snap))
        _L2_LAST_WRITE[email] = now
    except Exception:
        pass


async def get_account_snapshot(email: str) -> Optional[dict]:
    snap = _l1_get(email)
    if snap:
        return snap
    try:
        redis = await get_redis()
        raw = await redis.get(f"es:snap:{email}")
        if raw:
            snap = json.loads(raw)
            _l1_set(email, snap)
            return snap
    except Exception:
        pass
    snap = await _load_from_db(email)
    if snap:
        _l1_set(email, snap)
        # Compute TTL aligned to token expiry (max 1h)
        token_expiry_raw = snap.get("token_expiry")
        ttl = 3600
        if token_expiry_raw:
            try:
                exp = datetime.fromisoformat(token_expiry_raw)
                if exp.tzinfo:
                    exp = exp.replace(tzinfo=None)
                remaining = int((exp - datetime.utcnow()).total_seconds()) - 300
                if remaining > 0:
                    ttl = min(ttl, remaining)
            except Exception:
                pass
        await _write_snap_to_redis(email, snap, ttl)
    return snap


async def _load_from_db(email: str) -> Optional[dict]:
    try:
        from models.email_account import EmailAccount
        from sqlalchemy import select
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount).where(EmailAccount.email_address == email)
            )
            acct = result.scalar_one_or_none()
            if not acct:
                return None
            return {
                "id":              str(acct.id),
                "user_id":         str(acct.user_id),
                "email_address":   acct.email_address,
                "provider":        acct.provider.value,
                "access_token":    acct.access_token,
                "refresh_token":   acct.refresh_token,
                "token_expiry":    acct.token_expiry.isoformat() if acct.token_expiry else None,
                "last_history_id": acct.last_history_id,
                "watch_expiry":    acct.watch_expiry.isoformat() if acct.watch_expiry else None,
                "automation_enabled": acct.automation_enabled,
                "is_active":       acct.is_active,
                "smtp_host":       acct.smtp_host,
                "smtp_port":       acct.smtp_port,
                "smtp_username":   acct.smtp_username,
                "smtp_password":   acct.smtp_password,
                "smtp_use_tls":    acct.smtp_use_tls,
            }
    except Exception as e:
        logger.error("DB snapshot load failed for %s: %s", email, e)
        return None


async def invalidate(email: str) -> None:
    """
    Invalidate both L1 and L2 cache for an account.
    Only call this when data is KNOWN stale (token refresh, watch update).
    Do NOT call this on every read or after every DB write.
    """
    _l1_invalidate(email)
    try:
        redis = await get_redis()
        await redis.delete(f"es:snap:{email}")
    except Exception:
        pass


async def get_fresh_token(snap: dict) -> str:
    from shared.config import get_config
    cfg = get_config()
    expiry_raw = snap.get("token_expiry")
    expiry: Optional[datetime] = None
    if expiry_raw:
        try:
            expiry = datetime.fromisoformat(expiry_raw)
            if expiry.tzinfo:
                expiry = expiry.replace(tzinfo=None)
        except Exception:
            pass
    if expiry and expiry > datetime.utcnow() + timedelta(minutes=5):
        return decrypt_token(snap["access_token"])
    refresh_enc = snap.get("refresh_token")
    if not refresh_enc:
        return decrypt_token(snap["access_token"])
    provider = snap.get("provider", "gmail")
    try:
        if provider == "gmail":
            url  = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": cfg.GOOGLE_CLIENT_ID_EMAIL,
                "client_secret": cfg.GOOGLE_CLIENT_SECRET_EMAIL,
                "refresh_token": decrypt_token(refresh_enc),
                "grant_type": "refresh_token",
            }
        else:
            tenant = cfg.MICROSOFT_TENANT_ID_EMAIL or "common"
            url  = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
            data = {
                "client_id": cfg.MICROSOFT_CLIENT_ID_EMAIL,
                "client_secret": cfg.MICROSOFT_CLIENT_SECRET_EMAIL,
                "refresh_token": decrypt_token(refresh_enc),
                "grant_type": "refresh_token",
                "scope": "https://graph.microsoft.com/.default offline_access",
            }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, data=data)
        if resp.status_code != 200:
            # Token refresh failed — log with detail and raise so caller can handle
            logger.error("Token refresh failed for %s: HTTP %d — %s",
                         snap.get("email_address"), resp.status_code, resp.text[:200])
            raise RuntimeError(f"Token refresh HTTP {resp.status_code} for {snap.get('email_address')}")
        td = resp.json()
        new_token  = td["access_token"]
        new_expiry = datetime.utcnow() + timedelta(seconds=td.get("expires_in", 3600))
        await _persist_token(snap["id"], new_token, new_expiry)
        # Update L1 in-place with new token — no DEL needed
        updated_snap = dict(snap)
        updated_snap["access_token"] = encrypt_token(new_token)
        updated_snap["token_expiry"] = new_expiry.isoformat()
        _l1_set(snap["email_address"], updated_snap)
        # Force L2 refresh with new token (bypass write guard)
        _L2_LAST_WRITE.pop(snap["email_address"], None)
        remaining = int((new_expiry - datetime.utcnow()).total_seconds()) - 300
        await _write_snap_to_redis(snap["email_address"], updated_snap, max(60, remaining))
        return new_token
    except Exception as e:
        logger.error("Token refresh exception for %s: %s", snap.get("email_address"), e)
        return decrypt_token(snap["access_token"])


async def _persist_token(account_id: str, new_token: str, expiry: datetime) -> None:
    try:
        from models.email_account import EmailAccount
        from sqlalchemy import update as sa_update
        from uuid import UUID
        async with get_db_session() as session:
            await session.execute(
                sa_update(EmailAccount)
                .where(EmailAccount.id == UUID(account_id))
                .values(access_token=encrypt_token(new_token), token_expiry=expiry)
            )
            await session.commit()
    except Exception as e:
        logger.error("Failed to persist token: %s", e)


async def advance_history_cursor(account_id: str, new_history_id: str, email: str) -> None:
    """
    Update last_history_id in DB and patch L1 cache in-place.
    Does NOT invalidate L2 (Redis) — the key will expire naturally.
    This avoids a DEL + re-fetch cycle on every email processed.
    """
    try:
        from models.email_account import EmailAccount
        from sqlalchemy import update as sa_update
        from uuid import UUID
        async with get_db_session() as session:
            await session.execute(
                sa_update(EmailAccount)
                .where(EmailAccount.id == UUID(account_id))
                .values(last_history_id=str(new_history_id))
            )
            await session.commit()
        # Patch L1 in-place — no Redis operation needed
        snap = _l1_get(email)
        if snap:
            snap["last_history_id"] = str(new_history_id)
            _l1_set(email, snap)
    except Exception as e:
        logger.error("Cursor advance failed: %s", e)
