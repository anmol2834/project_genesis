"""
SMTP Adapter
Validates and normalizes manual SMTP/IMAP credentials.
"""

import asyncio
import smtplib
from typing import Any, Dict

from shared.logger import get_logger

logger = get_logger(__name__)


class SMTPAdapter:
    """Strategy adapter for manual SMTP connections."""

    async def connect(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        email_address = credentials.get("email_address") or credentials.get("username")
        smtp_host = credentials.get("smtp_host")
        smtp_port = credentials.get("smtp_port")
        username = credentials.get("username")
        password = credentials.get("password")
        smtp_use_tls = credentials.get("smtp_use_tls", True)

        if not all([smtp_host, smtp_port, username, password]):
            raise ValueError("smtp_host, smtp_port, username, and password are required for SMTP")

        if not email_address:
            raise ValueError("email address is required for SMTP connection")

        # Verify credentials with a real SMTP handshake (non-blocking via executor)
        await asyncio.get_running_loop().run_in_executor(
            None, self._verify_smtp, smtp_host, smtp_port, username, password, smtp_use_tls
        )

        return {
            "email_address": email_address,
            "provider": "smtp",
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_username": username,
            "smtp_password": password,
            "smtp_use_tls": smtp_use_tls,
            "imap_host": credentials.get("imap_host"),
            "imap_port": credentials.get("imap_port"),
        }

    @staticmethod
    def _verify_smtp(host: str, port: int, username: str, password: str, use_tls: bool) -> None:
        """Blocking SMTP login check — run in executor to avoid blocking the event loop."""
        try:
            # Port 465 → implicit SSL (SMTP_SSL); port 587/others → STARTTLS or plain
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=10)
            else:
                server = smtplib.SMTP(host, port, timeout=10)
                if use_tls:
                    server.starttls()
            server.login(username, password)
            server.quit()
        except smtplib.SMTPAuthenticationError:
            raise ValueError("SMTP authentication failed — check username and password")
        except Exception as exc:
            raise ValueError(f"SMTP connection failed: {exc}")
