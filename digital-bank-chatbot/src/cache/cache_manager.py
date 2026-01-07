"""
Cache Manager for Digital Bank Chatbot.

Implements multi-layer caching strategy:
1. In-memory LRU cache (hot data)
2. Redis semantic cache (distributed)
3. DynamoDB persistence (sessions, history)
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
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
    dynamodb_table: str = "chatbot-sessions"
    dynamodb_region: str = "us-east-1"
    default_ttl: int = 3600  # 1 hour
    semantic_cache_ttl: int = 86400  # 24 hours
    session_ttl: int = 1800  # 30 minutes
    similarity_threshold: float = 0.95


@dataclass
class SemanticCacheResult:
    """Result from semantic cache lookup."""
    query: str
    response: str
    similarity: float
    cached_at: datetime


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
    """
    Simple in-memory cache with TTL support.

    Used for hot data with very short TTL.
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 60):
        """Initialize in-memory cache."""
        self._cache: Dict[str, tuple] = {}  # key -> (value, expiry)
        self._max_size = max_size
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self._cache:
            value, expiry = self._cache[key]
            if expiry > time.time():
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        if len(self._cache) >= self._max_size:
            self._evict_expired()

        expiry = time.time() + (ttl or self._default_ttl)
        self._cache[key] = (value, expiry)

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def _evict_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, (_, exp) in self._cache.items() if exp <= now]
        for key in expired:
            del self._cache[key]

        # If still too many, remove oldest
        if len(self._cache) >= self._max_size:
            # Sort by expiry and remove oldest quarter
            sorted_items = sorted(self._cache.items(), key=lambda x: x[1][1])
            to_remove = len(sorted_items) // 4
            for key, _ in sorted_items[:to_remove]:
                del self._cache[key]


