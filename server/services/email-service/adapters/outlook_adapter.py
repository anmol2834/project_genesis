"""
Outlook OAuth Adapter
Exchanges authorization code for tokens and fetches the user's Outlook email address.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

import httpx

from shared.config import get_config
from shared.logger import get_logger

logger = get_logger(__name__)
config = get_config()

_MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_MICROSOFT_USERINFO_URL = "https://graph.microsoft.com/v1.0/me"


class OutlookAdapter:
    """Strategy adapter for Outlook OAuth connections."""

    async def connect(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exchange OAuth code for tokens and resolve the Outlook email address.
        Returns a normalized dict consumed by EmailConnectionService.
        """
        code = credentials.get("code")
        if not code:
            raise ValueError("OAuth authorization code is required for Outlook")

        client_id = config.MICROSOFT_CLIENT_ID_EMAIL
        client_secret = config.MICROSOFT_CLIENT_SECRET_EMAIL
        tenant_id = config.MICROSOFT_TENANT_ID_EMAIL or "common"
        redirect_uri = config.MICROSOFT_REDIRECT_URI_EMAIL

        if not client_id or not client_secret:
            raise RuntimeError("Microsoft email OAuth credentials are not configured")

        token_url = _MICROSOFT_TOKEN_URL.format(tenant=tenant_id)

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Exchange code → tokens
            token_resp = await client.post(
                token_url,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                    "scope": "https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/User.Read offline_access",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if token_resp.status_code != 200:
            logger.error("Microsoft token exchange failed: %s", token_resp.text)
            raise ValueError("Failed to exchange authorization code with Microsoft")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)

        if not access_token:
            raise ValueError("Microsoft did not return an access token")

        # Fetch user email via Microsoft Graph API
        async with httpx.AsyncClient(timeout=10.0) as client:
            info_resp = await client.get(
                _MICROSOFT_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if info_resp.status_code != 200:
            logger.error("Microsoft userinfo fetch failed: %s", info_resp.text)
            raise ValueError("Failed to fetch Outlook account info")

        user_info = info_resp.json()
        email_address = user_info.get("mail") or user_info.get("userPrincipalName")
        if not email_address:
            raise ValueError("Could not resolve email address from Microsoft account")

        return {
            "email_address": email_address,
            "provider": "outlook",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expiry": datetime.utcnow() + timedelta(seconds=expires_in),
            "provider_account_id": user_info.get("id"),
        }
