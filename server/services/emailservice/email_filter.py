"""
emailservice — Pre-Queue Smart Filtering Layer
===============================================
Ultra-fast, O(1) / constant-time filtering at every stage of the pipeline.

Design principles:
  1. EARLIEST possible rejection — before any API call if possible
  2. O(1) operations only — frozenset lookups, string prefix checks, bounded substrings
  3. Early-exit — first rejection condition stops all further checks instantly
  4. No regex on large content, no DB lookups, no external calls
  5. Zero-leak guarantee — same filter applied at both fetch stage AND pre-DB stage

Filter stages (in order of cheapness):
  Stage 1 — Gmail label_ids set membership (O(1), frozenset lookup)
             Rejects CATEGORY_PROMOTIONS, CATEGORY_UPDATES, CATEGORY_SOCIAL,
             CATEGORY_FORUMS before any content is fetched.
  Stage 2 — Sender domain/prefix frozenset lookup (O(1))
             Rejects known marketing/automated sender patterns.
  Stage 3 — Subject prefix check (O(k) where k = prefix length, bounded)
             Rejects bounce/delivery-failure/OTP subjects.
  Stage 4 — Snippet substring check (O(200) max, bounded)
             Rejects emails with unsubscribe/marketing indicators in snippet.

Allowlist:
  Known conversational senders bypass Stage 2-4 entirely.
  Populated from config or environment — zero runtime cost.

Content sanitization:
  strip_content() normalizes invisible/control characters before any
  substring check. Simple translate() call — O(n) but n is bounded to 200.
"""
from __future__ import annotations

# ── Stage 1: Gmail category labels (O(1) frozenset lookup) ───────────────────
# These labels are set by Gmail's own classifier — extremely reliable.
# Any email with these labels is promotional/automated by definition.
_REJECT_LABELS: frozenset[str] = frozenset({
    "CATEGORY_PROMOTIONS",
    "CATEGORY_UPDATES",
    "CATEGORY_SOCIAL",
    "CATEGORY_FORUMS",
    # Hard system labels — never store these
    "SPAM",
    "TRASH",
    "DRAFT",
})

# ── Stage 2: Sender domain/prefix rejection (O(1) frozenset lookup) ──────────
# ONLY clearly automated/system sender prefixes.
# Do NOT include legitimate business prefixes like support@, hello@, team@, info@
# — those are real conversational senders.
_REJECT_SENDER_PREFIXES: tuple[str, ...] = (
    "noreply@",
    "no-reply@",
    "donotreply@",
    "do-not-reply@",
    "no_reply@",
    "mailer-daemon@",
    "postmaster@",
    "bounce@",
    "bounces@",
    "automated@",
    "newsletter@",
    "newsletters@",
    "marketing@",
    "promo@",
    "promotions@",
    "unsubscribe@",
)

# Known marketing/transactional domain suffixes (O(1) frozenset lookup on domain part)
_REJECT_SENDER_DOMAINS: frozenset[str] = frozenset({
    # Email marketing platforms
    "mailchimp.com", "sendgrid.net", "sendgrid.com", "mailgun.org", "mailgun.net",
    "amazonses.com", "ses.amazonaws.com", "sparkpostmail.com", "sparkpost.com",
    "mandrillapp.com", "mandrill.com", "constantcontact.com", "campaignmonitor.com",
    "klaviyo.com", "klaviyomail.com", "hubspot.com", "hubspotemail.net",
    "marketo.com", "marketomail.com", "salesforce.com", "exacttarget.com",
    "pardot.com", "eloqua.com", "responsys.com", "braze.com", "iterable.com",
    "customer.io", "customeriomail.com", "drip.com", "convertkit.com",
    "activecampaign.com", "getresponse.com", "aweber.com", "mailerlite.com",
    "sendinblue.com", "brevo.com", "postmarkapp.com", "sendpulse.com",
    "moosend.com", "omnisend.com", "emarsys.com", "dotdigital.com",
    # Common transactional/notification senders
    "notifications.google.com", "accounts.google.com",
    "facebookmail.com", "fb.com", "twittermail.com",
    "linkedin.com", "linkedinmail.com",
    "github.com", "notifications.github.com",
    "slack.com", "slackhq.com",
    "medium.com", "substack.com",
    "quora.com", "reddit.com",
    "amazon.com", "amazon.co.uk", "amazon.in",
    "flipkart.com", "myntra.com", "snapdeal.com",
    "naukri.com", "shine.com", "indeed.com",
    "zomato.com", "swiggy.com", "uber.com", "ola.com",
    "paytm.com", "phonepe.com", "razorpay.com",
    "upstash.com", "vercel.com", "netlify.com",
    "codepen.io", "stackoverflow.com",
    "adobe.com", "microsoft.com", "apple.com",
    "paypal.com", "stripe.com",
})

# ── Stage 3: Subject prefix rejection (O(k), k ≤ 40 chars) ──────────────────
# Only check the first 40 characters of subject — never scan full subject.
_REJECT_SUBJECT_PREFIXES: tuple[str, ...] = (
    "delivery status",
    "mail delivery",
    "undeliverable",
    "address not found",
    "auto-reply:",
    "auto reply:",
    "out of office",
    "automatic reply",
    "[bulk]",
    "[newsletter]",
    "[promo]",
    "[marketing]",
    "[no reply]",
    "[noreply]",
    "fwd: [",
    "re: [bulk",
)

