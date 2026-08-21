"""
Memory Management System for USA Property Finder Assistant.

Implements:
- Short-term memory (within session - e.g., "the second listing", active search filters)
- Long-term memory (across sessions - e.g., learned buyer preferences)
- Semantic memory (facts about the buyer: budget, must-haves, deal-breakers)
- Episodic memory (past interactions: searches run, properties viewed, tours booked)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memories."""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"


class MemoryImportance(str, Enum):
    """Importance levels for memory items."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MemoryItem:
    """Single memory item."""
    memory_id: str
    user_id: str
    memory_type: MemoryType
    content: str
    importance: MemoryImportance = MemoryImportance.MEDIUM
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    related_intents: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    access_count: int = 0
    source_session_id: Optional[str] = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def touch(self) -> None:
        self.last_accessed = datetime.utcnow()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "user_id": self.user_id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "importance": self.importance.value,
            "context": self.context,
            "tags": self.tags,
            "related_intents": self.related_intents,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "access_count": self.access_count,
            "source_session_id": self.source_session_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        return cls(
            memory_id=data["memory_id"],
            user_id=data["user_id"],
            memory_type=MemoryType(data["memory_type"]),
            content=data["content"],
            importance=MemoryImportance(data.get("importance", "medium")),
            context=data.get("context", {}),
            tags=data.get("tags", []),
            related_intents=data.get("related_intents", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            access_count=data.get("access_count", 0),
            source_session_id=data.get("source_session_id"),
        )


class ShortTermMemory:
    """
    Short-term memory for the current session.

    Used for things like: "show me more like the third one" (needs to know
    what the active search results were) or "what about a bigger lot"
    (needs the active search filters).
    """

    def __init__(self, max_items: int = 100, ttl_minutes: int = 30):
        self.max_items = max_items
        self.ttl_minutes = ttl_minutes
        self._memory: Dict[str, Dict[str, MemoryItem]] = {}

    def store(
        self,
        session_id: str,
        key: str,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        importance: MemoryImportance = MemoryImportance.MEDIUM
    ) -> MemoryItem:
        if session_id not in self._memory:
            self._memory[session_id] = {}

        memory_id = f"stm_{session_id}_{key}_{datetime.utcnow().timestamp()}"
        item = MemoryItem(
            memory_id=memory_id,
            user_id=session_id,
            memory_type=MemoryType.SHORT_TERM,
            content=content,
            importance=importance,
            context=context or {},
            expires_at=datetime.utcnow() + timedelta(minutes=self.ttl_minutes),
            source_session_id=session_id,
        )
        self._memory[session_id][key] = item
        self._cleanup_session(session_id)
        return item

    def retrieve(self, session_id: str, key: Optional[str] = None) -> Optional[MemoryItem]:
        if session_id not in self._memory:
            return None

        if key:
            item = self._memory[session_id].get(key)
            if item and not item.is_expired():
                item.touch()
                return item
            return None

        items = [item for item in self._memory[session_id].values() if not item.is_expired()]
        if items:
            latest = max(items, key=lambda x: x.created_at)
            latest.touch()
            return latest
        return None

    def retrieve_all(self, session_id: str) -> List[MemoryItem]:
        if session_id not in self._memory:
            return []
        return [item for item in self._memory[session_id].values() if not item.is_expired()]

    def forget(self, session_id: str, key: Optional[str] = None) -> None:
        if session_id not in self._memory:
            return
        if key:
            self._memory[session_id].pop(key, None)
        else:
            del self._memory[session_id]

    def _cleanup_session(self, session_id: str) -> None:
        if session_id not in self._memory:
            return
        self._memory[session_id] = {
            k: v for k, v in self._memory[session_id].items() if not v.is_expired()
        }
        while len(self._memory[session_id]) > self.max_items:
            lowest = min(
                self._memory[session_id].items(),
                key=lambda x: (x[1].importance.value, x[1].created_at)
            )
            del self._memory[session_id][lowest[0]]


class LongTermMemory:
    """
    Long-term memory persisted across sessions: learned buyer preferences,
    deal-breakers, and history of properties viewed / tours booked.
    """

    def __init__(self, dynamodb_table: Optional[str] = None):
        self.dynamodb_table = dynamodb_table or "property-finder-memories"
        self._client = None

    @property
    def dynamodb(self):
        if self._client is None:
            import boto3
            self._client = boto3.resource("dynamodb").Table(self.dynamodb_table)
        return self._client

    async def store(
        self,
        user_id: str,
        content: str,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        related_intents: Optional[List[str]] = None,
        ttl_days: Optional[int] = None
    ) -> MemoryItem:
        import asyncio
        import uuid

        memory_id = f"ltm_{user_id}_{uuid.uuid4().hex[:8]}"
        expires_at = datetime.utcnow() + timedelta(days=ttl_days) if ttl_days else None

        item = MemoryItem(
            memory_id=memory_id,
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            importance=importance,
            context=context or {},
            tags=tags or [],
            related_intents=related_intents or [],
            expires_at=expires_at,
        )

        try:
            data = item.to_dict()
            if expires_at:
                data["ttl"] = int(expires_at.timestamp())

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.dynamodb.put_item(Item=data))
            logger.info(f"Stored long-term memory for user {user_id}: {memory_id}")
            return item
        except Exception as e:
            logger.error(f"Error storing long-term memory: {e}")
            raise

    async def retrieve(
        self,
        user_id: str,
        memory_type: Optional[MemoryType] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[MemoryItem]:
        import asyncio

        try:
            filter_expr = "user_id = :uid"
            expr_values: Dict[str, Any] = {":uid": user_id}

            if memory_type:
                filter_expr += " AND memory_type = :mtype"
                expr_values[":mtype"] = memory_type.value

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.dynamodb.scan(
                    FilterExpression=filter_expr,
                    ExpressionAttributeValues=expr_values,
                    Limit=limit * 2
                )
            )

            items = []
            for data in response.get("Items", []):
                item = MemoryItem.from_dict(data)
                if not item.is_expired():
                    if tags and not any(t in item.tags for t in tags):
                        continue
                    items.append(item)

            items.sort(key=lambda x: (x.importance.value, x.last_accessed), reverse=True)
            return items[:limit]

        except Exception as e:
            logger.error(f"Error retrieving long-term memories: {e}")
            return []


class MemoryManager:
    """Unified memory manager combining short-term and long-term memory."""

    def __init__(
        self,
        dynamodb_table: Optional[str] = None,
        short_term_ttl_minutes: int = 30,
        enable_long_term: bool = True
    ):
        self.short_term = ShortTermMemory(ttl_minutes=short_term_ttl_minutes)
        self.long_term = LongTermMemory(dynamodb_table) if enable_long_term else None
        self.enable_long_term = enable_long_term

    async def remember(
        self,
        user_id: str,
        session_id: str,
        key: str,
        content: str,
        persist: bool = False,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        related_intents: Optional[List[str]] = None
    ) -> MemoryItem:
        item = self.short_term.store(
            session_id=session_id, key=key, content=content,
            context=context, importance=importance
        )
        item.tags = tags or []
        item.related_intents = related_intents or []

        if persist and self.long_term:
            await self.long_term.store(
                user_id=user_id, content=content, importance=importance,
                context=context, tags=tags, related_intents=related_intents,
            )

        return item

    def remember_active_search(
        self, session_id: str, filters: Dict[str, Any], results: List[Dict[str, Any]]
    ) -> None:
        """Store the active search context so follow-ups like 'the second one' resolve."""
        self.short_term.store(
            session_id=session_id,
            key="active_search",
            content=f"Active search with {len(results)} results",
            context={"filters": filters, "results": results},
            importance=MemoryImportance.HIGH,
        )

    def get_active_search(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the active search context (filters + results) for a session."""
        item = self.short_term.retrieve(session_id, key="active_search")
        return item.context if item else None

    def remember_focused_property(self, session_id: str, property_id: str) -> None:
        """Track which property the conversation is currently focused on."""
        self.short_term.store(
            session_id=session_id,
            key="focused_property",
            content=property_id,
            importance=MemoryImportance.HIGH,
        )

    def get_focused_property(self, session_id: str) -> Optional[str]:
        """Get the property_id the conversation is currently focused on, if any."""
        item = self.short_term.retrieve(session_id, key="focused_property")
        return item.content if item else None

    async def learn_preference(
        self,
        user_id: str,
        preference_type: str,
        value: str,
        confidence: float = 1.0,
    ) -> None:
        """Learn a buyer preference (e.g., 'must_have: garage', 'budget_max: 500000')."""
        if not self.long_term:
            return

        await self.long_term.store(
            user_id=user_id,
            content=f"{preference_type}: {value}",
            memory_type=MemoryType.SEMANTIC,
            importance=MemoryImportance.HIGH,
            context={"preference_type": preference_type, "value": value, "confidence": confidence},
            tags=["preference", preference_type],
        )

    async def get_learned_preferences(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all learned preferences for a buyer."""
        if not self.long_term:
            return []
        memories = await self.long_term.retrieve(
            user_id=user_id, memory_type=MemoryType.SEMANTIC, limit=50
        )
        return [m.context for m in memories if m.context.get("preference_type")]

    async def record_interaction(
        self,
        user_id: str,
        session_id: str,
        event_type: str,
        summary: str,
        intent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record an interaction as episodic memory (e.g., 'viewed 123 Main St', 'booked tour')."""
        if not self.long_term:
            return

        await self.long_term.store(
            user_id=user_id,
            content=summary,
            memory_type=MemoryType.EPISODIC,
            importance=MemoryImportance.MEDIUM,
            context={"event_type": event_type, "details": details or {}},
            related_intents=[intent] if intent else [],
            tags=["episode", event_type],
        )

    def forget_session(self, session_id: str) -> None:
        """Clear all short-term memories for a session."""
        self.short_term.forget(session_id)


# Singleton instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get singleton memory manager."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
