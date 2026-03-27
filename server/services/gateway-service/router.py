"""
Enterprise-Level API Gateway Router
Handles routing, load balancing, circuit breaking, and request forwarding
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import Response
import httpx
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.logger import get_logger
from shared.cache import get_redis_client
from shared.config import get_config

logger = get_logger(__name__)
config = get_config()

# ── Service Registry ──────────────────────────────────────────────────────────
SERVICE_REGISTRY = {
    "auth-service": {
        "url": config.AUTH_SERVICE_URL or "http://localhost:8001",
        "prefix": "/auth",
        "timeout": 10.0,
        "retry": 2,
    },
    "user-service": {
        "url": config.USER_SERVICE_URL or "http://localhost:8002",
        "prefix": "/user-service",
        "timeout": 10.0,
        "retry": 2,
    },
    "business-service": {
        "url": config.BUSINESS_SERVICE_URL or "http://localhost:8003",
        "prefix": "/business-service",
        "timeout": 10.0,
        "retry": 2,
    },
    "email-service": {
        "url": config.EMAIL_SERVICE_URL or "http://localhost:8004",
        "prefix": "/email-service",
        "timeout": 15.0,
        "retry": 1,
    },
    "inbox-service": {
        "url": config.INBOX_SERVICE_URL or "http://localhost:8005",
        "prefix": "/inbox-service",
        "timeout": 10.0,
        "retry": 2,
    },
    "campaign-service": {
        "url": config.CAMPAIGN_SERVICE_URL or "http://localhost:8006",
        "prefix": "/campaign-service",
        "timeout": 10.0,
        "retry": 2,
    },
    "leads-service": {
        "url": config.LEADS_SERVICE_URL or "http://localhost:8007",
        "prefix": "/leads-service",
        "timeout": 10.0,
        "retry": 2,
    },
    "analytics-service": {
        "url": config.ANALYTICS_SERVICE_URL or "http://localhost:8008",
        "prefix": "/analytics-service",
        "timeout": 15.0,
        "retry": 1,
    },
    "automation-service": {
        "url": config.AUTOMATION_SERVICE_URL or "http://localhost:8009",
        "prefix": "/automation-service",
        "timeout": 10.0,
        "retry": 2,
    },
    "research-service": {
        "url": config.RESEARCH_SERVICE_URL or "http://localhost:8010",
        "prefix": "/research-service",
        "timeout": 20.0,
        "retry": 1,
    },
    "notification-service": {
        "url": config.NOTIFICATION_SERVICE_URL or "http://localhost:8011",
        "prefix": "/notification-service",
        "timeout": 10.0,
        "retry": 2,
    },
}

# ── HTTP Client Pool ──────────────────────────────────────────────────────────
_http_client: Optional[httpx.AsyncClient] = None

def get_http_client() -> httpx.AsyncClient:
    """Get or create HTTP client with connection pooling"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            follow_redirects=False,
        )
    return _http_client

async def close_http_client():
    """Close HTTP client"""
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None

