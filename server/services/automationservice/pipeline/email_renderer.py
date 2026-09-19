"""
automationservice — Email Renderer (Phase 14)
=============================================
Presentation-only email rendering layer.

Architectural Contract:
  - Receives ONLY policy-approved structured output.
  - Its sole responsibility is presentation (HTML, plain text, formatting, signature, branding, templates).
  - MUST NOT:
      * invent claims
      * add discounts
      * change prices
      * add availability
      * add shipping promises
      * rewrite policy
      * introduce new business facts
  - Rendering must be SEMANTICALLY PASSIVE.
"""
from __future__ import annotations

import html
import logging
import re
from typing import Any

from pipeline.contracts import RenderedEmailPayload

logger = logging.getLogger("automationservice.pipeline.email_renderer")


class SemanticDriftError(Exception):
    """Raised when email renderer violates semantic passivity by mutating factual content."""
    pass


def _extract_numbers_and_currencies(text: str) -> set[str]:
    """Extract numeric sequences and currency figures for semantic invariance check."""
    tokens = re.findall(r"(?:[\$₹€£]\s*\d+(?:,\d{3})*(?:\.\d+)?|\b\d+(?:\.\d+)?%|\b\d+(?:,\d{3})*(?:\.\d+)?\b)", text)
    return {re.sub(r"\s+", "", t) for t in tokens}


def verify_semantic_passivity(
    original_body: str,
    rendered_text: str,
    disclaimers: list[str] | None = None,
    authorized_metadata: list[str] | None = None,
) -> bool:
    """
    Verify that the rendering layer was 100% semantically passive.

    Guarantees:
      1. All numeric tokens and currency amounts in original body are preserved.
      2. No new numeric figures or discounts were introduced (outside authorized disclaimers & metadata).
    """
    orig_nums = _extract_numbers_and_currencies(original_body)
    rendered_nums = _extract_numbers_and_currencies(rendered_text)

    # All original figures must exist in rendered text
    missing_nums = orig_nums - rendered_nums
    if missing_nums:
        logger.error("[email_renderer] Semantic drift: original numbers missing from rendered text: %s", missing_nums)
        raise SemanticDriftError(f"Renderer dropped original factual numbers: {missing_nums}")

    # Permitted additions are ONLY from approved disclaimers and signature branding
    disclaimer_text = " ".join((disclaimers or []) + (authorized_metadata or []))
    allowed_nums = _extract_numbers_and_currencies(disclaimer_text)

    added_nums = rendered_nums - orig_nums - allowed_nums
    if added_nums:
        logger.error("[email_renderer] Semantic drift: renderer injected new numbers not in original prose: %s", added_nums)
        raise SemanticDriftError(f"Renderer injected unapproved numbers: {added_nums}")

    return True



def render_email(
    subject: str,
    body: str,
    business_context: dict[str, Any] | None = None,
    disclaimers: list[str] | None = None,
    recipient: str = "",
    recipient_name: str | None = None,
) -> RenderedEmailPayload:
    """
    Render customer response into presentation-ready HTML and Plain Text.

    Args:
        subject: Approved email subject.
        body: Approved email body prose.
        business_context: Business branding and profile info.
        disclaimers: Approved legal disclaimers added by Policy Engine.
        recipient: Target recipient email address.
        recipient_name: Optional customer name.

    Returns:
        RenderedEmailPayload with verified semantically passive presentation.
    """
    biz_ctx = business_context or {}
    company_name = biz_ctx.get("business_name") or "Our Support Team"
    brand_color = biz_ctx.get("brand_color") or "#1a56db"
    clean_disclaimers = [d.strip() for d in (disclaimers or []) if d.strip()]

    # ── 1. Render Plain Text ──────────────────────────────────────────────────
    clean_body = body.strip()

    text_parts = [clean_body]

    # Signature
    text_parts.append("\n\n---\nBest regards,\n" + company_name)
    contact_info = biz_ctx.get("contact_phone") or biz_ctx.get("contact_email")
    if contact_info:
        text_parts.append(f"Contact: {contact_info}")

    # Disclaimers
    if clean_disclaimers:
        text_parts.append("\n\nLegal & Policy Notices:\n" + "\n".join(f"• {d}" for d in clean_disclaimers))

    text_body = "".join(text_parts).strip()

    # ── 2. Render Responsive HTML ─────────────────────────────────────────────
    # Split paragraphs by double newline
    paragraphs = [p.strip() for p in clean_body.split("\n\n") if p.strip()]
    html_paragraphs = []
    for p in paragraphs:
        # Check if paragraph contains bullet lines
        lines = p.split("\n")
        if any(line.strip().startswith(("- ", "• ", "* ")) for line in lines):
            items = []
            for line in lines:
                clean_line = re.sub(r"^[-•*]\s*", "", line.strip())
                if clean_line:
                    items.append(f"<li style='margin-bottom: 6px;'>{html.escape(clean_line)}</li>")
            html_paragraphs.append(f"<ul style='padding-left: 20px; margin: 12px 0;'>{''.join(items)}</ul>")
        else:
            safe_p = html.escape(p).replace("\n", "<br/>")
            html_paragraphs.append(f"<p style='margin: 0 0 16px 0; line-height: 1.6;'>{safe_p}</p>")

    body_html_content = "".join(html_paragraphs)

    # Disclaimers HTML
    disclaimers_html = ""
    if clean_disclaimers:
        d_items = "".join(f"<li style='margin-bottom: 4px;'>{html.escape(d)}</li>" for d in clean_disclaimers)
        disclaimers_html = f"""
        <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 11px; color: #6b7280; line-height: 1.5;">
            <strong style="color: #4b5563;">Notices & Terms:</strong>
            <ul style="padding-left: 16px; margin: 6px 0 0 0;">
                {d_items}
            </ul>
        </div>
        """

    # Full styled email template
    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(subject)}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1f2937;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed;">
        <tr>
            <td align="center" style="padding: 24px 12px;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <!-- Brand Header -->
                    <tr>
                        <td style="padding: 24px 32px; border-bottom: 2px solid {brand_color}; background-color: #fafafa;">
                            <h2 style="margin: 0; font-size: 18px; font-weight: 600; color: #111827;">{html.escape(company_name)}</h2>
                        </td>
                    </tr>
                    <!-- Main Body -->
                    <tr>
                        <td style="padding: 32px; font-size: 14px; color: #374151;">
                            {body_html_content}
                            <!-- Signature -->
                            <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #f3f4f6; color: #4b5563; font-size: 13px;">
                                <p style="margin: 0 0 4px 0;">Best regards,</p>
                                <p style="margin: 0; font-weight: 600; color: #111827;">{html.escape(company_name)}</p>
                            </div>
                            {disclaimers_html}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    # ── 3. Verify Semantic Invariance (Passive Rendering) ─────────────────────
    authorized_meta = [
        str(v) for k, v in biz_ctx.items()
        if k in ("contact_phone", "contact_email", "business_name", "address", "website") and v
    ]

    verify_semantic_passivity(
        original_body=clean_body,
        rendered_text=text_body,
        disclaimers=clean_disclaimers,
        authorized_metadata=authorized_meta,
    )


    logger.info(
        "[email_renderer] rendered passively | recipient=%s subject='%s' html_len=%d text_len=%d",
        recipient, subject, len(html_body), len(text_body),
    )

    return RenderedEmailPayload(
        recipient=recipient,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        approval_status="draft_only",  # Sender authorization gate sets this to 'approved'
        metadata={
            "disclaimers_count": len(clean_disclaimers),
            "company_name": company_name,
            "semantically_passive_verified": True,
        },
    )
