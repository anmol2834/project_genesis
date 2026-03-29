"""
SMTP/IMAP Receiver
Polls IMAP servers for new emails (no push notifications available).
"""

from typing import Dict, Any, List
import imaplib
import email
from email.header import decode_header
from datetime import datetime

from shared.logger import get_logger
from utils.encryption import decrypt_token
from provider.filters.email_filter import EmailFilter
from provider.deduplicator.event_deduplicator import EventDeduplicator
from normalizer.normalizer import EmailNormalizer
from email_queue.producer.event_producer import EventProducer

logger = get_logger(__name__)


class SMTPReceiver:
    """Polls IMAP servers for new emails."""

    def __init__(self):
        self.email_filter = EmailFilter()
        self.deduplicator = EventDeduplicator()
        self.normalizer = EmailNormalizer()
        self.queue_producer = EventProducer()

    async def poll_account(self, account) -> List[Dict[str, Any]]:
        """
        Poll IMAP server for new emails.
        Returns list of new email events.
        """
        logger.info(f"Polling IMAP for {account.email_address}")

        if not account.imap_host or not account.imap_port:
            logger.warning(f"IMAP not configured for {account.email_address}")
            return []

        try:
            # Decrypt credentials
            password = decrypt_token(account.smtp_password)

            # Connect to IMAP
            if account.smtp_use_tls:
                imap = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
            else:
                imap = imaplib.IMAP4(account.imap_host, account.imap_port)

            # Login
            imap.login(account.smtp_username or account.email_address, password)

            # Select INBOX
            imap.select("INBOX")

            # Search for unseen emails
            status, messages = imap.search(None, "UNSEEN")

            if status != "OK":
                logger.warning(f"IMAP search failed for {account.email_address}")
                imap.logout()
                return []

            message_ids = messages[0].split()
            
            if not message_ids:
                logger.debug(f"No new emails for {account.email_address}")
                imap.logout()
                return []

            logger.info(f"Found {len(message_ids)} new emails for {account.email_address}")

            events = []

            # Fetch each message
            for msg_id in message_ids[:50]:  # Limit to 50 per poll
                try:
                    event = await self._fetch_message(imap, msg_id, account)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.error(f"Failed to fetch message {msg_id}: {e}")

            imap.logout()
            return events

        except Exception as e:
            logger.error(f"IMAP polling failed for {account.email_address}: {e}")
            return []

    async def _fetch_message(
        self,
        imap: imaplib.IMAP4,
        msg_id: bytes,
        account
    ) -> Dict[str, Any]:
        """Fetch and parse a single message."""
        status, msg_data = imap.fetch(msg_id, "(RFC822)")

        if status != "OK":
            return None

        # Parse email
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # Extract headers
        message_id = msg.get("Message-ID", "").strip("<>")
        subject = self._decode_header(msg.get("Subject", ""))
        from_email = self._decode_header(msg.get("From", ""))
        to_email = self._decode_header(msg.get("To", ""))
        date_str = msg.get("Date", "")

        # Deduplicate
        dedup_key = f"smtp_{account.id}_{message_id}"
        if await self.deduplicator.is_duplicate(dedup_key):
            logger.debug(f"Duplicate SMTP message: {message_id}")
            return None

        # Pre-filter
        if await self.email_filter.should_filter(subject, from_email):
            logger.debug(f"Filtered SMTP message: {subject} from {from_email}")
            await self.deduplicator.mark_processed(dedup_key)
            return None

        # Mark as processed
        await self.deduplicator.mark_processed(dedup_key)

        logger.info(f"SMTP message received: {subject} from {from_email}")

        raw_event = {
            "status": "received",
            "provider": "smtp",
            "account_id": str(account.id),
            "message_id": message_id,
            "subject": subject,
            "from": from_email,
            "to": to_email,
            "date": date_str,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Normalize event
        normalized_event = await self.normalizer.normalize("smtp", raw_event)
        
        if normalized_event:
            # Push to queue
            queued = await self.queue_producer.produce(normalized_event)
            
            return {
                "status": "queued" if queued else "normalized",
                "message_id": normalized_event.message_id,
                "user_id": normalized_event.user_id,
                "queued": queued
            }
        else:
            return raw_event

    def _decode_header(self, header: str) -> str:
        """Decode email header."""
        if not header:
            return ""
        
        decoded_parts = decode_header(header)
        decoded_str = ""
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_str += part.decode(encoding or "utf-8", errors="ignore")
            else:
                decoded_str += part
        
        return decoded_str
