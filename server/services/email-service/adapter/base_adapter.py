"""
Base Adapter Interface
All provider adapters must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseAdapter(ABC):
    """
    Base adapter for converting provider-specific payloads
    into structured intermediate format.
    """
    
    @abstractmethod
    async def parse(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse provider-specific payload into structured format.
        
        Args:
            payload: Raw provider payload
            
        Returns:
            Structured intermediate format with keys:
                - message_id: str
                - thread_id: Optional[str]
                - subject: str
                - from_email: str
                - to_emails: List[str]
                - content: str
                - content_html: Optional[str]
                - timestamp: datetime
                - provider_data: Dict (provider-specific metadata)
        
        Raises:
            ValueError: If payload is invalid or missing required fields
        """
        raise NotImplementedError
    
    def _validate_required_fields(
        self,
        data: Dict[str, Any],
        required_fields: list
    ):
        """Validate that required fields are present."""
        missing = [f for f in required_fields if f not in data or not data[f]]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
