"""
Retry Pattern Implementation.

Handles transient failures (e.g., property data provider timeouts, geocoding
rate limits) with configurable retry strategies.
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Callable, Tuple, Type, TypeVar
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryExhausted(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, message: str, attempts: int, last_exception: Exception, total_time: float):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception
        self.total_time = total_time


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.25
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()

    def should_retry(self, exception: Exception) -> bool:
        if isinstance(exception, self.non_retryable_exceptions):
            return False
        return isinstance(exception, self.retryable_exceptions)

    def get_delay(self, attempt: int) -> float:
        delay = self.initial_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)
        if self.jitter:
            jitter_range = delay * self.jitter_factor
            delay = max(0, delay + random.uniform(-jitter_range, jitter_range))
        return delay


@dataclass
class RetryResult:
    """Result of a retry operation."""
    success: bool
    result: object = None
    attempts: int = 0
    total_time: float = 0.0
    attempt_history: list = field(default_factory=list)
    final_exception: Exception = None


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    policy: RetryPolicy = None,
    on_retry: Callable[[int, Exception, float], None] = None,
    **kwargs,
) -> T:
    """Execute a function with retry logic."""
    policy = policy or RetryPolicy()
    start_time = datetime.utcnow()
    last_exception = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        except Exception as e:
            last_exception = e

            if not policy.should_retry(e):
                raise

            if attempt >= policy.max_attempts:
                break

            delay = policy.get_delay(attempt)
            logger.warning(
                f"Attempt {attempt}/{policy.max_attempts} failed: {e}. Retrying in {delay:.2f}s"
            )

            if on_retry:
                try:
                    on_retry(attempt, e, delay)
                except Exception as callback_error:
                    logger.error(f"Retry callback failed: {callback_error}")

            await asyncio.sleep(delay)

    total_time = (datetime.utcnow() - start_time).total_seconds()
    raise RetryExhausted(
        message=f"All {policy.max_attempts} retry attempts exhausted",
        attempts=policy.max_attempts,
        last_exception=last_exception,
        total_time=total_time,
    )


def retry(policy: RetryPolicy = None, on_retry: Callable[[int, Exception, float], None] = None):
    """Decorator for adding retry logic to functions."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry_with_backoff(func, *args, policy=policy, on_retry=on_retry, **kwargs)
        return wrapper
    return decorator


# Pre-configured retry policies for common services

BEDROCK_RETRY_POLICY = RetryPolicy(
    max_attempts=3, initial_delay=1.0, max_delay=10.0, exponential_base=2.0,
    retryable_exceptions=(ConnectionError, TimeoutError),
)

PROPERTY_DATA_RETRY_POLICY = RetryPolicy(
    max_attempts=3, initial_delay=0.5, max_delay=8.0, exponential_base=2.0, jitter=True,
)

GEOCODING_RETRY_POLICY = RetryPolicy(
    max_attempts=2, initial_delay=0.5, max_delay=4.0, exponential_base=2.0,
)

MORTGAGE_RATES_RETRY_POLICY = RetryPolicy(
    max_attempts=2, initial_delay=0.5, max_delay=4.0, exponential_base=2.0,
)

CACHE_RETRY_POLICY = RetryPolicy(
    max_attempts=2, initial_delay=0.1, max_delay=1.0, exponential_base=2.0,
)

KNOWLEDGE_BASE_RETRY_POLICY = RetryPolicy(
    max_attempts=3, initial_delay=0.5, max_delay=5.0, exponential_base=2.0,
)
