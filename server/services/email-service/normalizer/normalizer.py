"""
Normalizer Engine
Converts adapted data into universal NormalizedEmailEvent format.
"""

from typing import Dict, Any, Optional
import re

from shared.logger import get_logger
from shared.database import get_db_session
from models.email_account import EmailAccount
from sqlalchemy import select

from normalizer.event_schema import NormalizedEmailEvent, EmailProvider, EmailDirection
from normalizer.enrichers.user_mapper import UserMapper
from normalizer.enrichers.account_mapper import AccountMapper
from normalizer.enrichers.metadata_enricher import MetadataEnricher
from adapter.adapter_factory import AdapterFactory

logger = get_logger(__name__)


class EmailNormalizer:
    """
    Main normalizer engine.
    Orchestrates the entire normalization pipeline.
    """
    
    def __init__(self):
        self.user_mapper = UserMapper()
        self.account_mapper = AccountMapper()
        self.metadata_enricher = MetadataEnricher()
    
    async def normalize(
        self,
        provider: str,
        raw_payload: Dict[str, Any]
    ) -> Optional[NormalizedEmailEvent]:
        """
        Complete normalization pipeline.
        
        Flow:
        1. Adapt provider payload → structured format
        2. Validate required fields
        3. Clean content
        4. Enrich with user/account mapping
        5. Enrich with metadata
        6. Create NormalizedEmailEvent
        
        Args:
            provider: Provider name (gmail, outlook, smtp)
            raw_payload: Raw provider payload
            
        Returns:
            NormalizedEmailEvent or None if normalization fails
        """
        try:
            # Step 1: Adapt provider payload
            logger.info(f"Normalizing {provider} event for {raw_payload.get('email_address', '?')}")
            adapted_data = await AdapterFactory.parse_event(provider, raw_payload)

            if adapted_data is None:
                logger.info(f"Adapter returned None for {provider} — no new messages (normal)")
                return None

            logger.info(
                f"Adapter returned message: id={adapted_data.get('message_id')} "
                f"subject='{adapted_data.get('subject')}' "
                f"from={adapted_data.get('from_email')}"
            )

            # Step 2: Validate required fields
            self._validate_adapted_data(adapted_data)
            
            # Step 3: Resolve email account
            email_account_id, account_email = await self._resolve_account(
                provider,
                raw_payload,
                adapted_data
            )
            
            if not email_account_id:
                logger.error("Failed to resolve email account")
                return None
            
            # Step 4: Resolve user
            user_id = await self.user_mapper.get_user_id(email_account_id)
            if not user_id:
                logger.error(f"Failed to resolve user for account: {email_account_id}")
                return None
            
            # Step 5: Clean content
            cleaned_content = self._clean_content(adapted_data.get("content", ""))
            
            # Step 6: Enrich with metadata
            enriched_data = self.metadata_enricher.enrich(adapted_data, account_email)
            
            # Step 7: Create normalized event
            normalized_event = NormalizedEmailEvent(
                user_id=user_id,
                email_account_id=email_account_id,
                provider=EmailProvider(provider.lower()),
                message_id=enriched_data["message_id"],
                thread_id=enriched_data.get("thread_id"),
                subject=enriched_data["subject"],
                from_email=enriched_data["from_email"],
                to_emails=enriched_data.get("to_emails", []),
                cc_emails=enriched_data.get("cc_emails", []),
                bcc_emails=enriched_data.get("bcc_emails", []),
                content=cleaned_content,
                content_html=enriched_data.get("content_html"),
                timestamp=enriched_data["timestamp"],
                direction=EmailDirection(enriched_data["direction"]),
                has_attachments=enriched_data.get("has_attachments", False),
                attachment_count=self._count_attachments(enriched_data),
                provider_data=enriched_data.get("provider_data", {}),
                received_at=enriched_data["received_at"],
                normalized_at=enriched_data["normalized_at"]
            )
            
            logger.info(
                f"Successfully normalized {provider} event: "
                f"message_id={normalized_event.message_id}, "
                f"user_id={user_id}"
            )
            
            return normalized_event
            
        except Exception as e:
            # Only log as error for unexpected failures, not for known "no account" cases
            msg = str(e)
            if "not found" in msg.lower() or "no new messages" in msg.lower():
                logger.warning(f"Normalization skipped for {provider}: {msg}")
            else:
                logger.error(f"Normalization failed for {provider}: {e}", exc_info=True)
            return None
    
    async def _resolve_account(
        self,
        provider: str,
        raw_payload: Dict[str, Any],
        adapted_data: Dict[str, Any]
    ) -> tuple:
        """
        Resolve email_account_id and account_email.
        
        Returns:
            (email_account_id, account_email) or (None, None)
        """
        # Try different resolution strategies based on provider
        
        # Strategy 1: From raw payload (SMTP has account_id)
        if "account_id" in raw_payload:
            account_id = raw_payload["account_id"]
            account_email = await self._get_account_email(account_id)
            if account_email:
                return account_id, account_email
        
        # Strategy 2: From email_address in payload (Gmail)
        if "email_address" in raw_payload:
            email_address = raw_payload["email_address"]
            account_id = await self.account_mapper.get_account_id_by_email(email_address)
            if account_id:
                return account_id, email_address
        
        # Strategy 3: From subscription_id (Outlook)
        if "subscription_id" in raw_payload:
            subscription_id = raw_payload["subscription_id"]
            account_id = await self.account_mapper.get_account_id_by_subscription(subscription_id)
            if account_id:
                account_email = await self._get_account_email(account_id)
                if account_email:
                    return account_id, account_email
        
        # Strategy 4: From to_emails (if this is an outgoing email)
        # This is a fallback and less reliable
        
        logger.error(f"Could not resolve account for {provider} event")
        return None, None
    
    async def _get_account_email(self, account_id: str) -> Optional[str]:
        """Get email address for an account."""
        async with get_db_session() as session:
            result = await session.execute(
                select(EmailAccount.email_address).where(
                    EmailAccount.id == account_id
                )
            )
            return result.scalar_one_or_none()
    
    def _validate_adapted_data(self, data: Dict[str, Any]):
        """Validate that adapted data has required fields."""
        required = ["message_id", "subject", "from_email", "content"]
        missing = [f for f in required if f not in data or not data[f]]
        
        if missing:
            raise ValueError(f"Adapted data missing required fields: {', '.join(missing)}")
    
    def _clean_content(self, content: str) -> str:
        """
        Clean email content for AI processing.
        
        - Remove excessive whitespace
        - Remove tracking pixels
        - Normalize line breaks
        """
        if not content:
            return ""
        
        # Remove tracking pixels (1x1 images)
        content = re.sub(
            r'<img[^>]*(?:width|height)=["\']1["\'][^>]*>',
            '',
            content,
            flags=re.IGNORECASE
        )
        
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Normalize line breaks
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        
        # Trim
        content = content.strip()
        
        return content
    
    def _count_attachments(self, data: Dict[str, Any]) -> int:
        """Count attachments from provider data."""
        if not data.get("has_attachments"):
            return 0
        
        # Try to get count from provider_data
        provider_data = data.get("provider_data", {})
        
        # Gmail might have attachment info
        if "attachments" in provider_data:
            return len(provider_data["attachments"])
        
        # Default to 1 if has_attachments is True but no count
        return 1 if data.get("has_attachments") else 0
