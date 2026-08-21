"""
Circuit Breaker Pattern Implementation.

Prevents cascading failures by failing fast when a dependency (property data
provider, geocoding API, mortgage rates provider, Bedrock) is unhealthy.
"""

import asyncio
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, Optional, TypeVar
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_seconds: float = 30.0
    half_open_max_calls: int = 3
    excluded_exceptions: tuple = ()


@dataclass
class CircuitBreakerMetrics:
    """Metrics tracked by circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreaker:
    """Circuit breaker implementation with async support."""

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        on_state_change: Optional[Callable[[str, CircuitState, CircuitState], None]] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.on_state_change = on_state_change

        self._state = CircuitState.CLOSED
        self._metrics = CircuitBreakerMetrics()
        self._opened_at: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._should_transition_to_half_open():
            self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    @property
    def metrics(self) -> CircuitBreakerMetrics:
        return self._metrics

    def _should_transition_to_half_open(self) -> bool:
        if self._opened_at is None:
            return False
        return (time.time() - self._opened_at) >= self.config.timeout_seconds

    def _transition_to(self, new_state: CircuitState) -> None:
        old_state = self._state

        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
            self._half_open_calls = 0
            logger.warning(
                f"Circuit breaker '{self.name}' OPENED after "
                f"{self._metrics.consecutive_failures} failures"
            )
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            logger.info(f"Circuit breaker '{self.name}' entering HALF-OPEN state")
        elif new_state == CircuitState.CLOSED:
            self._opened_at = None
            self._metrics.consecutive_failures = 0
            logger.info(f"Circuit breaker '{self.name}' CLOSED - service recovered")

        self._state = new_state
        self._metrics.state_changes += 1

        if self.on_state_change:
            try:
                self.on_state_change(self.name, old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback failed: {e}")

    def _record_success(self) -> None:
        self._metrics.total_calls += 1
        self._metrics.successful_calls += 1
        self._metrics.consecutive_successes += 1
        self._metrics.consecutive_failures = 0
        self._metrics.last_success_time = datetime.utcnow()

        if self._state == CircuitState.HALF_OPEN:
            if self._metrics.consecutive_successes >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)

    def _record_failure(self, exception: Exception) -> None:
        if isinstance(exception, self.config.excluded_exceptions):
            return

        self._metrics.total_calls += 1
        self._metrics.failed_calls += 1
        self._metrics.consecutive_failures += 1
        self._metrics.consecutive_successes = 0
        self._metrics.last_failure_time = datetime.utcnow()

        if self._state == CircuitState.CLOSED:
            if self._metrics.consecutive_failures >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)

    def _can_execute(self) -> bool:
        state = self.state

        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.OPEN:
            self._metrics.rejected_calls += 1
            return False
        if state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        return False

    async def __aenter__(self):
        async with self._lock:
            if not self._can_execute():
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is OPEN",
                    breaker_name=self.name,
                    retry_after=self._get_retry_after(),
                )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            if exc_type is None:
                self._record_success()
            elif exc_val is not None:
                self._record_failure(exc_val)
        return False

    def _get_retry_after(self) -> Optional[float]:
        if self._state != CircuitState.OPEN or self._opened_at is None:
            return None
        return max(0, self.config.timeout_seconds - (time.time() - self._opened_at))

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            async with self:
                return await func(*args, **kwargs)
        return wrapper

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._half_open_calls = 0
        self._metrics.consecutive_failures = 0
        self._metrics.consecutive_successes = 0
        logger.info(f"Circuit breaker '{self.name}' manually reset")


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, message: str, breaker_name: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.breaker_name = breaker_name
        self.retry_after = retry_after


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._default_config = CircuitBreakerConfig()

    def set_default_config(self, config: CircuitBreakerConfig) -> None:
        self._default_config = config

    def get_or_create(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                config=config or self._default_config,
                on_state_change=self._on_state_change,
            )
        return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        return self._breakers.get(name)

    def _on_state_change(self, name: str, old_state: CircuitState, new_state: CircuitState) -> None:
        logger.info(f"Circuit breaker '{name}': {old_state.value} -> {new_state.value}")

    def get_all_metrics(self) -> Dict[str, CircuitBreakerMetrics]:
        return {name: cb.metrics for name, cb in self._breakers.items()}

    def get_unhealthy(self) -> Dict[str, CircuitBreaker]:
        return {name: cb for name, cb in self._breakers.items() if cb.state != CircuitState.CLOSED}

    def reset_all(self) -> None:
        for breaker in self._breakers.values():
            breaker.reset()


_global_registry = CircuitBreakerRegistry()


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker from the global registry."""
    return _global_registry.get_or_create(name)


def circuit_breaker(name: str):
    """Decorator to protect a function with a circuit breaker."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker = get_circuit_breaker(name)
        return breaker(func)
    return decorator
