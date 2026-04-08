"""
emailservice — OAuth + SMTP adapters (standalone)
Identical logic to email-service/adapters/, no cross-service imports.
"""
from __future__ import annotations
import asyncio, smtplib
from datetime import datetime, timedelta
from typing import Any, Dict
import httpx
from shared.config import get_config
import logging

logger = logging.getLogger("emailservice.adapters")


class GmailAdapter:
    async def connect(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        cfg = get_config()
        code = credentials.get("code")
        if not code:
            raise ValueError("OAuth authorization code is required for Gmail")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": cfg.GOOGLE_CLIENT_ID_EMAIL,
                    "client_secret": cfg.GOOGLE_CLIENT_SECRET_EMAIL,
                    "redirect_uri": cfg.GOOGLE_REDIRECT_URI_EMAIL,
                    "grant_type": "authorization_code",
                },
            )
        if resp.status_code != 200:
            raise ValueError("Failed to exchange authorization code with Google")
        td = resp.json()
        access_token = td.get("access_token")
        if not access_token:
            raise ValueError("Google did not return an access token")
        async with httpx.AsyncClient(timeout=10.0) as client:
            info = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if info.status_code != 200:
            raise ValueError("Failed to fetch Gmail account info")
        ui = info.json()
        email = ui.get("email")
        if not email:
            raise ValueError("Could not resolve email from Google account")
        return {
            "email_address": email, "provider": "gmail",
            "access_token": access_token, "refresh_token": td.get("refresh_token"),
            "token_expiry": datetime.utcnow() + timedelta(seconds=td.get("expires_in", 3600)),
            "provider_account_id": ui.get("sub"),
        }


class OutlookAdapter:
    async def connect(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        cfg = get_config()
        code = credentials.get("code")
        if not code:
            raise ValueError("OAuth authorization code is required for Outlook")
        tenant = cfg.MICROSOFT_TENANT_ID_EMAIL or "common"

        token_data: Dict[str, Any] = {
            "code": code,
            "client_id": cfg.MICROSOFT_CLIENT_ID_EMAIL,
            "redirect_uri": cfg.MICROSOFT_REDIRECT_URI_EMAIL,
            "grant_type": "authorization_code",
            "scope": "https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/User.Read offline_access",
        }

        # PKCE flow: use code_verifier instead of client_secret when provided
        code_verifier = credentials.get("code_verifier")
        if code_verifier:
            token_data["code_verifier"] = code_verifier
        else:
            token_data["client_secret"] = cfg.MICROSOFT_CLIENT_SECRET_EMAIL

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code != 200:
            error_detail = ""
            try:
                err_json = resp.json()
                error_detail = f": {err_json.get('error')} — {err_json.get('error_description', '')[:200]}"
            except Exception:
                error_detail = f": HTTP {resp.status_code}"
            logger.error("Microsoft token exchange failed%s", error_detail)
            raise ValueError(f"Failed to exchange authorization code with Microsoft{error_detail}")
        td = resp.json()
        access_token = td.get("access_token")
        if not access_token:
            raise ValueError("Microsoft did not return an access token")
        async with httpx.AsyncClient(timeout=10.0) as client:
            info = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if info.status_code != 200:
            raise ValueError("Failed to fetch Outlook account info")
        ui = info.json()
        email = ui.get("mail") or ui.get("userPrincipalName")
        if not email:
            raise ValueError("Could not resolve email from Microsoft account")
        return {
            "email_address": email, "provider": "outlook",
            "access_token": access_token, "refresh_token": td.get("refresh_token"),
            "token_expiry": datetime.utcnow() + timedelta(seconds=td.get("expires_in", 3600)),
            "provider_account_id": ui.get("id"),
        }


class SMTPAdapter:
    async def connect(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        email = credentials.get("email_address") or credentials.get("username")
        host  = credentials.get("smtp_host")
        port  = credentials.get("smtp_port")
        user  = credentials.get("username")
        pwd   = credentials.get("password")
        tls   = credentials.get("smtp_use_tls", True)
        if not all([host, port, user, pwd]):
            raise ValueError("smtp_host, smtp_port, username, and password are required")
        if not email:
            raise ValueError("email_address is required for SMTP")
        await asyncio.get_running_loop().run_in_executor(
            None, self._verify, host, port, user, pwd, tls
        )
        return {
            "email_address": email, "provider": "smtp",
            "smtp_host": host, "smtp_port": port,
            "smtp_username": user, "smtp_password": pwd,
            "smtp_use_tls": tls,
            "imap_host": credentials.get("imap_host"),
            "imap_port": credentials.get("imap_port"),
        }

    @staticmethod
    def _verify(host, port, user, pwd, tls):
        try:
            if port == 465:
                s = smtplib.SMTP_SSL(host, port, timeout=10)
            else:
                s = smtplib.SMTP(host, port, timeout=10)
                if tls:
                    s.starttls()
            s.login(user, pwd)
            s.quit()
        except smtplib.SMTPAuthenticationError:
            raise ValueError("SMTP authentication failed")
        except Exception as e:
            raise ValueError(f"SMTP connection failed: {e}")
