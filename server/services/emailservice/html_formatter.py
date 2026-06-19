"""
emailservice — HTML Email Formatter
=====================================
Converts AI-generated plain text responses into a beautifully structured,
branded HTML email that is fully readable on all modern email clients.

Design principles:
  • Table-based layout — maximum compatibility (Gmail, Outlook, Yahoo, Apple Mail)
  • Inline CSS only — no external stylesheets, no <style> blocks stripped by clients
  • Bullet points for lists — dash/asterisk/numbered lines → <ul>/<ol> list items
  • Paragraph detection — blank-line separated paragraphs → <p> tags
  • Greeting line detection — first line treated as personal salutation
  • Signature block — professional, consistent closing for every email
  • No external resources — no images, no web fonts (avoids spam filters)
  • UTF-8 safe — handles all languages including Hindi, Arabic, CJK
"""
from __future__ import annotations

import html
import re
import textwrap
from typing import List, Tuple


# ── Colour palette & typography ───────────────────────────────────────────────
_PRIMARY       = "#1a1a2e"   # dark navy  — header background
_ACCENT        = "#4f46e5"   # indigo     — divider, bullet colour
_BODY_BG       = "#f8f9fa"   # light grey — outer wrapper
_CARD_BG       = "#ffffff"   # white      — email card
_TEXT_PRIMARY  = "#1f2937"   # near-black — body text
_TEXT_MUTED    = "#6b7280"   # grey       — secondary text / footer
_BORDER        = "#e5e7eb"   # light grey — card border
_BULLET_BG     = "#eef2ff"   # pale indigo — bullet row background
_FONT          = (
    "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
    "Helvetica,Arial,sans-serif"
)


# ── Public API ────────────────────────────────────────────────────────────────

def format_email_html(
    plain_text: str,
    from_name: str = "ProxiPilot Support",
    subject: str = "",
    recipient_name: str = "",
) -> str:
    """
    Convert a plain-text AI response into a fully formatted HTML email.

    Args:
        plain_text:     Raw text from the LLM / fallback chain.
        from_name:      Display name shown in the email header.
        subject:        Email subject (used as header title if available).
        recipient_name: Customer's first name for the greeting (optional).

    Returns:
        A complete HTML string, ready to drop into MIMEText("html").
    """
    if not plain_text or not plain_text.strip():
        plain_text = "Thank you for contacting us. We will get back to you shortly."

    clean_text  = _sanitize(plain_text)
    sections    = _parse_sections(clean_text)
    body_html   = _render_sections(sections)
    header_title = subject or "Your Message"

    return _wrap_in_template(
        body_html=body_html,
        header_title=header_title,
        from_name=from_name,
    )


# ── Text parsing ──────────────────────────────────────────────────────────────

_BULLET_PATTERNS = re.compile(
    r"^(\s*(?:[-•*\u2022\u2023\u25e6]|\d+[.)]\s|\([a-zA-Z\d]+\)\s))\s*(.+)$"
)
_NUMBERED_PATTERN = re.compile(r"^(\s*\d+[.)]\s*)(.+)$")
_HEADER_PATTERN   = re.compile(r"^#{1,3}\s+(.+)$")
_SEPARATOR_PATTERN = re.compile(r"^[-=_*]{3,}\s*$")


class _Section:
    """Parsed content block."""
    __slots__ = ("kind", "content")

    def __init__(self, kind: str, content):
        self.kind    = kind    # "greeting"|"para"|"bullet_list"|"num_list"|"header"|"divider"
        self.content = content # str for para/greeting/header; List[str] for lists


