"""
Bulkhead Pattern Implementation

Isolates failures by limiting concurrent operations per service.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional, TypeVar
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BulkheadFull(Exception):
    """Raised when bulkhead capacity is exhausted."""

    def __init__(self, name: str, max_concurrent: int, queue_size: int):
        super().__init__(
            f"Bulkhead '{name}' is full: "
            f"{max_concurrent} concurrent, {queue_size} queued"
        )
        self.name = name
        self.max_concurrent = max_concurrent
        self.queue_size = queue_size


@dataclass
class BulkheadMetrics:
    """Metrics for bulkhead monitoring."""
    total_accepted: int = 0
    total_rejected: int = 0
    total_completed: int = 0
    total_failed: int = 0
    current_concurrent: int = 0
    current_queued: int = 0
    max_concurrent_reached: int = 0
    max_queued_reached: int = 0
    avg_wait_time_ms: float = 0.0
    avg_execution_time_ms: float = 0.0


class Bulkhead:
    """
    Bulkhead implementation for isolating service calls.

    Limits concurrent operations and queues excess requests.

    Usage:
        bulkhead = Bulkhead("bedrock", max_concurrent=10, queue_size=50)

        async with bulkhead:
            result = await call_bedrock()
    """

    def __init__(
        self,
        name: str,
        max_concurrent: int = 10,
        queue_size: int = 50,
        queue_timeout: float = 30.0,
    ):
        self.name = name
        self.max_concurrent = max_concurrent
        self.queue_size = queue_size
        self.queue_timeout = queue_timeout

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue_semaphore = asyncio.Semaphore(queue_size)
        self._metrics = BulkheadMetrics()
        self._lock = asyncio.Lock()

        # Timing tracking
        self._total_wait_time = 0.0
        self._total_execution_time = 0.0
        self._completed_count = 0

    @property
    def metrics(self) -> BulkheadMetrics:
        """Get current metrics."""
        return self._metrics

    async def __aenter__(self):
        """Enter bulkhead context."""
        # Try to acquire queue slot
        if not self._queue_semaphore.locked():
            acquired_queue = await asyncio.wait_for(
                self._queue_semaphore.acquire(),
                timeout=0.0,
            )
        else:
            # Try with small timeout
            try:
                acquired_queue = await asyncio.wait_for(
                    self._queue_semaphore.acquire(),
                    timeout=0.1,
                )
            except asyncio.TimeoutError:
                async with self._lock:
                    self._metrics.total_rejected += 1
                raise BulkheadFull(
                    self.name,
                    self.max_concurrent,
                    self.queue_size,
                )

        async with self._lock:
            self._metrics.total_accepted += 1
            self._metrics.current_queued += 1
            self._metrics.max_queued_reached = max(
                self._metrics.max_queued_reached,
                self._metrics.current_queued,
            )

        # Wait for execution slot
        queue_start = datetime.utcnow()
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.queue_timeout,
            )
        except asyncio.TimeoutError:
            self._queue_semaphore.release()
            async with self._lock:
                self._metrics.current_queued -= 1
                self._metrics.total_rejected += 1
            raise BulkheadFull(
                self.name,
                self.max_concurrent,
                self.queue_size,
            )

        queue_time = (datetime.utcnow() - queue_start).total_seconds() * 1000

        async with self._lock:
            self._metrics.current_queued -= 1
            self._metrics.current_concurrent += 1
            self._metrics.max_concurrent_reached = max(
                self._metrics.max_concurrent_reached,
                self._metrics.current_concurrent,
            )
            self._total_wait_time += queue_time

        self._execution_start = datetime.utcnow()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit bulkhead context."""
        execution_time = (datetime.utcnow() - self._execution_start).total_seconds() * 1000

        self._semaphore.release()
        self._queue_semaphore.release()

        async with self._lock:
            self._metrics.current_concurrent -= 1
            self._metrics.total_completed += 1
            self._total_execution_time += execution_time
            self._completed_count += 1

            if exc_type is not None:
                self._metrics.total_failed += 1

            # Update averages
            if self._completed_count > 0:
                self._metrics.avg_wait_time_ms = (
                    self._total_wait_time / self._completed_count
                )
                self._metrics.avg_execution_time_ms = (
                    self._total_execution_time / self._completed_count
                )

        return False

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for bulkhead protection."""
        async def wrapper(*args, **kwargs) -> T:
            async with self:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
        return wrapper


class BulkheadRegistry:
    """
    Registry for managing bulkheads per service.

    Usage:
        registry = BulkheadRegistry()
        bulkhead = registry.get_or_create("bedrock")
    """

    # Default configurations for different services
    DEFAULT_CONFIGS = {
        "bedrock": {"max_concurrent": 50, "queue_size": 100},
        "bedrock-agent": {"max_concurrent": 20, "queue_size": 50},
        "tcs-bancs": {"max_concurrent": 30, "queue_size": 60},
        "knowledge-base": {"max_concurrent": 20, "queue_size": 40},
        "dynamodb": {"max_concurrent": 100, "queue_size": 200},
        "redis": {"max_concurrent": 200, "queue_size": 500},
        "ses": {"max_concurrent": 10, "queue_size": 50},
    }

    def __init__(self):
        self._bulkheads: Dict[str, Bulkhead] = {}
        self._lock = asyncio.Lock()

    def get_or_create(
        self,
        name: str,
        max_concurrent: Optional[int] = None,
        queue_size: Optional[int] = None,
        queue_timeout: float = 30.0,
    ) -> Bulkhead:
        """Get existing or create new bulkhead."""
        if name not in self._bulkheads:
            config = self.DEFAULT_CONFIGS.get(name, {})
            self._bulkheads[name] = Bulkhead(
                name=name,
                max_concurrent=max_concurrent or config.get("max_concurrent", 10),
                queue_size=queue_size or config.get("queue_size", 50),
                queue_timeout=queue_timeout,
            )
        return self._bulkheads[name]

    def get(self, name: str) -> Optional[Bulkhead]:
        """Get bulkhead by name."""
        return self._bulkheads.get(name)

    def get_all_metrics(self) -> Dict[str, BulkheadMetrics]:
        """Get metrics for all bulkheads."""
        return {name: bh.metrics for name, bh in self._bulkheads.items()}

    def get_overloaded(self) -> Dict[str, Bulkhead]:
        """Get bulkheads that are at or near capacity."""
        overloaded = {}
        for name, bh in self._bulkheads.items():
            utilization = bh.metrics.current_concurrent / bh.max_concurrent
            if utilization >= 0.8:  # 80% threshold
                overloaded[name] = bh
        return overloaded


# Global registry
_global_bulkhead_registry = BulkheadRegistry()


def get_bulkhead(name: str) -> Bulkhead:
    """Get or create bulkhead from global registry."""
    return _global_bulkhead_registry.get_or_create(name)


def bulkhead(name: str):
    """Decorator to protect function with bulkhead."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        bh = get_bulkhead(name)
        return bh(func)
    return decorator