# ── Circuit Breaker ───────────────────────────────────────────────────────────
class CircuitBreaker:
    """Circuit breaker pattern for service resilience"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures: Dict[str, int] = {}
        self.last_failure_time: Dict[str, datetime] = {}
        self.open_circuits: Dict[str, bool] = {}
    
    async def is_open(self, service_name: str) -> bool:
        """Check if circuit is open for a service"""
        if service_name not in self.open_circuits:
            return False
        
        if not self.open_circuits[service_name]:
            return False
        
        # Check if timeout has passed
        if service_name in self.last_failure_time:
            if datetime.utcnow() - self.last_failure_time[service_name] > timedelta(seconds=self.timeout):
                # Reset circuit
                self.open_circuits[service_name] = False
                self.failures[service_name] = 0
                logger.info(f"Circuit breaker reset for {service_name}")
                return False
        
        return True
    
    async def record_success(self, service_name: str):
        """Record successful request"""
        if service_name in self.failures:
            self.failures[service_name] = 0
        if service_name in self.open_circuits:
            self.open_circuits[service_name] = False
    
    async def record_failure(self, service_name: str):
        """Record failed request"""
        self.failures[service_name] = self.failures.get(service_name, 0) + 1
        self.last_failure_time[service_name] = datetime.utcnow()
        
        if self.failures[service_name] >= self.failure_threshold:
            self.open_circuits[service_name] = True
            logger.error(f"Circuit breaker opened for {service_name} after {self.failures[service_name]} failures")

circuit_breaker = CircuitBreaker()

# ── Rate Limiting ─────────────────────────────────────────────────────────────
async def check_rate_limit(client_ip: str, endpoint: str) -> bool:
    """
    Check if request is within rate limit
    Returns True if allowed, False if rate limited
    """
    redis = get_redis_client()
    key = f"rate_limit:{client_ip}:{endpoint}"
    
    try:
        # Get current count
        count = await redis.get(key)
        
        if count is None:
            # First request
            await redis.setex(key, 60, 1)
            return True
        
        count = int(count)
        
        # Check if over limit (60 requests per minute per endpoint)
        if count >= 60:
            return False
        
        # Increment counter
        await redis.incr(key)
        return True
    
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        # Fail open - allow request if Redis is down
        return True

# ── Service Discovery ─────────────────────────────────────────────────────────
def discover_service(path: str) -> Optional[Dict]:
    """
    Discover which service should handle the request based on path
    Returns service config or None
    """
    for service_name, service_config in SERVICE_REGISTRY.items():
        if path.startswith(service_config["prefix"]):
            return {
                "name": service_name,
                "url": service_config["url"],
                "prefix": service_config["prefix"],
                "timeout": service_config["timeout"],
                "retry": service_config["retry"],
            }
    return None

# ── Request Forwarding ────────────────────────────────────────────────────────
async def forward_request(
    request: Request,
    service_config: Dict,
    attempt: int = 0
) -> Response:
    """
    Forward request to target service with retry logic
    """
    service_name = service_config["name"]
    service_url = service_config["url"]
    service_prefix = service_config["prefix"]
    max_retries = service_config["retry"]
    timeout = service_config["timeout"]
    
    # Check circuit breaker
    if await circuit_breaker.is_open(service_name):
        logger.error(f"Circuit breaker open for {service_name}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service {service_name} is temporarily unavailable"
        )
    
    # Build target URL
    path = request.url.path
    
    # For auth-service, keep the full path (it has /auth prefix in routes)
    # For other services, strip the service prefix
    if service_name == "auth-service":
        target_url = f"{service_url}{path}"
    else:
        # Remove service prefix from path
        target_path = path[len(service_prefix):] if path.startswith(service_prefix) else path
        target_url = f"{service_url}{target_path}"
    
    # Add query parameters
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"
    
    # Prepare headers (exclude host header)
    headers = dict(request.headers)
    headers.pop("host", None)
    
    # Add gateway headers
    headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"
    headers["X-Forwarded-Proto"] = request.url.scheme
    headers["X-Gateway-Request-ID"] = request.headers.get("X-Request-ID", "unknown")
    
    # Get request body
    body = await request.body()
    
    client = get_http_client()
    
    try:
        # Forward request (removed verbose logging)
        response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            timeout=timeout,
        )
        
        # Record success
        await circuit_breaker.record_success(service_name)
        
        # Return response
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
        )
    
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
        logger.error(f"Request to {service_name} failed (attempt {attempt + 1}): {e}")
        
        # Record failure
        await circuit_breaker.record_failure(service_name)
        
        # Retry if attempts remaining
        if attempt < max_retries:
            logger.info(f"Retrying request to {service_name} (attempt {attempt + 2})")
            await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
            return await forward_request(request, service_config, attempt + 1)
        
        # Max retries exceeded
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service {service_name} is unavailable"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error forwarding to {service_name}: {e}", exc_info=True)
        await circuit_breaker.record_failure(service_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gateway error"
        )

# ── Main Router Handler ───────────────────────────────────────────────────────
async def route_request(request: Request) -> Response:
    """
    Main routing handler
    1. Rate limiting
    2. Service discovery
    3. Request forwarding
    """
    path = request.url.path
    
    # Skip health check and root
    if path in ["/health", "/"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not await check_rate_limit(client_ip, path):
        logger.warning(f"Rate limit exceeded for {client_ip} on {path}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    
    # Service discovery
    service_config = discover_service(path)
    if not service_config:
        logger.warning(f"No service found for path: {path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    # Forward request
    return await forward_request(request, service_config)
