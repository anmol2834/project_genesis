"""
Email Filter - Pre-Filter Layer
Filters out spam, promotions, OTP emails, and no-reply emails.
Only genuine conversation emails pass through.
"""

import re
from typing import List

from shared.logger import get_logger

logger = get_logger(__name__)


class EmailFilter:
    """Filters unwanted emails before processing."""

    # Spam/promotional keywords in subject
    SPAM_KEYWORDS = [
        "unsubscribe", "opt out", "promotional", "advertisement",
        "limited time offer", "act now", "click here", "free trial",
        "congratulations", "you've won", "claim your", "special offer",
        "discount", "sale", "deal", "coupon", "promo code"
    ]

    # OTP/verification keywords
    OTP_KEYWORDS = [
        "otp", "verification code", "confirm your", "verify your",
        "authentication code", "security code", "one-time password",
        "2fa", "two-factor", "login code", "access code"
    ]

    # No-reply patterns
    NOREPLY_PATTERNS = [
        r"noreply@",
        r"no-reply@",
        r"donotreply@",
        r"do-not-reply@",
        r"notifications@",
        r"automated@",
        r"system@",
        r"mailer@"
    ]

    # Promotional sender domains
    PROMO_DOMAINS = [
        "marketing", "newsletter", "promo", "offers", "deals",
        "notifications", "updates", "alerts"
    ]

    async def should_filter(self, subject: str, from_email: str) -> bool:
        """
        Determine if email should be filtered out.
        Returns True if email should be ignored.
        """
        if not subject or not from_email:
            return False

        subject_lower = subject.lower()
        from_lower = from_email.lower()

        # Check OTP emails
        if self._contains_otp(subject_lower):
            logger.debug(f"Filtered OTP email: {subject}")
            return True

        # Check no-reply emails
        if self._is_noreply(from_lower):
            logger.debug(f"Filtered no-reply email from: {from_email}")
            return True

        # Check spam/promotional
        if self._is_promotional(subject_lower, from_lower):
            logger.debug(f"Filtered promotional email: {subject}")
            return True

        return False

    def _contains_otp(self, subject: str) -> bool:
        """Check if subject contains OTP/verification keywords."""
        return any(keyword in subject for keyword in self.OTP_KEYWORDS)

    def _is_noreply(self, from_email: str) -> bool:
        """Check if sender is a no-reply address."""
        return any(
            re.search(pattern, from_email)
            for pattern in self.NOREPLY_PATTERNS
        )

    def _is_promotional(self, subject: str, from_email: str) -> bool:
        """Check if email is promotional."""
        # Check subject for spam keywords
        if any(keyword in subject for keyword in self.SPAM_KEYWORDS):
            return True

        # Check sender domain for promotional indicators
        email_parts = from_email.split("@")
        if len(email_parts) == 2:
            domain = email_parts[1].lower()
            if any(promo in domain for promo in self.PROMO_DOMAINS):
                return True

        return False

    async def get_filter_stats(self) -> dict:
        """Get filtering statistics (for monitoring)."""
        # TODO: Implement stats tracking in Redis
        return {
            "total_filtered": 0,
            "otp_filtered": 0,
            "noreply_filtered": 0,
            "promo_filtered": 0
        }