# ── Stage 4: Snippet substring rejection (O(200) max, bounded) ───────────────
# Only check first 200 chars of snippet — never full body.
# These are strong indicators of marketing/automated emails.
_REJECT_SNIPPET_SUBSTRINGS: tuple[str, ...] = (
    "unsubscribe",
    "opt out",
    "opt-out",
    "click here",
    "view in browser",
    "view this email",
    "email preferences",
    "manage preferences",
    "manage subscriptions",
    "privacy policy",
    "terms of service",
    "you are receiving this",
    "you received this",
    "to stop receiving",
    "remove yourself",
    "©",
    "\u00a9",  # © unicode
)

# ── Allowlist: bypass Stage 2-4 for known conversational senders ─────────────
# Add your own domain, key clients, team members here.
# O(1) frozenset lookup — zero cost.
_SENDER_ALLOWLIST: frozenset[str] = frozenset({
    # Add known good domains: e.g. "yourcompany.com", "keypartner.com"
    # These bypass all sender/snippet checks (Stage 2-4)
    # Stage 1 (label check) still applies — Gmail's classifier is authoritative
})

# ── Control characters to strip (for sanitization) ───────────────────────────
# Simple translate table — O(n) but n is bounded to 200 chars max
_CTRL_CHARS = dict.fromkeys(range(32), " ")  # replace control chars with space
_CTRL_CHARS.update({127: " ", 0xFEFF: ""})   # DEL + BOM


def sanitize(text: str, max_len: int = 200) -> str:
    """
    Strip invisible/control characters and normalize whitespace.
    Bounded to max_len — never processes full content.
    O(max_len) — constant time for practical purposes.
    """
    if not text:
        return ""
    # Truncate first — never process more than needed
    t = text[:max_len]
    # Strip control characters
    t = t.translate(_CTRL_CHARS)
    # Collapse whitespace (single pass)
    return " ".join(t.split()).lower()


def should_filter_by_labels(label_ids: list[str] | None) -> bool:
    """
    Stage 1: O(1) Gmail label check.
    Called BEFORE fetching message content — cheapest possible check.
    Returns True if email should be rejected.
    """
    if not label_ids:
        return False
    # frozenset intersection — O(min(|label_ids|, |_REJECT_LABELS|))
    # In practice |label_ids| ≤ 10, so this is O(1)
    return bool(_REJECT_LABELS.intersection(label_ids))


def should_filter(subject: str, from_email: str, snippet: str = "",
                  label_ids: list[str] | None = None) -> bool:
    """
    Full pre-queue filter. Returns True if email must be rejected.
    All operations are O(1) or O(bounded constant).
    Early-exit: stops at first rejection condition.

    Call order (cheapest first):
      1. Label check (O(1) frozenset)
      2. Allowlist check (O(1) frozenset) — bypass if known good sender
      3. Sender domain check (O(1) frozenset on domain part)
      4. Sender prefix check (O(k) startswith tuple)
      5. Subject prefix check (O(40) bounded)
      6. Snippet substring check (O(200) bounded)
    """
    # ── Stage 1: Gmail labels (O(1)) ─────────────────────────────────────────
    if label_ids and should_filter_by_labels(label_ids):
        return True

    # Normalize sender once — used in stages 2, 3, 4
    frm = (from_email or "").strip().lower()

    # ── Allowlist bypass (O(1)) ───────────────────────────────────────────────
    if frm:
        # Extract domain from sender
        at_pos = frm.rfind("@")
        if at_pos != -1:
            domain = frm[at_pos + 1:]
            if domain in _SENDER_ALLOWLIST:
                return False  # known good sender — skip all further checks

    # ── Stage 2: Sender domain rejection (O(1) frozenset) ────────────────────
    if frm:
        at_pos = frm.rfind("@")
        if at_pos != -1:
            domain = frm[at_pos + 1:]
            if domain in _REJECT_SENDER_DOMAINS:
                return True

    # ── Stage 3a: Sender prefix rejection (O(k) C-level startswith) ──────────
    if frm and frm.startswith(_REJECT_SENDER_PREFIXES):
        return True

    # ── Stage 3b: Subject prefix check (O(40) bounded) ───────────────────────
    if subject:
        subj_prefix = sanitize(subject, max_len=40)
        if subj_prefix.startswith(_REJECT_SUBJECT_PREFIXES):
            return True

    # ── Stage 4: Snippet substring check (O(200) bounded) ────────────────────
    if snippet:
        snip = sanitize(snippet, max_len=200)
        for indicator in _REJECT_SNIPPET_SUBSTRINGS:
            if indicator in snip:
                return True

    return False


def should_filter_pre_db(msg: dict) -> bool:
    """
    Zero-leak guarantee: final filter check before database insertion.
    Reuses the same O(1) logic — no additional cost.
    Called by StorageWorker just before store_message_with_retry().
    """
    label_ids = None
    metadata  = msg.get("metadata") or {}
    if isinstance(metadata, dict):
        label_ids = metadata.get("label_ids")

    return should_filter(
        subject   = msg.get("subject", ""),
        from_email= msg.get("from_email", ""),
        snippet   = (metadata.get("snippet") or "")[:200],
        label_ids = label_ids,
    )
