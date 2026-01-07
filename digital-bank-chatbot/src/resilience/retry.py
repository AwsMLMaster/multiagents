"""
Retry Pattern Implementation

Handles transient failures with configurable retry strategies.
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryExhausted(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_exception: Exception,
        total_time: float,
    ):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception
        self.total_time = total_time


@dataclass
class RetryPolicy:
    """
    Configuration for retry behavior.

    Supports:
    - Fixed delay
    - Exponential backoff
    - Jitter
    - Exception filtering
    """
    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.25  # +/- 25%
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()

    def should_retry(self, exception: Exception) -> bool:
        """Check if exception is retryable."""
        if isinstance(exception, self.non_retryable_exceptions):
            return False
        return isinstance(exception, self.retryable_exceptions)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt (1-indexed)."""
        delay = self.initial_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)

        if self.jitter:
            jitter_range = delay * self.jitter_factor
            delay = delay + random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)

        return delay


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    attempt_number: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    success: bool = False
    exception: Optional[Exception] = None
    delay_before: float = 0.0


@dataclass
class RetryResult:
    """Result of a retry operation."""
    success: bool
    result: Any = None
    attempts: int = 0
    total_time: float = 0.0
    attempt_history: list = field(default_factory=list)
    final_exception: Optional[Exception] = None


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    policy: Optional[RetryPolicy] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    **kwargs,
) -> T:
    """
    Execute a function with retry logic.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        policy: Retry policy configuration
        on_retry: Callback called before each retry (attempt, exception, delay)
        **kwargs: Keyword arguments for func

    Returns:
        Result of successful function call

    Raises:
        RetryExhausted: If all attempts fail
    """
    policy = policy or RetryPolicy()
    start_time = datetime.utcnow()
    last_exception = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            return result

        except Exception as e:
            last_exception = e

            # Check if we should retry
            if not policy.should_retry(e):
                logger.debug(f"Exception {type(e).__name__} is not retryable")
                raise

            # Check if we have attempts left
            if attempt >= policy.max_attempts:
                break

            # Calculate delay
            delay = policy.get_delay(attempt)

            logger.warning(
                f"Attempt {attempt}/{policy.max_attempts} failed: {e}. "
                f"Retrying in {delay:.2f}s"
            )

            # Notify callback
            if on_retry:
                try:
                    on_retry(attempt, e, delay)
                except Exception as callback_error:
                    logger.error(f"Retry callback failed: {callback_error}")

            # Wait before retry
            await asyncio.sleep(delay)

    # All attempts exhausted
    total_time = (datetime.utcnow() - start_time).total_seconds()
    raise RetryExhausted(
        message=f"All {policy.max_attempts} retry attempts exhausted",
        attempts=policy.max_attempts,
        last_exception=last_exception,
        total_time=total_time,
    )


def retry(
    policy: Optional[RetryPolicy] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
):
    """
    Decorator for adding retry logic to functions.

    Usage:
        @retry(policy=RetryPolicy(max_attempts=5))
        async def call_api():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry_with_backoff(
                func,
                *args,
                policy=policy,
                on_retry=on_retry,
                **kwargs,
            )
        return wrapper
    return decorator


# Pre-configured retry policies for common scenarios

BEDROCK_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    retryable_exceptions=(
        ConnectionError,
        TimeoutError,
        # Add boto3 throttling exceptions
    ),
)

TCS_BANCS_RETRY_POLICY = RetryPolicy(
    max_attempts=2,
    initial_delay=0.5,
    max_delay=5.0,
    exponential_base=2.0,
    jitter=True,
    # Financial operations - be conservative with retries
)

CACHE_RETRY_POLICY = RetryPolicy(
    max_attempts=2,
    initial_delay=0.1,
    max_delay=1.0,
    exponential_base=2.0,
)

KNOWLEDGE_BASE_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    initial_delay=0.5,
    max_delay=5.0,
    exponential_base=2.0,
)


class RetryBudget:
    """
    Limits total retries across multiple operations.

    Prevents retry storms when many operations fail simultaneously.
    """

    def __init__(
        self,
        budget_per_second: float = 10.0,
        min_budget: float = 3.0,
    ):
        self.budget_per_second = budget_per_second
        self.min_budget = min_budget
        self._budget = min_budget
        self._last_update = datetime.utcnow()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Try to acquire a retry token."""
        async with self._lock:
            self._replenish()

            if self._budget >= 1.0:
                self._budget -= 1.0
                return True

            return False

    def _replenish(self) -> None:
        """Replenish budget based on elapsed time."""
        now = datetime.utcnow()
        elapsed = (now - self._last_update).total_seconds()
        self._budget = min(
            self.min_budget * 3,  # Max budget
            self._budget + (elapsed * self.budget_per_second)
        )
        self._last_update = now


# Global retry budget
_global_budget = RetryBudget()


async def retry_with_budget(
    func: Callable[..., T],
    *args,
    policy: Optional[RetryPolicy] = None,
    budget: Optional[RetryBudget] = None,
    **kwargs,
) -> T:
    """
    Retry with global budget limiting.

    Prevents retry storms during widespread outages.
    """
    policy = policy or RetryPolicy()
    budget = budget or _global_budget
    start_time = datetime.utcnow()
    last_exception = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            return result

        except Exception as e:
            last_exception = e

            if not policy.should_retry(e):
                raise

            if attempt >= policy.max_attempts:
                break

            # Check budget before retrying
            if not await budget.acquire():
                logger.warning("Retry budget exhausted, failing fast")
                break

            delay = policy.get_delay(attempt)
            await asyncio.sleep(delay)

    total_time = (datetime.utcnow() - start_time).total_seconds()
    raise RetryExhausted(
        message=f"Retry failed after {attempt} attempts",
        attempts=attempt,
        last_exception=last_exception,
        total_time=total_time,
    )
