"""
Fallback Pattern Implementation

Provides graceful degradation when primary services fail.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FallbackStrategy(Enum):
    """Fallback behavior strategies."""
    FIRST_SUCCESS = "first_success"  # Try fallbacks until one succeeds
    FASTEST = "fastest"  # Try all concurrently, use fastest success
    CACHED = "cached"  # Return cached value
    DEFAULT = "default"  # Return default value
    FAIL = "fail"  # Raise exception


@dataclass
class FallbackResult(Generic[T]):
    """Result of fallback execution."""
    success: bool
    value: Optional[T] = None
    source: str = "primary"
    latency_ms: float = 0.0
    was_fallback: bool = False
    error: Optional[Exception] = None


class FallbackChain(Generic[T]):
    """
    Chain of fallback options with configurable strategies.

    Usage:
        chain = FallbackChain[str]()
        chain.add_primary(call_bedrock)
        chain.add_fallback("cache", get_cached_response)
        chain.add_fallback("default", lambda: "Sorry, I couldn't process that")

        result = await chain.execute()
    """

    def __init__(
        self,
        strategy: FallbackStrategy = FallbackStrategy.FIRST_SUCCESS,
        timeout: float = 30.0,
    ):
        self.strategy = strategy
        self.timeout = timeout
        self._primary: Optional[Callable[..., T]] = None
        self._fallbacks: List[tuple[str, Callable[..., T]]] = []
        self._cached_value: Optional[T] = None
        self._default_value: Optional[T] = None

    def add_primary(self, func: Callable[..., T]) -> "FallbackChain[T]":
        """Set the primary function."""
        self._primary = func
        return self

    def add_fallback(
        self,
        name: str,
        func: Callable[..., T],
    ) -> "FallbackChain[T]":
        """Add a fallback option."""
        self._fallbacks.append((name, func))
        return self

    def set_cached(self, value: T) -> "FallbackChain[T]":
        """Set cached value for CACHED strategy."""
        self._cached_value = value
        return self

    def set_default(self, value: T) -> "FallbackChain[T]":
        """Set default value for DEFAULT strategy."""
        self._default_value = value
        return self

    async def execute(self, *args, **kwargs) -> FallbackResult[T]:
        """Execute with fallback logic."""
        start_time = datetime.utcnow()

        if self.strategy == FallbackStrategy.FASTEST:
            return await self._execute_fastest(*args, **kwargs)

        # Try primary first
        if self._primary:
            try:
                result = await self._execute_with_timeout(
                    self._primary, *args, **kwargs
                )
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                return FallbackResult(
                    success=True,
                    value=result,
                    source="primary",
                    latency_ms=latency,
                    was_fallback=False,
                )
            except Exception as e:
                logger.warning(f"Primary failed: {e}, trying fallbacks")

        # Try fallbacks in order
        for name, fallback_func in self._fallbacks:
            try:
                result = await self._execute_with_timeout(
                    fallback_func, *args, **kwargs
                )
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.info(f"Fallback '{name}' succeeded")
                return FallbackResult(
                    success=True,
                    value=result,
                    source=name,
                    latency_ms=latency,
                    was_fallback=True,
                )
            except Exception as e:
                logger.warning(f"Fallback '{name}' failed: {e}")
                continue

        # Handle based on strategy
        return await self._handle_all_failed(start_time)

    async def _execute_fastest(self, *args, **kwargs) -> FallbackResult[T]:
        """Execute all options concurrently, use fastest success."""
        start_time = datetime.utcnow()

        all_funcs = []
        all_names = []

        if self._primary:
            all_funcs.append(self._primary)
            all_names.append("primary")

        for name, func in self._fallbacks:
            all_funcs.append(func)
            all_names.append(name)

        if not all_funcs:
            return await self._handle_all_failed(start_time)

        # Create tasks for all options
        tasks = [
            asyncio.create_task(
                self._execute_with_timeout(func, *args, **kwargs)
            )
            for func in all_funcs
        ]

        # Wait for first success
        done = set()
        pending = set(tasks)

        while pending:
            finished, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in finished:
                done.add(task)
                try:
                    result = task.result()
                    # Cancel remaining tasks
                    for p in pending:
                        p.cancel()

                    task_idx = tasks.index(task)
                    latency = (datetime.utcnow() - start_time).total_seconds() * 1000

                    return FallbackResult(
                        success=True,
                        value=result,
                        source=all_names[task_idx],
                        latency_ms=latency,
                        was_fallback=all_names[task_idx] != "primary",
                    )
                except Exception:
                    continue

        # All failed
        return await self._handle_all_failed(start_time)

    async def _execute_with_timeout(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """Execute function with timeout."""
        if asyncio.iscoroutinefunction(func):
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.timeout,
            )
        else:
            return func(*args, **kwargs)

    async def _handle_all_failed(
        self,
        start_time: datetime,
    ) -> FallbackResult[T]:
        """Handle case when all options failed."""
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        if self.strategy == FallbackStrategy.CACHED and self._cached_value is not None:
            return FallbackResult(
                success=True,
                value=self._cached_value,
                source="cached",
                latency_ms=latency,
                was_fallback=True,
            )

        if self.strategy == FallbackStrategy.DEFAULT and self._default_value is not None:
            return FallbackResult(
                success=True,
                value=self._default_value,
                source="default",
                latency_ms=latency,
                was_fallback=True,
            )

        return FallbackResult(
            success=False,
            source="none",
            latency_ms=latency,
            was_fallback=True,
            error=Exception("All fallback options exhausted"),
        )


class GracefulDegradation:
    """
    Manages graceful degradation of service capabilities.

    Tracks which services are healthy and adjusts responses accordingly.
    """

    def __init__(self):
        self._service_status: Dict[str, bool] = {}
        self._degraded_handlers: Dict[str, Callable[..., Any]] = {}
        self._capabilities: Dict[str, List[str]] = {}

    def register_service(
        self,
        service_name: str,
        capabilities: List[str],
        degraded_handler: Optional[Callable[..., Any]] = None,
    ) -> None:
        """Register a service and its capabilities."""
        self._service_status[service_name] = True
        self._capabilities[service_name] = capabilities
        if degraded_handler:
            self._degraded_handlers[service_name] = degraded_handler

    def mark_unhealthy(self, service_name: str) -> None:
        """Mark a service as unhealthy."""
        if service_name in self._service_status:
            self._service_status[service_name] = False
            logger.warning(f"Service '{service_name}' marked as unhealthy")

    def mark_healthy(self, service_name: str) -> None:
        """Mark a service as healthy."""
        if service_name in self._service_status:
            self._service_status[service_name] = True
            logger.info(f"Service '{service_name}' marked as healthy")

    def is_healthy(self, service_name: str) -> bool:
        """Check if service is healthy."""
        return self._service_status.get(service_name, False)

    def get_available_capabilities(self) -> List[str]:
        """Get list of currently available capabilities."""
        available = []
        for service, healthy in self._service_status.items():
            if healthy:
                available.extend(self._capabilities.get(service, []))
        return list(set(available))

    def can_handle(self, capability: str) -> bool:
        """Check if a capability is currently available."""
        return capability in self.get_available_capabilities()

    async def execute_with_degradation(
        self,
        service_name: str,
        primary_func: Callable[..., T],
        *args,
        **kwargs,
    ) -> Optional[T]:
        """Execute with automatic degradation handling."""
        if not self.is_healthy(service_name):
            handler = self._degraded_handlers.get(service_name)
            if handler:
                return await self._execute_async(handler, *args, **kwargs)
            return None

        try:
            return await self._execute_async(primary_func, *args, **kwargs)
        except Exception as e:
            logger.error(f"Service '{service_name}' failed: {e}")
            self.mark_unhealthy(service_name)

            handler = self._degraded_handlers.get(service_name)
            if handler:
                return await self._execute_async(handler, *args, **kwargs)
            return None

    async def _execute_async(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """Execute function (async or sync)."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    def get_degraded_response_template(self) -> Dict[str, Any]:
        """Get template for degraded response."""
        unavailable_services = [
            s for s, healthy in self._service_status.items() if not healthy
        ]

        return {
            "degraded": True,
            "unavailable_services": unavailable_services,
            "available_capabilities": self.get_available_capabilities(),
            "message_he": "חלק מהשירותים אינם זמינים כרגע. אנו מטפלים בבעיה.",
            "message_en": "Some services are currently unavailable. We are working on it.",
        }


# Pre-configured fallback chains for banking chatbot

def create_llm_fallback_chain() -> FallbackChain[str]:
    """Create fallback chain for LLM responses."""
    chain = FallbackChain[str](strategy=FallbackStrategy.FIRST_SUCCESS)
    chain.set_default(
        "אני מתנצל, אך אינני יכול לעבד את הבקשה כרגע. "
        "אנא נסה שוב מאוחר יותר או פנה לנציג אנושי."
    )
    return chain


def create_cache_fallback_chain() -> FallbackChain[Any]:
    """Create fallback chain for cache operations."""
    chain = FallbackChain[Any](strategy=FallbackStrategy.FIRST_SUCCESS)
    chain.set_default(None)  # No cache is ok, continue without
    return chain


def create_knowledge_base_fallback_chain() -> FallbackChain[List[Dict[str, Any]]]:
    """Create fallback chain for knowledge base queries."""
    chain = FallbackChain[List[Dict[str, Any]]](
        strategy=FallbackStrategy.FIRST_SUCCESS
    )
    chain.set_default([])  # Empty results if KB unavailable
    return chain
