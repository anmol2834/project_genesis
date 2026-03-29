"""
Adapter Factory
Provides the correct adapter based on provider type.
"""

from typing import Dict, Any
from adapter.base_adapter import BaseAdapter
from adapter.providers.gmail_adapter import GmailEventAdapter
from adapter.providers.outlook_adapter import OutlookEventAdapter
from adapter.providers.smtp_adapter import SMTPEventAdapter

from shared.logger import get_logger

logger = get_logger(__name__)


class AdapterFactory:
    """Factory for creating provider-specific adapters."""
    
    _adapters: Dict[str, BaseAdapter] = {
        "gmail": GmailEventAdapter(),
        "outlook": OutlookEventAdapter(),
        "smtp": SMTPEventAdapter()
    }
    
    @classmethod
    def get_adapter(cls, provider: str) -> BaseAdapter:
        """
        Get adapter for the specified provider.
        
        Args:
            provider: Provider name (gmail, outlook, smtp)
            
        Returns:
            Provider-specific adapter instance
            
        Raises:
            ValueError: If provider is not supported
        """
        provider_lower = provider.lower()
        
        adapter = cls._adapters.get(provider_lower)
        
        if not adapter:
            raise ValueError(f"Unsupported provider: {provider}")
        
        logger.debug(f"Retrieved adapter for provider: {provider}")
        return adapter
    
    @classmethod
    async def parse_event(cls, provider: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convenience method to get adapter and parse in one call.
        
        Args:
            provider: Provider name
            payload: Raw provider payload
            
        Returns:
            Parsed intermediate format
        """
        adapter = cls.get_adapter(provider)
        return await adapter.parse(payload)
