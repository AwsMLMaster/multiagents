"""
Fallback Pattern Implementation.

Provides graceful degradation when a primary dependency (property data
provider, geocoding, mortgage rates, Bedrock) fails - e.g. falling back to
cached listings or a static mortgage rate table instead of failing the
whole request.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Callable, Generic, List, Optional, TypeVar
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FallbackStrategy(Enum):
    """Fallback behavior strategies."""
    FIRST_SUCCESS = "first_success"
    CACHED = "cached"
    DEFAULT = "default"
    FAIL = "fail"


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
        chain = FallbackChain[list]()
        chain.add_primary(search_live_listings)
        chain.add_fallback("cache", get_cached_listings)
        chain.set_default([])

        result = await chain.execute(location="Austin, TX")
    """

    def __init__(self, strategy: FallbackStrategy = FallbackStrategy.FIRST_SUCCESS, timeout: float = 15.0):
        self.strategy = strategy
        self.timeout = timeout
        self._primary: Optional[Callable[..., T]] = None
        self._fallbacks: List[tuple] = []
        self._default_value: Optional[T] = None

    def add_primary(self, func: Callable[..., T]) -> "FallbackChain[T]":
        self._primary = func
        return self

    def add_fallback(self, name: str, func: Callable[..., T]) -> "FallbackChain[T]":
        self._fallbacks.append((name, func))
        return self

    def set_default(self, value: T) -> "FallbackChain[T]":
        self._default_value = value
        return self

    async def execute(self, *args, **kwargs) -> FallbackResult[T]:
        start_time = datetime.utcnow()

        if self._primary:
            try:
                result = await self._execute_with_timeout(self._primary, *args, **kwargs)
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                return FallbackResult(success=True, value=result, source="primary", latency_ms=latency)
            except Exception as e:
                logger.warning(f"Primary failed: {e}, trying fallbacks")

        for name, fallback_func in self._fallbacks:
            try:
                result = await self._execute_with_timeout(fallback_func, *args, **kwargs)
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.info(f"Fallback '{name}' succeeded")
                return FallbackResult(
                    success=True, value=result, source=name, latency_ms=latency, was_fallback=True
                )
            except Exception as e:
                logger.warning(f"Fallback '{name}' failed: {e}")
                continue

        return self._handle_all_failed(start_time)

    async def _execute_with_timeout(self, func: Callable[..., T], *args, **kwargs) -> T:
        if asyncio.iscoroutinefunction(func):
            return await asyncio.wait_for(func(*args, **kwargs), timeout=self.timeout)
        return func(*args, **kwargs)

    def _handle_all_failed(self, start_time: datetime) -> FallbackResult[T]:
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        if self._default_value is not None:
            return FallbackResult(
                success=True, value=self._default_value, source="default",
                latency_ms=latency, was_fallback=True,
            )

        return FallbackResult(
            success=False, source="none", latency_ms=latency, was_fallback=True,
            error=Exception("All fallback options exhausted"),
        )


def create_search_fallback_chain() -> FallbackChain:
    """Fallback chain for property search: primary live search -> cached results -> empty."""
    chain = FallbackChain(strategy=FallbackStrategy.FIRST_SUCCESS)
    chain.set_default([])
    return chain


def create_mortgage_rates_fallback_chain() -> FallbackChain:
    """Fallback chain for mortgage rates: live provider -> static fallback table."""
    chain = FallbackChain(strategy=FallbackStrategy.FIRST_SUCCESS)
    return chain


def create_llm_fallback_chain() -> FallbackChain:
    """Fallback chain for LLM responses."""
    chain = FallbackChain(strategy=FallbackStrategy.FIRST_SUCCESS)
    chain.set_default(
        "I'm sorry, I couldn't process that request right now. Please try again "
        "in a moment."
    )
    return chain
