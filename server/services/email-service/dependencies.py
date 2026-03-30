"""
FastAPI dependencies for email-service.
"""

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from typing import Optional

from shared.config import get_config

_bearer = HTTPBearer(auto_error=False)
_config = get_config()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    token: Optional[str] = Query(default=None, description="JWT token (for SSE EventSource)"),
) -> dict:
    """
    Extract and validate JWT from either:
      - Authorization: Bearer <token>  (standard API calls)
      - ?token=<token>                 (SSE EventSource — browsers can't set headers)
    """
    raw_token = None

    if credentials:
        raw_token = credentials.credentials
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(
            raw_token,
            _config.JWT_SECRET_KEY,
            algorithms=[_config.JWT_ALGORITHM],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    return {"user_id": user_id, "email": payload.get("email")}
