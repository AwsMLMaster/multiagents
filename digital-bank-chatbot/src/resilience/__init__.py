# Resilience Module
# Fault tolerance patterns: circuit breaker, retry, fallback, bulkhead

from .circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerRegistry
from .retry import RetryPolicy, retry_with_backoff, RetryExhausted
from .fallback import FallbackChain, FallbackStrategy, GracefulDegradation
from .bulkhead import Bulkhead, BulkheadRegistry
from .resilient_client import ResilientClient, ResilientConfig

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerRegistry",
    "RetryPolicy",
    "retry_with_backoff",
    "RetryExhausted",
    "FallbackChain",
    "FallbackStrategy",
    "GracefulDegradation",
    "Bulkhead",
    "BulkheadRegistry",
    "ResilientClient",
    "ResilientConfig",
]
