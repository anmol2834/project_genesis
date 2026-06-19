"""
Enterprise-Level API Gateway Router
Handles routing, load balancing, circuit breaking, and request forwarding
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import Response
from starlette.requests import ClientDisconnect
import httpx
import asyncio
import hashlib
import json
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
        "timeout": 30.0,
        "retry": 2,
    },
    "user-service": {
        "url": config.USER_SERVICE_URL or "http://localhost:8002",
        "prefix": "/user-service",
        "timeout": 120.0,   # 120s — BGE-M3 model loading takes ~30s on first call
        "retry": 1,
        "circuit_breaker_threshold": 10,  # higher threshold — ML service is slow but not broken
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
        "timeout": 300.0,   # 5 min — needed for SSE long-lived connections
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
    "automationservice": {
        "url": "http://localhost:8010",
        "prefix": "/automationservice",
        "timeout": 120.0,
        "retry": 1,
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
    """Get or create HTTP client with connection pooling.

    Client-level timeout is intentionally set to None so each request uses
    its own per-service timeout (e.g. 120s for user-service which loads BGE-M3).
    A hardcoded client-level timeout would silently override the per-request
    value and cause premature 503s on slow services.
    """
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(None),   # no client-level cap — use per-request timeout
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
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures: Dict[str, int] = {}
        self.last_failure_time: Dict[str, datetime] = {}
        self.open_circuits: Dict[str, bool] = {}
    
    def _get_threshold(self, service_name: str) -> int:
        """Get per-service failure threshold (falls back to default)."""
        svc = SERVICE_REGISTRY.get(service_name, {})
        return svc.get("circuit_breaker_threshold", self.failure_threshold)

    async def is_open(self, service_name: str) -> bool:
        """Check if circuit is open for a service"""
        if not self.open_circuits.get(service_name):
            return False
        
        # Check if timeout has passed — auto-reset
        last = self.last_failure_time.get(service_name)
        if last and datetime.utcnow() - last > timedelta(seconds=self.timeout):
            self.open_circuits[service_name] = False
            self.failures[service_name] = 0
            logger.info(f"Circuit breaker reset for {service_name}")
            return False
        
        return True
    
    async def record_success(self, service_name: str):
        """Record successful request"""
        self.failures[service_name] = 0
        self.open_circuits[service_name] = False
    
    async def record_failure(self, service_name: str):
        """Record failed request"""
        self.failures[service_name] = self.failures.get(service_name, 0) + 1
        self.last_failure_time[service_name] = datetime.utcnow()
        
        threshold = self._get_threshold(service_name)
        if self.failures[service_name] >= threshold:
            self.open_circuits[service_name] = True
            logger.error(
                f"Circuit breaker opened for {service_name} "
                f"after {self.failures[service_name]} failures "
                f"(threshold={threshold})"
            )

circuit_breaker = CircuitBreaker()

# ── Request Deduplication ─────────────────────────────────────────────────────
_pending_requests: Dict[str, asyncio.Future] = {}
_pending_lock = asyncio.Lock()

async def get_request_key(request: Request, body: bytes) -> str:
    """
    Generate unique key for request deduplication
    Based on: method + path + user + body hash
    """
    # Get user identifier from Authorization header
    auth_header = request.headers.get("Authorization", "")
    user_id = auth_header[-20:] if auth_header else "anonymous"  # Last 20 chars of token
    
    # Hash body for large payloads
    body_hash = hashlib.md5(body).hexdigest() if body else "empty"
    
    # Create unique key
    key = f"{request.method}:{request.url.path}:{user_id}:{body_hash}"
    return key

# ── Rate Limiting ─────────────────────────────────────────────────────────────
async def check_rate_limit(client_ip: str, endpoint: str) -> bool:
    """
    Check if request is within rate limit
    Returns True if allowed, False if rate limited
    Uses Redis with graceful fallback
    """
    try:
        redis = get_redis_client()
        key = f"rate_limit:{client_ip}:{endpoint}"
        
        # Use pipeline for atomic operations
        pipe = redis.pipeline()
        
        # Get current count
        pipe.get(key)
        pipe.ttl(key)
        
        # Execute pipeline with timeout
        results = await asyncio.wait_for(pipe.execute(), timeout=2.0)
        count_str, ttl = results
        
        if count_str is None:
            # First request - set with expiry
            await asyncio.wait_for(redis.setex(key, 60, 1), timeout=2.0)
            return True
        
        count = int(count_str)
        
        # Check if over limit (60 requests per minute per endpoint)
        if count >= 60:
            return False
        
        # Increment counter
        await asyncio.wait_for(redis.incr(key), timeout=2.0)
        return True
    
    except asyncio.TimeoutError:
        logger.warning(f"Rate limit check timeout for {client_ip}")
        # Fail open - allow request if Redis is slow
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
    Handles client disconnects gracefully and deduplicates rapid requests
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
    
    # Get request body with client disconnect handling
    try:
        body = await request.body()
    except ClientDisconnect:
        logger.warning(f"Client disconnected before request body was read for {service_name}")
        raise HTTPException(
            status_code=status.HTTP_499_CLIENT_CLOSED_REQUEST,
            detail="Client closed connection"
        )
    except Exception as e:
        logger.error(f"Error reading request body: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request body"
        )
    
    # Request deduplication for PATCH/PUT requests (settings updates)
    if request.method in ["PATCH", "PUT"]:
        request_key = await get_request_key(request, body)
        
        async with _pending_lock:
            if request_key in _pending_requests:
                # Duplicate request in progress - wait for it
                logger.info(f"Deduplicating request to {service_name}")
                try:
                    return await asyncio.wait_for(_pending_requests[request_key], timeout=timeout)
                except asyncio.TimeoutError:
                    # Original request timed out, proceed with new request
                    pass
            
            # Create future for this request
            future = asyncio.Future()
            _pending_requests[request_key] = future
    else:
        request_key = None
        future = None
    
    client = get_http_client()
    
    try:
        # Forward request with timeout
        response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            timeout=timeout,
        )
        
        # Record success
        await circuit_breaker.record_success(service_name)
        
        # Create response
        result = Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
        )
        
        # Set future result if deduplication was used
        if future and not future.done():
            future.set_result(result)
        
        return result
    
    except httpx.ReadTimeout as e:
        logger.error(f"Request to {service_name} timed out (attempt {attempt + 1}): {timeout}s timeout exceeded")
        
        # Record failure
        await circuit_breaker.record_failure(service_name)
        
        # Cancel future if exists
        if future and not future.done():
            future.set_exception(HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Service {service_name} request timed out after {timeout}s"
            ))
        
        # Retry if attempts remaining
        if attempt < max_retries:
            logger.info(f"Retrying request to {service_name} (attempt {attempt + 2})")
            await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
            return await forward_request(request, service_config, attempt + 1)
        
        # Max retries exceeded
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Service {service_name} request timed out after {timeout}s"
        )
    
    except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
        logger.error(f"Request to {service_name} failed (attempt {attempt + 1}): {type(e).__name__} - {str(e)}")
        
        # Record failure
        await circuit_breaker.record_failure(service_name)
        
        # Cancel future if exists
        if future and not future.done():
            future.set_exception(HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service {service_name} is unavailable"
            ))
        
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
        
        # Cancel future if exists
        if future and not future.done():
            future.set_exception(HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Gateway error"
            ))
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gateway error"
        )
    
    finally:
        # Clean up pending request
        if request_key:
            async with _pending_lock:
                _pending_requests.pop(request_key, None)

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
