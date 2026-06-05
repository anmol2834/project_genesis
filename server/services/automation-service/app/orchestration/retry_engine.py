"""
Orchestration - Retry Engine
=============================
Enterprise retry system with exponential backoff and DLQ.
"""
import asyncio
import random
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
from app.observability import get_logger, get_metrics_collector

logger = get_logger(__name__)

class RetryPolicy:
    """Retry policy configuration"""
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay_ms: float = 100,
        max_delay_ms: float = 10000,
        backoff_multiplier: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff"""
        delay = min(
            self.initial_delay_ms * (self.backoff_multiplier ** attempt),
            self.max_delay_ms
        )
        
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay / 1000  # Convert to seconds

class RetryableError(Exception):
    """Error that should trigger retry"""
    pass

class NonRetryableError(Exception):
    """Error that should NOT trigger retry"""
    pass

class RetryEngine:
    """Enterprise retry engine"""
    
    # Default policies by operation type
    POLICIES = {
        "retrieval": RetryPolicy(max_retries=2, initial_delay_ms=50),
        "llm": RetryPolicy(max_retries=3, initial_delay_ms=100),
        "memory": RetryPolicy(max_retries=2, initial_delay_ms=20),
        "dispatch": RetryPolicy(max_retries=3, initial_delay_ms=200),
        "default": RetryPolicy(max_retries=3, initial_delay_ms=100)
    }
    
    def __init__(self):
        self.metrics = get_metrics_collector()
        self.retry_counts: dict[str, int] = {}
    
    async def execute_with_retry(
        self,
        operation: str,
        func: Callable,
        *args,
        policy: Optional[RetryPolicy] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Execute function with retry logic"""
        policy = policy or self.POLICIES.get(operation, self.POLICIES["default"])
        
        last_error = None
        for attempt in range(policy.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(
                        f"Retry succeeded",
                        operation=operation,
                        attempt=attempt,
                        user_id=user_id
                    )
                    self.metrics.record_counter(
                        f"retry.{operation}.success",
                        1,
                        user_id or "system"
                    )
                
                return result
                
            except NonRetryableError as e:
                logger.error(
                    f"Non-retryable error",
                    operation=operation,
                    error=e,
                    user_id=user_id
                )
                raise
                
            except Exception as e:
                last_error = e
                
                if attempt < policy.max_retries:
                    delay = policy.calculate_delay(attempt)
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{policy.max_retries}",
                        operation=operation,
                        delay_sec=delay,
                        error=str(e),
                        user_id=user_id
                    )
                    
                    self.metrics.record_counter(
                        f"retry.{operation}.attempt",
                        1,
                        user_id or "system"
                    )
                    
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Max retries exceeded",
                        operation=operation,
                        attempts=policy.max_retries + 1,
                        error=e,
                        user_id=user_id
                    )
                    self.metrics.record_counter(
                        f"retry.{operation}.exhausted",
                        1,
                        user_id or "system"
                    )
        
        raise last_error
    
    def is_transient_error(self, error: Exception) -> bool:
        """Classify error as transient or permanent"""
        transient_indicators = [
            "timeout",
            "connection",
            "temporarily unavailable",
            "rate limit",
            "503",
            "429"
        ]
        
        error_str = str(error).lower()
        return any(indicator in error_str for indicator in transient_indicators)

retry_engine = RetryEngine()

__all__ = ["RetryEngine", "RetryPolicy", "RetryableError", "NonRetryableError", "retry_engine"]