class RedisCache:
    """
    Redis-based distributed cache.

    Provides:
    - Response caching
    - Semantic similarity cache
    - Rate limiting support
    """

    def __init__(self, config: CacheConfig):
        """Initialize Redis cache."""
        self.config = config
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Redis client."""
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
        """Get value from Redis."""
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in Redis."""
        try:
            return self.client.setex(
                key,
                ttl or self.config.default_ttl,
                value
            )
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False

    async def incr(self, key: str, ttl: Optional[int] = None) -> int:
        """Increment counter (for rate limiting)."""
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

    def exists(self, key: str) -> int:
        return 1 if key in self._data else 0

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
    """
    DynamoDB-based persistent storage.

    Stores:
    - Session data
    - Conversation history
    - User preferences
    """

    def __init__(self, config: CacheConfig):
        """Initialize DynamoDB store."""
        self.config = config
        self._client = None
        self._table = None

    @property
    def client(self):
        """Lazy initialization of DynamoDB client."""
        if self._client is None:
            boto_config = Config(
                region_name=self.config.dynamodb_region,
                retries={"max_attempts": 3, "mode": "adaptive"},
            )
            self._client = boto3.resource("dynamodb", config=boto_config)
        return self._client

    @property
    def table(self):
        """Get DynamoDB table."""
        if self._table is None:
            self._table = self.client.Table(self.config.dynamodb_table)
        return self._table

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session data."""
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
        """Save session data."""
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
            await loop.run_in_executor(
                None,
                lambda: self.table.put_item(Item=item)
            )
            return True

        except Exception as e:
            logger.error(f"DynamoDB save_session error: {e}")
            return False

    async def delete_session(self, session_id: str) -> bool:
        """Delete session."""
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
    """
    Unified cache manager combining all cache layers.
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialize cache manager."""
        self.config = config or CacheConfig()
        self.memory_cache = InMemoryCache()
        self.redis_cache = RedisCache(self.config)
        self.dynamodb_store = DynamoDBStore(self.config)
        self._embedding_client = None

    def generate_key(
        self,
        query: str,
        user_id: Optional[str] = None,
        intent: Optional[str] = None
    ) -> str:
        """
        Generate cache key from query.

        Args:
            query: User query.
            user_id: Optional user ID for personalized caching.
            intent: Optional intent for grouping.

        Returns:
            Cache key string.
        """
        # Normalize query
        normalized = query.lower().strip()

        # Create key components
        components = [normalized]
        if user_id:
            components.append(f"user:{user_id}")
        if intent:
            components.append(f"intent:{intent}")

        # Hash for fixed-length key
        key_data = "|".join(components)
        hash_val = hashlib.sha256(key_data.encode()).hexdigest()[:16]

        prefix = "response" if not user_id else "personal"
        return f"{prefix}:{hash_val}"

    async def get(self, key: str) -> Optional[str]:
        """
        Get value from cache (checking all layers).

        Args:
            key: Cache key.

        Returns:
            Cached value or None.
        """
        # Check memory cache first
        value = self.memory_cache.get(key)
        if value is not None:
            logger.debug(f"Memory cache hit: {key}")
            return value

        # Check Redis
        value = await self.redis_cache.get(key)
        if value is not None:
            logger.debug(f"Redis cache hit: {key}")
            # Promote to memory cache
            self.memory_cache.set(key, value)
            return value

        return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache (all layers).

        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Time-to-live in seconds.

        Returns:
            Success status.
        """
        ttl = ttl or self.config.default_ttl

        # Set in memory cache (shorter TTL)
        self.memory_cache.set(key, value, min(ttl, 300))

        # Set in Redis
        return await self.redis_cache.set(key, value, ttl)

    async def semantic_search(
        self,
        query: str
    ) -> Optional[SemanticCacheResult]:
        """
        Search for semantically similar cached responses.

        Uses embedding similarity to find matching queries.

        Args:
            query: User query.

        Returns:
            SemanticCacheResult if found with high similarity.
        """
        # This would typically use vector similarity search
        # For now, implement simple hash-based lookup
        # In production, use Redis Search or OpenSearch

        key = f"semantic:{hashlib.sha256(query.lower().encode()).hexdigest()[:16]}"
        cached = await self.redis_cache.get(key)

        if cached:
            try:
                data = json.loads(cached)
                return SemanticCacheResult(
                    query=data["query"],
                    response=data["response"],
                    similarity=1.0,  # Exact match
                    cached_at=datetime.fromisoformat(data["cached_at"])
                )
            except (json.JSONDecodeError, KeyError):
                pass

        return None

    async def add_semantic_entry(
        self,
        query: str,
        response: str
    ) -> bool:
        """
        Add entry to semantic cache.

        Args:
            query: User query.
            response: Response to cache.

        Returns:
            Success status.
        """
        key = f"semantic:{hashlib.sha256(query.lower().encode()).hexdigest()[:16]}"
        data = {
            "query": query,
            "response": response,
            "cached_at": datetime.utcnow().isoformat()
        }
        return await self.redis_cache.set(
            key,
            json.dumps(data),
            self.config.semantic_cache_ttl
        )

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session data."""
        return await self.dynamodb_store.get_session(session_id)

    async def save_session(self, session: SessionData) -> bool:
        """Save session data."""
        return await self.dynamodb_store.save_session(session)

    async def check_rate_limit(
        self,
        user_id: str,
        endpoint: str,
        limit: int = 100,
        window: int = 60
    ) -> tuple[bool, int]:
        """
        Check if user is within rate limit.

        Args:
            user_id: User identifier.
            endpoint: Endpoint being accessed.
            limit: Maximum requests per window.
            window: Time window in seconds.

        Returns:
            Tuple of (allowed, remaining_requests).
        """
        key = f"ratelimit:{user_id}:{endpoint}"
        count = await self.redis_cache.incr(key, window)
        allowed = count <= limit
        remaining = max(0, limit - count)
        return allowed, remaining

    async def invalidate_user_cache(self, user_id: str) -> int:
        """
        Invalidate all cached data for a user.

        Args:
            user_id: User identifier.

        Returns:
            Number of keys invalidated.
        """
        # In production, use Redis SCAN to find matching keys
        # For now, this is a placeholder
        logger.info(f"Invalidating cache for user: {user_id}")
        return 0
