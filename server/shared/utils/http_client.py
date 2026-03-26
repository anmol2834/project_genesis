"""
HTTP Client for Inter-Service Communication
Async HTTP client using httpx
"""

import httpx
from typing import Optional, Dict, Any
import logging

from shared.config import get_config
from shared.logger import get_logger

logger = get_logger(__name__)

# Global HTTP client instance
_http_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    """
    Get or create async HTTP client
    """
    global _http_client
    
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
            ),
            follow_redirects=True,
        )
        
        logger.info("HTTP client created")
    
    return _http_client


async def close_http_client():
    """
    Close HTTP client
    Call this on application shutdown
    """
    global _http_client
    
    if _http_client:
        await _http_client.aclose()
        _http_client = None
        logger.info("HTTP client closed")


class ServiceClient:
    """
    Base class for service-to-service communication
    """
    
    def __init__(self, service_url: str):
        """
        Initialize service client
        
        Args:
            service_url: Base URL of the service
        """
        self.service_url = service_url.rstrip('/')
        self.client = get_http_client()
    
    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make GET request to service
        """
        url = f"{self.service_url}/{endpoint.lstrip('/')}"
        
        try:
            response = await self.client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP GET error to {url}: {e}")
            raise
    
    async def post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make POST request to service
        """
        url = f"{self.service_url}/{endpoint.lstrip('/')}"
        
        try:
            response = await self.client.post(url, json=json_data, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP POST error to {url}: {e}")
            raise
    
    async def put(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make PUT request to service
        """
        url = f"{self.service_url}/{endpoint.lstrip('/')}"
        
        try:
            response = await self.client.put(url, json=json_data, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP PUT error to {url}: {e}")
            raise
    
    async def delete(
        self,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make DELETE request to service
        """
        url = f"{self.service_url}/{endpoint.lstrip('/')}"
        
        try:
            response = await self.client.delete(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP DELETE error to {url}: {e}")
            raise


def get_service_client(service_name: str) -> ServiceClient:
    """
    Get service client by service name
    
    Args:
        service_name: Name of the service (e.g., 'auth', 'email', 'inbox')
    
    Returns:
        ServiceClient instance
    """
    config = get_config()
    
    service_urls = {
        'gateway': config.GATEWAY_SERVICE_URL,
        'auth': config.AUTH_SERVICE_URL,
        'user': config.USER_SERVICE_URL,
        'business': config.BUSINESS_SERVICE_URL,
        'email': config.EMAIL_SERVICE_URL,
        'inbox': config.INBOX_SERVICE_URL,
        'campaign': config.CAMPAIGN_SERVICE_URL,
        'leads': config.LEADS_SERVICE_URL,
        'analytics': config.ANALYTICS_SERVICE_URL,
        'automation': config.AUTOMATION_SERVICE_URL,
        'research': config.RESEARCH_SERVICE_URL,
        'notification': config.NOTIFICATION_SERVICE_URL,
    }
    
    service_url = service_urls.get(service_name.lower())
    if not service_url:
        raise ValueError(f"Unknown service: {service_name}")
    
    return ServiceClient(service_url)