def _sanitize(text: str) -> str:
    """Normalise line endings and strip leading/trailing whitespace."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse more than 3 consecutive blank lines into 2
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def _parse_sections(text: str) -> List[_Section]:
    """
    Parse plain text into semantic sections:
      - Greeting line (Dear X / Hi X / Hello X)
      - Markdown-style headers
      - Bullet / numbered lists
      - Paragraphs (blank-line separated)
      - Horizontal rules
    """
    sections: List[_Section] = []
    paragraphs = re.split(r"\n{2,}", text)

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        lines = [l.rstrip() for l in para.splitlines()]

        # ── Horizontal rule ──
        if len(lines) == 1 and _SEPARATOR_PATTERN.match(lines[0]):
            sections.append(_Section("divider", ""))
            continue

        # ── Markdown header ──
        if len(lines) == 1 and _HEADER_PATTERN.match(lines[0]):
            m = _HEADER_PATTERN.match(lines[0])
            sections.append(_Section("header", m.group(1).strip()))
            continue

        # ── List detection — check if majority of lines are bullet/numbered ──
        bullet_lines, num_lines, plain_lines = [], [], []
        for line in lines:
            bm = _BULLET_PATTERNS.match(line)
            nm = _NUMBERED_PATTERN.match(line)
            if bm and not nm:
                bullet_lines.append(bm.group(2).strip())
            elif nm:
                num_lines.append(nm.group(2).strip())
            else:
                plain_lines.append(line)

        total = len(lines)
        if total > 0:
            bullet_ratio = len(bullet_lines) / total
            num_ratio    = len(num_lines) / total

            if bullet_ratio >= 0.6 and len(bullet_lines) >= 2:
                # Mix: any non-bullet lines become a preceding paragraph
                if plain_lines:
                    sections.append(_Section("para", " ".join(plain_lines)))
                sections.append(_Section("bullet_list", bullet_lines))
                continue

            if num_ratio >= 0.6 and len(num_lines) >= 2:
                if plain_lines:
                    sections.append(_Section("para", " ".join(plain_lines)))
                sections.append(_Section("num_list", num_lines))
                continue

        # ── Greeting detection ──
        joined = " ".join(lines)
        if _is_greeting_line(lines[0]) and len(lines) <= 3:
            sections.append(_Section("greeting", joined))
            continue

        # ── Regular paragraph ──
        sections.append(_Section("para", joined))

    return sections


def _is_greeting_line(line: str) -> bool:
    """Returns True if the line looks like an email salutation."""
    lower = line.lower().strip()
    greetings = (
        "dear ", "hi ", "hello ", "good morning", "good afternoon",
        "good evening", "greetings", "hi there", "hello there",
        "namaste", "respected",
    )
    return any(lower.startswith(g) for g in greetings)


# ── HTML rendering ────────────────────────────────────────────────────────────

def _render_sections(sections: List[_Section]) -> str:
    parts: List[str] = []

    for sec in sections:
        if sec.kind == "greeting":
            parts.append(_render_greeting(sec.content))

        elif sec.kind == "header":
            parts.append(_render_section_header(sec.content))

        elif sec.kind == "divider":
            parts.append(_render_divider())

        elif sec.kind == "bullet_list":
            parts.append(_render_bullet_list(sec.content))

        elif sec.kind == "num_list":
            parts.append(_render_numbered_list(sec.content))

        elif sec.kind == "para":
            # Check if this paragraph is actually a closing/signature line
            if _is_closing_line(sec.content):
                parts.append(_render_closing_para(sec.content))
            else:
                parts.append(_render_paragraph(sec.content))

    return "\n".join(parts)


def _esc(text: str) -> str:
    """HTML-escape and convert newlines to <br>."""
    return html.escape(text).replace("\n", "<br>")


def _render_greeting(text: str) -> str:
    return (
        f'<p style="margin:0 0 20px 0;font-size:16px;font-weight:600;'
        f'color:{_TEXT_PRIMARY};font-family:{_FONT};">'
        f"{_esc(text)}</p>"
    )


def _render_section_header(text: str) -> str:
    return (
        f'<p style="margin:24px 0 10px 0;font-size:15px;font-weight:700;'
        f'color:{_ACCENT};font-family:{_FONT};text-transform:uppercase;'
        f'letter-spacing:0.5px;">'
        f"{_esc(text)}</p>"
        f'<div style="width:40px;height:2px;background:{_ACCENT};'
        f'margin:0 0 16px 0;border-radius:1px;"></div>'
    )


def _render_divider() -> str:
    return (
        f'<div style="height:1px;background:{_BORDER};'
        f'margin:20px 0;"></div>'
    )


def _render_paragraph(text: str) -> str:
    return (
        f'<p style="margin:0 0 16px 0;font-size:15px;line-height:1.7;'
        f'color:{_TEXT_PRIMARY};font-family:{_FONT};">'
        f"{_esc(text)}</p>"
    )


def _render_closing_para(text: str) -> str:
    return (
        f'<p style="margin:20px 0 0 0;font-size:14px;line-height:1.6;'
        f'color:{_TEXT_MUTED};font-family:{_FONT};font-style:italic;">'
        f"{_esc(text)}</p>"
    )


def _render_bullet_list(items: List[str]) -> str:
    rows = []
    for item in items:
        rows.append(
            f'<tr>'
            f'<td style="width:28px;vertical-align:top;padding:5px 8px 5px 0;">'
            f'<span style="display:inline-block;width:8px;height:8px;'
            f'background:{_ACCENT};border-radius:50%;margin-top:5px;"></span>'
            f'</td>'
            f'<td style="vertical-align:top;padding:4px 0;">'
            f'<span style="font-size:15px;line-height:1.6;color:{_TEXT_PRIMARY};'
            f'font-family:{_FONT};">{_esc(item)}</span>'
            f'</td>'
            f'</tr>'
        )
    inner = "\n".join(rows)
    return (
        f'<table role="presentation" border="0" cellpadding="0" cellspacing="0" '
        f'style="width:100%;margin:0 0 18px 0;background:{_BULLET_BG};'
        f'border-radius:8px;border-left:3px solid {_ACCENT};padding:10px 16px;">'
        f'<tbody>{inner}</tbody>'
        f'</table>'
    )


def _render_numbered_list(items: List[str]) -> str:
    rows = []
    for i, item in enumerate(items, 1):
        rows.append(
            f'<tr>'
            f'<td style="width:32px;vertical-align:top;padding:5px 10px 5px 0;">'
            f'<span style="display:inline-block;width:24px;height:24px;'
            f'background:{_ACCENT};border-radius:50%;text-align:center;'
            f'line-height:24px;font-size:12px;font-weight:700;color:#fff;'
            f'font-family:{_FONT};">{i}</span>'
            f'</td>'
            f'<td style="vertical-align:top;padding:4px 0;">'
            f'<span style="font-size:15px;line-height:1.6;color:{_TEXT_PRIMARY};'
            f'font-family:{_FONT};">{_esc(item)}</span>'
            f'</td>'
            f'</tr>'
        )
    inner = "\n".join(rows)
    return (
        f'<table role="presentation" border="0" cellpadding="0" cellspacing="0" '
        f'style="width:100%;margin:0 0 18px 0;">'
        f'<tbody>{inner}</tbody>'
        f'</table>'
    )


def _is_closing_line(text: str) -> bool:
    """Detect common email closing phrases."""
    lower = text.lower().strip()
    closings = (
        "best regards", "warm regards", "kind regards", "thanks and regards",
        "sincerely", "thank you", "thanks,", "best,", "regards,",
        "looking forward", "please let us know", "feel free to",
        "do not hesitate", "don't hesitate", "have a great", "have a wonderful",
        "we hope", "we appreciate", "we value", "we apologize",
        "if you have any further", "for any further",
    )
    return any(lower.startswith(c) for c in closings)


# ── Email template wrapper ─────────────────────────────────────────────────────

def _wrap_in_template(
    body_html: str,
    header_title: str,
    from_name: str,
) -> str:
    """
    Wrap rendered body in a full HTML email template.
    Table-based, inline CSS, works in all major email clients.
    """
    safe_title   = html.escape(header_title)
    safe_name    = html.escape(from_name)

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>{safe_title}</title>
</head>
<body style="margin:0;padding:0;background-color:{_BODY_BG};
  font-family:{_FONT};-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">

  <!-- Outer wrapper -->
  <table role="presentation" border="0" cellpadding="0" cellspacing="0"
    style="width:100%;background-color:{_BODY_BG};padding:32px 16px;">
    <tr>
      <td align="center">

        <!-- Email card (max 620px) -->
        <table role="presentation" border="0" cellpadding="0" cellspacing="0"
          style="width:100%;max-width:620px;background:{_CARD_BG};
          border-radius:12px;overflow:hidden;
          box-shadow:0 2px 12px rgba(0,0,0,0.08);
          border:1px solid {_BORDER};">

          <!-- Header -->
          <tr>
            <td style="background:{_PRIMARY};padding:28px 32px;">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0"
                style="width:100%;">
                <tr>
                  <td>
                    <p style="margin:0;font-size:13px;font-weight:600;
                      color:#a5b4fc;font-family:{_FONT};
                      text-transform:uppercase;letter-spacing:1px;">
                      {safe_name}
                    </p>
                    <h1 style="margin:6px 0 0 0;font-size:20px;font-weight:700;
                      color:#ffffff;font-family:{_FONT};line-height:1.3;">
                      {safe_title}
                    </h1>
                  </td>
                  <td style="text-align:right;vertical-align:middle;">
                    <!-- Brand accent dot -->
                    <div style="width:40px;height:40px;background:{_ACCENT};
                      border-radius:50%;display:inline-block;
                      opacity:0.9;"></div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Accent line -->
          <tr>
            <td style="height:3px;background:linear-gradient(
              90deg,{_ACCENT} 0%,#818cf8 50%,#c7d2fe 100%);"></td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px 32px 24px 32px;">
              {body_html}
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:0 32px;">
              <div style="height:1px;background:{_BORDER};"></div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 32px 28px 32px;">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0"
                style="width:100%;">
                <tr>
                  <td>
                    <p style="margin:0;font-size:13px;color:{_TEXT_MUTED};
                      font-family:{_FONT};line-height:1.5;">
                      This message was sent by <strong>{safe_name}</strong>.<br>
                      If you have further questions, simply reply to this email.
                    </p>
                  </td>
                  <td style="text-align:right;vertical-align:top;">
                    <p style="margin:0;font-size:11px;color:{_TEXT_MUTED};
                      font-family:{_FONT};">
                      Powered by<br>
                      <strong style="color:{_ACCENT};">proxipilot.com</strong>
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
        <!-- /Email card -->

      </td>
    </tr>
  </table>
  <!-- /Outer wrapper -->

</body>
</html>"""

