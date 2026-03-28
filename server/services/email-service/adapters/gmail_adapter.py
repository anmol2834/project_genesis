"""
Gmail OAuth Adapter
Exchanges authorization code for tokens and fetches the user's Gmail address.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

import httpx

from shared.config import get_config
from shared.logger import get_logger

logger = get_logger(__name__)
config = get_config()

_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GmailAdapter:
    """Strategy adapter for Gmail OAuth connections."""

    async def connect(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exchange OAuth code for tokens and resolve the Gmail address.
        Returns a normalized dict consumed by EmailConnectionService.
        """
        code = credentials.get("code")
        if not code:
            raise ValueError("OAuth authorization code is required for Gmail")

        client_id = config.GOOGLE_CLIENT_ID_EMAIL
        client_secret = config.GOOGLE_CLIENT_SECRET_EMAIL
        redirect_uri = config.GOOGLE_REDIRECT_URI_EMAIL

        if not client_id or not client_secret:
            raise RuntimeError("Google email OAuth credentials are not configured")

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Exchange code → tokens
            token_resp = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )

        if token_resp.status_code != 200:
            logger.error("Google token exchange failed: %s", token_resp.text)
            raise ValueError("Failed to exchange authorization code with Google")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)

        if not access_token:
            raise ValueError("Google did not return an access token")

        # Fetch user email via userinfo endpoint
        async with httpx.AsyncClient(timeout=10.0) as client:
            info_resp = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if info_resp.status_code != 200:
            logger.error("Google userinfo fetch failed: %s", info_resp.text)
            raise ValueError("Failed to fetch Gmail account info")

        user_info = info_resp.json()
        email_address = user_info.get("email")
        if not email_address:
            raise ValueError("Could not resolve email address from Google account")

        return {
            "email_address": email_address,
            "provider": "gmail",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expiry": datetime.utcnow() + timedelta(seconds=expires_in),
            "provider_account_id": user_info.get("sub"),
        }
