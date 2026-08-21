"""
Cache Manager for USA Property Finder Assistant.

Implements a multi-layer caching strategy:
1. In-memory LRU cache (hot data - e.g., repeated searches within a session)
2. Redis distributed cache (search results, AVM estimates, market data)
3. DynamoDB persistence (sessions, saved searches)

Property/market data changes frequently, so TTLs are intentionally shorter
than typical chatbot response caches.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Cache configuration."""
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    dynamodb_table: str = "property-finder-sessions"
    dynamodb_region: str = "us-east-1"
    default_ttl: int = 3600  # 1 hour
    search_results_ttl: int = 900  # 15 minutes - listings change often
    valuation_ttl: int = 86400  # 24 hours - AVM data updates daily
    session_ttl: int = 1800  # 30 minutes


@dataclass
class SessionData:
    """Session data structure."""
    session_id: str
    user_id: str
    messages: List[Dict[str, Any]]
    context: Dict[str, Any]
    created_at: datetime
    last_activity: datetime
    metadata: Dict[str, Any]


class InMemoryCache:
    """Simple in-memory cache with TTL support for hot data."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 60):
        self._cache: Dict[str, tuple] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, expiry = self._cache[key]
            if expiry > time.time():
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if len(self._cache) >= self._max_size:
            self._evict_expired()
        expiry = time.time() + (ttl or self._default_ttl)
        self._cache[key] = (value, expiry)

    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, (_, exp) in self._cache.items() if exp <= now]
        for key in expired:
            del self._cache[key]
        if len(self._cache) >= self._max_size:
            sorted_items = sorted(self._cache.items(), key=lambda x: x[1][1])
            to_remove = len(sorted_items) // 4
            for key, _ in sorted_items[:to_remove]:
                del self._cache[key]


class RedisCache:
    """Redis-based distributed cache."""

    def __init__(self, config: CacheConfig):
        self.config = config
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import redis
                self._client = redis.Redis(
                    host=self.config.redis_host,
                    port=self.config.redis_port,
                    db=self.config.redis_db,
                    password=self.config.redis_password,
                    decode_responses=True,
                )
            except ImportError:
                logger.warning("Redis not available, using mock client")
                self._client = MockRedisClient()
        return self._client

    async def get(self, key: str) -> Optional[str]:
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        try:
            return self.client.setex(key, ttl or self.config.default_ttl, value)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    async def incr(self, key: str, ttl: Optional[int] = None) -> int:
        try:
            pipe = self.client.pipeline()
            pipe.incr(key)
            if ttl:
                pipe.expire(key, ttl)
            results = pipe.execute()
            return results[0]
        except Exception as e:
            logger.error(f"Redis incr error: {e}")
            return 0


class MockRedisClient:
    """Mock Redis client for development/testing."""

    def __init__(self):
        self._data = {}
        self._expiry = {}

    def get(self, key: str) -> Optional[str]:
        if key in self._expiry and self._expiry[key] < time.time():
            del self._data[key]
            del self._expiry[key]
            return None
        return self._data.get(key)

    def setex(self, key: str, ttl: int, value: str) -> bool:
        self._data[key] = value
        self._expiry[key] = time.time() + ttl
        return True

    def delete(self, key: str) -> int:
        if key in self._data:
            del self._data[key]
            self._expiry.pop(key, None)
            return 1
        return 0

    def pipeline(self):
        return MockPipeline(self)


class MockPipeline:
    """Mock Redis pipeline."""

    def __init__(self, client):
        self.client = client
        self.commands = []

    def incr(self, key: str):
        self.commands.append(("incr", key))
        return self

    def expire(self, key: str, ttl: int):
        self.commands.append(("expire", key, ttl))
        return self

    def execute(self):
        results = []
        for cmd in self.commands:
            if cmd[0] == "incr":
                key = cmd[1]
                val = int(self.client._data.get(key, 0)) + 1
                self.client._data[key] = str(val)
                results.append(val)
            elif cmd[0] == "expire":
                key, ttl = cmd[1], cmd[2]
                self.client._expiry[key] = time.time() + ttl
                results.append(True)
        return results


class DynamoDBStore:
    """DynamoDB-based persistent session storage."""

    def __init__(self, config: CacheConfig):
        self.config = config
        self._client = None
        self._table = None

    @property
    def client(self):
        if self._client is None:
            boto_config = Config(
                region_name=self.config.dynamodb_region,
                retries={"max_attempts": 3, "mode": "adaptive"},
            )
            self._client = boto3.resource("dynamodb", config=boto_config)
        return self._client

    @property
    def table(self):
        if self._table is None:
            self._table = self.client.Table(self.config.dynamodb_table)
        return self._table

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.table.get_item(Key={"session_id": session_id})
            )
            item = response.get("Item")
            if not item:
                return None

            return SessionData(
                session_id=item["session_id"],
                user_id=item.get("user_id", ""),
                messages=json.loads(item.get("messages", "[]")),
                context=json.loads(item.get("context", "{}")),
                created_at=datetime.fromisoformat(item["created_at"]),
                last_activity=datetime.fromisoformat(item["last_activity"]),
                metadata=json.loads(item.get("metadata", "{}"))
            )
        except Exception as e:
            logger.error(f"DynamoDB get_session error: {e}")
            return None

    async def save_session(self, session: SessionData) -> bool:
        import asyncio

        try:
            item = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "messages": json.dumps(session.messages),
                "context": json.dumps(session.context),
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "metadata": json.dumps(session.metadata),
                "ttl": int((session.last_activity + timedelta(
                    seconds=self.config.session_ttl
                )).timestamp())
            }
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.table.put_item(Item=item))
            return True
        except Exception as e:
            logger.error(f"DynamoDB save_session error: {e}")
            return False

    async def delete_session(self, session_id: str) -> bool:
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.table.delete_item(Key={"session_id": session_id})
            )
            return True
        except Exception as e:
            logger.error(f"DynamoDB delete_session error: {e}")
            return False


class CacheManager:
    """Unified cache manager combining all cache layers."""

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.memory_cache = InMemoryCache()
        self.redis_cache = RedisCache(self.config)
        self.dynamodb_store = DynamoDBStore(self.config)

    def generate_key(
        self,
        query: str,
        user_id: Optional[str] = None,
        intent: Optional[str] = None
    ) -> str:
        """Generate cache key from query."""
        normalized = query.lower().strip()
        components = [normalized]
        if user_id:
            components.append(f"user:{user_id}")
        if intent:
            components.append(f"intent:{intent}")

        key_data = "|".join(components)
        hash_val = hashlib.sha256(key_data.encode()).hexdigest()[:16]
        prefix = "response" if not user_id else "personal"
        return f"{prefix}:{hash_val}"

    def generate_search_key(self, filters: Dict[str, Any]) -> str:
        """Generate a stable cache key for a set of search filters."""
        normalized = json.dumps(filters, sort_keys=True, default=str)
        hash_val = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return f"search:{hash_val}"

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache (checking all layers)."""
        value = self.memory_cache.get(key)
        if value is not None:
            logger.debug(f"Memory cache hit: {key}")
            return value

        value = await self.redis_cache.get(key)
        if value is not None:
            logger.debug(f"Redis cache hit: {key}")
            self.memory_cache.set(key, value)
            return value

        return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value in cache (all layers)."""
        ttl = ttl or self.config.default_ttl
        self.memory_cache.set(key, value, min(ttl, 300))
        return await self.redis_cache.set(key, value, ttl)

    async def get_search_results(self, filters: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Get cached search results for a set of filters."""
        key = self.generate_search_key(filters)
        cached = await self.get(key)
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                return None
        return None

    async def set_search_results(
        self, filters: Dict[str, Any], results: List[Dict[str, Any]]
    ) -> bool:
        """Cache search results (short TTL since listings change frequently)."""
        key = self.generate_search_key(filters)
        return await self.set(
            key, json.dumps(results, default=str), self.config.search_results_ttl
        )

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        return await self.dynamodb_store.get_session(session_id)

    async def save_session(self, session: SessionData) -> bool:
        return await self.dynamodb_store.save_session(session)

    async def check_rate_limit(
        self, user_id: str, endpoint: str, limit: int = 100, window: int = 60
    ) -> tuple:
        """Check if user is within rate limit."""
        key = f"ratelimit:{user_id}:{endpoint}"
        count = await self.redis_cache.incr(key, window)
        allowed = count <= limit
        remaining = max(0, limit - count)
        return allowed, remaining
