"""
JSON Conversation Manager
Handles 24-hour sliding window message storage with enterprise-grade logic.

Message object schema (stored in last_24h_messages JSONB):
{
    "from":            "sender@example.com",
    "to":              ["recipient@example.com"],
    "content":         "Clean message body only — no quoted replies",
    "timestamp":       "2026-03-29T13:31:54",
    "direction":       "incoming" | "outgoing",
    "has_attachments": false
}

Fields intentionally excluded:
  - message_id  → stored separately as EmailConversation.message_id
  - subject     → stored separately as EmailConversation.subject
  - cc          → not needed for AI context
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re
from shared.logger import get_logger

logger = get_logger(__name__)


class JSONConversationManager:
    """Manages conversation message history with 24-hour sliding window."""

    @staticmethod
    def update_messages(
        existing_messages: List[Dict[str, Any]],
        new_message: Dict[str, Any],
        message_id: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Update message list with new message and apply 24h window.

        Args:
            existing_messages: Current stored message list
            new_message:       Clean message object (no message_id/subject/cc)
            message_id:        Used only for dedup — NOT stored in the object
        """
        try:
            if not isinstance(existing_messages, list):
                existing_messages = []

            if not JSONConversationManager._validate_message(new_message):
                logger.error(f"Invalid message structure: {new_message}")
                return existing_messages

            if JSONConversationManager._is_duplicate(existing_messages, new_message):
                logger.debug("Duplicate message, skipping")
                return existing_messages

            messages = existing_messages.copy()
            messages.append(new_message)
            messages = JSONConversationManager._sort_by_timestamp(messages)
            messages = JSONConversationManager._apply_24h_filter(messages)

            logger.debug(f"Messages: {len(existing_messages)} → {len(messages)}")
            return messages

        except Exception as e:
            logger.error(f"Failed to update messages: {e}", exc_info=True)
            return existing_messages

    @staticmethod
    def create_message_object(
        from_email: str,
        to_emails: List[str],
        content: str,
        timestamp: datetime,
        direction: str,
        has_attachments: bool = False,
        # Accepted for call-site compatibility but NOT stored
        message_id: str = "",
        subject: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a clean message object for JSONB storage.

        Stored:   from, to, content (cleaned), timestamp, direction, has_attachments
        Excluded: message_id, subject, cc
        """
        return {
            "from":            from_email,
            "to":              to_emails or [],
            "content":         JSONConversationManager._strip_quoted_reply(content),
            "timestamp":       timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            "direction":       direction,
            "has_attachments": has_attachments,
        }

    # ── Content cleaning ──────────────────────────────────────────────────────

    @staticmethod
    def _strip_quoted_reply(content: str) -> str:
        """
        Remove Gmail/Outlook quoted reply headers from email content.

        Only strips the specific quote header format:
          "On <weekday>, <month> <day>, <year> at/,  <time> <Name> <email> wrote:"

        Does NOT strip messages that happen to contain the word "on"
        (e.g. "let's meet on sunday" is kept intact).

        Searches from the LAST match so earlier "on" words in the real
        message body are never accidentally truncated.
        """
        if not content:
            return content

        # Pattern requires a DATE immediately after "On <weekday>" — this is the
        # discriminator. Real quote headers: "On Sun, Mar 29..." or "On Mon, 31 Mar..."
        # The weekday is ALWAYS followed by a comma in Gmail/Outlook headers.
        # "on sunday" has no comma after "Sun" so it won't match.
        quote_header = re.compile(
            r'\bOn\s+'
            r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),'   # weekday + COMMA (required)
            r'[^<]{5,200}'
            r'<[^>]+>'
            r'\s+wrote\s*:',
            re.IGNORECASE
        )

        last_match = None
        for m in quote_header.finditer(content):
            last_match = m

        if last_match:
            before = content[:last_match.start()].strip()
            # Strip any trailing "> " quoted lines after the cut point
            before = re.sub(r'\s*>.*$', '', before, flags=re.DOTALL).strip()
            return before

        # Multi-line fallback (Outlook "From:/Sent:/To:" block and "> " lines)
        lines = content.splitlines()
        clean_lines = []
        for i, line in enumerate(lines):
            stripped = line.strip()

            if re.match(
                r'^On\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*.{5,200}wrote\s*:',
                stripped, re.IGNORECASE
            ):
                break

            if re.match(r'^From:\s+.+', stripped, re.IGNORECASE):
                upcoming = [l.strip() for l in lines[i:i + 5] if l.strip()]
                if any(re.match(r'^(Sent|To|Subject):\s+', u, re.IGNORECASE) for u in upcoming):
                    break

            if stripped.startswith('>'):
                continue

            clean_lines.append(line)

        result = '\n'.join(clean_lines).strip()
        return re.sub(r'\n{3,}', '\n\n', result)

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_message(message: Dict[str, Any]) -> bool:
        for field in ["from", "to", "content", "timestamp", "direction"]:
            if field not in message:
                logger.error(f"Message missing required field: {field}")
                return False
        if message.get("direction") not in ["incoming", "outgoing"]:
            logger.error(f"Invalid direction: {message.get('direction')}")
            return False
        return True

    @staticmethod
    def _is_duplicate(messages: List[Dict[str, Any]], new_message: Dict[str, Any]) -> bool:
        """Dedup by timestamp + from (message_id no longer stored in object)."""
        new_ts   = new_message.get("timestamp")
        new_from = new_message.get("from")
        return any(
            m.get("timestamp") == new_ts and m.get("from") == new_from
            for m in messages
        )

    # ── Sorting ───────────────────────────────────────────────────────────────

    @staticmethod
    def _sort_by_timestamp(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        from datetime import timezone

        def get_ts(msg):
            ts = msg.get("timestamp")
            if isinstance(ts, datetime):
                return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            if isinstance(ts, str):
                try:
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
            return datetime.min.replace(tzinfo=timezone.utc)

        try:
            return sorted(messages, key=get_ts)
        except Exception as e:
            logger.error(f"Failed to sort messages: {e}")
            return messages

    # ── 24h filter ────────────────────────────────────────────────────────────

    @staticmethod
    def _apply_24h_filter(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            from datetime import timezone
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            filtered = []

            for msg in messages:
                ts = msg.get("timestamp")
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except ValueError:
                        try:
                            ts = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
                        except ValueError:
                            continue
                elif isinstance(ts, datetime):
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                else:
                    continue

                if ts >= cutoff:
                    filtered.append(msg)

            return filtered

        except Exception as e:
            logger.error(f"Failed to apply 24h filter: {e}", exc_info=True)
            return messages

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def get_message_count(messages: List[Dict[str, Any]]) -> int:
        return len(messages) if isinstance(messages, list) else 0

    @staticmethod
    def get_latest_message(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not messages or not isinstance(messages, list):
            return None
        return messages[-1]

    @staticmethod
    def extract_conversation_participants(
        messages: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        from_emails, to_emails = set(), set()
        for msg in messages:
            if "from" in msg:
                from_emails.add(msg["from"])
            if "to" in msg and isinstance(msg["to"], list):
                to_emails.update(msg["to"])
        return {"from": list(from_emails), "to": list(to_emails)}
