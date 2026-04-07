"""
emailservice — Email Filter
Pre-filter layer: rejects only clearly automated/system emails.
Philosophy: when in doubt, PASS the email through. False negatives
(missing a promo) are far better than false positives (dropping a real email).
"""
from __future__ import annotations
import re

# ── Only filter clearly automated system emails ───────────────────────────────
# These are bounce notifications, delivery failures, and mailer-daemon messages.
# We do NOT filter newsletters, promos, or job alerts here — that's the user's choice.

_AUTOMATED_SUBJECT_RE = re.compile(
    r"^delivery status notification"
    r"|^mail delivery (failed|failure|error)"
    r"|^undeliverable:"
    r"|^address not found"
    r"|^auto-?reply:"
    r"|^out of office",
    re.IGNORECASE,
)

_AUTOMATED_SENDER_RE = re.compile(
    r"^noreply@"
    r"|^no-reply@"
    r"|^donotreply@"
    r"|^do-not-reply@"
    r"|^mailer-daemon@"
    r"|^postmaster@"
    r"|^bounce@"
    r"|^automated@",
    re.IGNORECASE,
)

_OTP_SUBJECT_RE = re.compile(
    r"\botp\b"
    r"|\bone.?time.?password\b"
    r"|\bverification code\b"
    r"|\bauthentication code\b",
    re.IGNORECASE,
)


def should_filter(subject: str, from_email: str) -> bool:
    """
    Returns True ONLY for clearly automated system messages.
    Conservative — prefers false negatives over false positives.
    """
    subj = (subject or "").strip()
    frm  = (from_email or "").strip().lower()

    # Bounce / delivery failure subjects
    if _AUTOMATED_SUBJECT_RE.search(subj):
        return True

    # Mailer-daemon / noreply senders (exact prefix match only)
    if _AUTOMATED_SENDER_RE.match(frm):
        return True

    # OTP emails (no business value for AI processing)
    if _OTP_SUBJECT_RE.search(subj):
        return True

    return False
