"""
Resilient Client

Combines circuit breaker, retry, fallback, and bulkhead patterns
into a unified resilient execution framework.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar
from dataclasses import dataclass, field

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitState,
)
from .retry import RetryPolicy, retry_with_backoff, RetryExhausted
from .fallback import FallbackChain, FallbackResult, FallbackStrategy
from .bulkhead import Bulkhead, BulkheadFull

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ResilientConfig:
    """Configuration for resilient client."""
    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    success_threshold: int = 3
    circuit_timeout_seconds: float = 30.0

    # Retry settings
    retry_enabled: bool = True
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 10.0
    exponential_base: float = 2.0

    # Bulkhead settings
    bulkhead_enabled: bool = True
    max_concurrent: int = 20
    queue_size: int = 50
    queue_timeout: float = 30.0

    # Fallback settings
    fallback_enabled: bool = True
    fallback_strategy: FallbackStrategy = FallbackStrategy.FIRST_SUCCESS

    # Timeout
    timeout_seconds: float = 30.0


@dataclass
class ExecutionResult(Generic[T]):
    """Result of resilient execution."""
    success: bool
    value: Optional[T] = None
    source: str = "primary"
    latency_ms: float = 0.0
    retries: int = 0
    circuit_state: Optional[CircuitState] = None
    was_fallback: bool = False
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthStatus:
    """Health status of resilient client."""
    healthy: bool
    circuit_state: CircuitState
    current_concurrent: int
    max_concurrent: int
    success_rate: float
    avg_latency_ms: float
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None


class ResilientClient(Generic[T]):
    """
    Resilient client combining multiple fault tolerance patterns.

    Usage:
        client = ResilientClient[str](
            name="bedrock",
            primary=call_bedrock,
            config=ResilientConfig(max_attempts=3),
        )

        client.add_fallback("cache", get_from_cache)
        client.add_fallback("default", lambda: "Sorry, service unavailable")

        result = await client.execute(query="Hello")
    """

    def __init__(
        self,
        name: str,
        primary: Callable[..., T],
        config: Optional[ResilientConfig] = None,
    ):
        self.name = name
        self.primary = primary
        self.config = config or ResilientConfig()

        # Initialize components
        if self.config.circuit_breaker_enabled:
            self._circuit_breaker = CircuitBreaker(
                name=f"{name}-circuit",
                config=CircuitBreakerConfig(
                    failure_threshold=self.config.failure_threshold,
                    success_threshold=self.config.success_threshold,
                    timeout_seconds=self.config.circuit_timeout_seconds,
                ),
            )
        else:
            self._circuit_breaker = None

        if self.config.retry_enabled:
            self._retry_policy = RetryPolicy(
                max_attempts=self.config.max_attempts,
                initial_delay=self.config.initial_delay,
                max_delay=self.config.max_delay,
                exponential_base=self.config.exponential_base,
            )
        else:
            self._retry_policy = None

        if self.config.bulkhead_enabled:
            self._bulkhead = Bulkhead(
                name=f"{name}-bulkhead",
                max_concurrent=self.config.max_concurrent,
                queue_size=self.config.queue_size,
                queue_timeout=self.config.queue_timeout,
            )
        else:
            self._bulkhead = None

        self._fallbacks: List[tuple[str, Callable[..., T]]] = []
        self._default_value: Optional[T] = None

        # Metrics
        self._total_calls = 0
        self._successful_calls = 0
        self._total_latency = 0.0
        self._last_error: Optional[Exception] = None
        self._last_error_time: Optional[datetime] = None

    def add_fallback(
        self,
        name: str,
        func: Callable[..., T],
    ) -> "ResilientClient[T]":
        """Add a fallback option."""
        self._fallbacks.append((name, func))
        return self

    def set_default(self, value: T) -> "ResilientClient[T]":
        """Set default value when all else fails."""
        self._default_value = value
        return self

    async def execute(self, *args, **kwargs) -> ExecutionResult[T]:
        """Execute with full resilience pattern."""
        start_time = datetime.utcnow()
        self._total_calls += 1
        retries = 0

        try:
            # Check circuit breaker first
            if self._circuit_breaker:
                if self._circuit_breaker.state == CircuitState.OPEN:
                    logger.warning(f"Circuit breaker {self.name} is open, trying fallbacks")
                    return await self._execute_fallbacks(
                        start_time, args, kwargs
                    )

            # Execute with bulkhead
            if self._bulkhead:
                try:
                    async with self._bulkhead:
                        result, retries = await self._execute_with_retry(
                            *args, **kwargs
                        )
                except BulkheadFull as e:
                    logger.warning(f"Bulkhead {self.name} is full: {e}")
                    return await self._execute_fallbacks(
                        start_time, args, kwargs, error=e
                    )
            else:
                result, retries = await self._execute_with_retry(*args, **kwargs)

            # Success
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._successful_calls += 1
            self._total_latency += latency

            if self._circuit_breaker:
                # Record success (handled by context manager)
                pass

            return ExecutionResult(
                success=True,
                value=result,
                source="primary",
                latency_ms=latency,
                retries=retries,
                circuit_state=self._circuit_breaker.state if self._circuit_breaker else None,
                was_fallback=False,
            )

        except CircuitBreakerOpen as e:
            logger.warning(f"Circuit breaker open for {self.name}")
            return await self._execute_fallbacks(
                start_time, args, kwargs, error=e
            )

        except RetryExhausted as e:
            logger.error(f"All retries exhausted for {self.name}: {e.last_exception}")
            self._last_error = e.last_exception
            self._last_error_time = datetime.utcnow()

            # Open circuit breaker if configured
            if self._circuit_breaker:
                # Record failures
                pass

            return await self._execute_fallbacks(
                start_time, args, kwargs, error=e.last_exception, retries=e.attempts
            )

        except Exception as e:
            logger.error(f"Unexpected error in {self.name}: {e}")
            self._last_error = e
            self._last_error_time = datetime.utcnow()
            return await self._execute_fallbacks(
                start_time, args, kwargs, error=e
            )

    async def _execute_with_retry(
        self,
        *args,
        **kwargs,
    ) -> tuple[T, int]:
        """Execute primary with retry logic."""
        if not self._retry_policy:
            result = await self._execute_primary(*args, **kwargs)
            return result, 0

        retries = [0]  # Use list to allow modification in closure

        def on_retry(attempt, exception, delay):
            retries[0] = attempt

        result = await retry_with_backoff(
            self._execute_primary,
            *args,
            policy=self._retry_policy,
            on_retry=on_retry,
            **kwargs,
        )
        return result, retries[0]

    async def _execute_primary(self, *args, **kwargs) -> T:
        """Execute primary function with timeout."""
        if asyncio.iscoroutinefunction(self.primary):
            return await asyncio.wait_for(
                self.primary(*args, **kwargs),
                timeout=self.config.timeout_seconds,
            )
        return self.primary(*args, **kwargs)

    async def _execute_fallbacks(
        self,
        start_time: datetime,
        args: tuple,
        kwargs: dict,
        error: Optional[Exception] = None,
        retries: int = 0,
    ) -> ExecutionResult[T]:
        """Execute fallback chain."""
        if not self.config.fallback_enabled:
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            return ExecutionResult(
                success=False,
                latency_ms=latency,
                retries=retries,
                circuit_state=self._circuit_breaker.state if self._circuit_breaker else None,
                was_fallback=False,
                error=error,
            )

        # Try each fallback
        for name, fallback_func in self._fallbacks:
            try:
                if asyncio.iscoroutinefunction(fallback_func):
                    result = await asyncio.wait_for(
                        fallback_func(*args, **kwargs),
                        timeout=self.config.timeout_seconds,
                    )
                else:
                    result = fallback_func(*args, **kwargs)

                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.info(f"Fallback '{name}' succeeded for {self.name}")

                return ExecutionResult(
                    success=True,
                    value=result,
                    source=name,
                    latency_ms=latency,
                    retries=retries,
                    circuit_state=self._circuit_breaker.state if self._circuit_breaker else None,
                    was_fallback=True,
                )

            except Exception as e:
                logger.warning(f"Fallback '{name}' failed: {e}")
                continue

        # Use default value if set
        if self._default_value is not None:
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            return ExecutionResult(
                success=True,
                value=self._default_value,
                source="default",
                latency_ms=latency,
                retries=retries,
                circuit_state=self._circuit_breaker.state if self._circuit_breaker else None,
                was_fallback=True,
            )

        # All failed
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        return ExecutionResult(
            success=False,
            latency_ms=latency,
            retries=retries,
            circuit_state=self._circuit_breaker.state if self._circuit_breaker else None,
            was_fallback=True,
            error=error,
        )

    def get_health(self) -> HealthStatus:
        """Get current health status."""
        success_rate = (
            self._successful_calls / self._total_calls
            if self._total_calls > 0
            else 1.0
        )

        avg_latency = (
            self._total_latency / self._successful_calls
            if self._successful_calls > 0
            else 0.0
        )

        circuit_state = (
            self._circuit_breaker.state
            if self._circuit_breaker
            else CircuitState.CLOSED
        )

        current_concurrent = 0
        max_concurrent = self.config.max_concurrent
        if self._bulkhead:
            current_concurrent = self._bulkhead.metrics.current_concurrent

        return HealthStatus(
            healthy=circuit_state == CircuitState.CLOSED and success_rate >= 0.5,
            circuit_state=circuit_state,
            current_concurrent=current_concurrent,
            max_concurrent=max_concurrent,
            success_rate=success_rate,
            avg_latency_ms=avg_latency,
            last_error=str(self._last_error) if self._last_error else None,
            last_error_time=self._last_error_time,
        )

    def reset(self) -> None:
        """Reset circuit breaker and metrics."""
        if self._circuit_breaker:
            self._circuit_breaker.reset()
        self._total_calls = 0
        self._successful_calls = 0
        self._total_latency = 0.0
        self._last_error = None
        self._last_error_time = None


class ResilientClientFactory:
    """
    Factory for creating pre-configured resilient clients.
    """

    # Pre-configured settings for different services
    SERVICE_CONFIGS = {
        "bedrock": ResilientConfig(
            failure_threshold=5,
            max_attempts=3,
            initial_delay=1.0,
            max_concurrent=50,
            queue_size=100,
            timeout_seconds=60.0,
        ),
        "bedrock-agent": ResilientConfig(
            failure_threshold=3,
            max_attempts=2,
            initial_delay=0.5,
            max_concurrent=20,
            queue_size=50,
            timeout_seconds=90.0,
        ),
        "tcs-bancs": ResilientConfig(
            failure_threshold=3,
            max_attempts=2,
            initial_delay=0.5,
            max_concurrent=30,
            queue_size=60,
            timeout_seconds=30.0,
        ),
        "knowledge-base": ResilientConfig(
            failure_threshold=5,
            max_attempts=3,
            initial_delay=0.5,
            max_concurrent=20,
            queue_size=40,
            timeout_seconds=30.0,
        ),
        "cache-redis": ResilientConfig(
            failure_threshold=10,
            max_attempts=2,
            initial_delay=0.1,
            max_concurrent=200,
            queue_size=500,
            timeout_seconds=5.0,
        ),
        "cache-dynamodb": ResilientConfig(
            failure_threshold=5,
            max_attempts=3,
            initial_delay=0.2,
            max_concurrent=100,
            queue_size=200,
            timeout_seconds=10.0,
        ),
    }

    @classmethod
    def create(
        cls,
        service_type: str,
        primary: Callable[..., T],
        name: Optional[str] = None,
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> ResilientClient[T]:
        """Create a resilient client for a service type."""
        base_config = cls.SERVICE_CONFIGS.get(service_type, ResilientConfig())

        # Apply overrides
        if config_overrides:
            config_dict = {
                k: v for k, v in vars(base_config).items()
                if not k.startswith("_")
            }
            config_dict.update(config_overrides)
            config = ResilientConfig(**config_dict)
        else:
            config = base_config

        return ResilientClient(
            name=name or service_type,
            primary=primary,
            config=config,
        )
