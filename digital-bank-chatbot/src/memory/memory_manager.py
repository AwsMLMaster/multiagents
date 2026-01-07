"""
Memory Management System for Digital Bank Chatbot.

Implements:
- Short-term memory (within session)
- Long-term memory (across sessions)
- Semantic memory (learned facts about user)
- Episodic memory (past interactions)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# Memory Types
# =============================================================================

class MemoryType(str, Enum):
    """Types of memories."""
    SHORT_TERM = "short_term"  # Current session
    LONG_TERM = "long_term"  # Across sessions
    SEMANTIC = "semantic"  # Facts about user
    EPISODIC = "episodic"  # Specific interactions
    PROCEDURAL = "procedural"  # Learned patterns


class MemoryImportance(str, Enum):
    """Importance levels for memory items."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# Memory Items
# =============================================================================

@dataclass
class MemoryItem:
    """
    Single memory item.
    """
    memory_id: str
    user_id: str
    memory_type: MemoryType
    content: str
    importance: MemoryImportance = MemoryImportance.MEDIUM

    # Context
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    related_intents: List[str] = field(default_factory=list)

    # Temporal
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    # Retrieval
    access_count: int = 0
    relevance_score: float = 1.0

    # Source
    source_session_id: Optional[str] = None
    source_message_id: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if memory has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def touch(self) -> None:
        """Update last accessed time and increment access count."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
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
            "relevance_score": self.relevance_score,
            "source_session_id": self.source_session_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """Deserialize from dictionary."""
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
            relevance_score=data.get("relevance_score", 1.0),
            source_session_id=data.get("source_session_id"),
        )


@dataclass
class SemanticFact:
    """
    A semantic fact learned about the user.
    """
    fact_id: str
    user_id: str
    fact_type: str  # e.g., "preference", "behavior", "relationship", "financial"
    subject: str  # What the fact is about
    predicate: str  # The relationship/action
    object: str  # The value/target

    confidence: float = 1.0
    source: str = "inferred"  # inferred, stated, observed
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_confirmed: datetime = field(default_factory=datetime.utcnow)
    confirmation_count: int = 1

    def to_natural_language(self) -> str:
        """Convert fact to natural language."""
        return f"{self.subject} {self.predicate} {self.object}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "fact_id": self.fact_id,
            "user_id": self.user_id,
            "fact_type": self.fact_type,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "last_confirmed": self.last_confirmed.isoformat(),
            "confirmation_count": self.confirmation_count,
        }


@dataclass
class EpisodicMemory:
    """
    Memory of a specific interaction/event.
    """
    episode_id: str
    user_id: str
    session_id: str

    # Event details
    event_type: str  # e.g., "transaction", "inquiry", "complaint", "request"
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)

    # Outcome
    outcome: str = "success"  # success, failure, partial, pending
    user_satisfaction: Optional[int] = None  # 1-5 rating if available

    # Context
    intent: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)

    # Temporal
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "episode_id": self.episode_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "summary": self.summary,
            "details": self.details,
            "outcome": self.outcome,
            "user_satisfaction": self.user_satisfaction,
            "intent": self.intent,
            "entities": self.entities,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Short-Term Memory (Session Memory)
# =============================================================================

class ShortTermMemory:
    """
    Short-term memory for current session.

    Stores:
    - Current conversation context
    - Working memory for multi-turn interactions
    - Temporary state
    """

    def __init__(self, max_items: int = 100, ttl_minutes: int = 30):
        """Initialize short-term memory."""
        self.max_items = max_items
        self.ttl_minutes = ttl_minutes
        self._memory: Dict[str, Dict[str, MemoryItem]] = {}  # session_id -> {key: item}

    def store(
        self,
        session_id: str,
        key: str,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        importance: MemoryImportance = MemoryImportance.MEDIUM
    ) -> MemoryItem:
        """
        Store item in short-term memory.

        Args:
            session_id: Session identifier.
            key: Memory key.
            content: Memory content.
            context: Optional context.
            importance: Importance level.

        Returns:
            Created MemoryItem.
        """
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

        # Enforce max items
        self._cleanup_session(session_id)

        return item

    def retrieve(
        self,
        session_id: str,
        key: Optional[str] = None
    ) -> Optional[MemoryItem]:
        """
        Retrieve from short-term memory.

        Args:
            session_id: Session identifier.
            key: Optional specific key.

        Returns:
            MemoryItem or None.
        """
        if session_id not in self._memory:
            return None

        if key:
            item = self._memory[session_id].get(key)
            if item and not item.is_expired():
                item.touch()
                return item
            return None

        # Return most recent non-expired item
        items = [
            item for item in self._memory[session_id].values()
            if not item.is_expired()
        ]
        if items:
            latest = max(items, key=lambda x: x.created_at)
            latest.touch()
            return latest
        return None

    def retrieve_all(self, session_id: str) -> List[MemoryItem]:
        """Get all non-expired items for session."""
        if session_id not in self._memory:
            return []

        return [
            item for item in self._memory[session_id].values()
            if not item.is_expired()
        ]

    def retrieve_by_intent(
        self,
        session_id: str,
        intent: str
    ) -> List[MemoryItem]:
        """Get memories related to an intent."""
        if session_id not in self._memory:
            return []

        return [
            item for item in self._memory[session_id].values()
            if not item.is_expired() and intent in item.related_intents
        ]

    def forget(self, session_id: str, key: Optional[str] = None) -> None:
        """Remove items from memory."""
        if session_id not in self._memory:
            return

        if key:
            self._memory[session_id].pop(key, None)
        else:
            del self._memory[session_id]

    def _cleanup_session(self, session_id: str) -> None:
        """Clean up expired items and enforce max size."""
        if session_id not in self._memory:
            return

        # Remove expired
        self._memory[session_id] = {
            k: v for k, v in self._memory[session_id].items()
            if not v.is_expired()
        }

        # Enforce max items (remove lowest importance first)
        while len(self._memory[session_id]) > self.max_items:
            lowest = min(
                self._memory[session_id].items(),
                key=lambda x: (x[1].importance.value, x[1].created_at)
            )
            del self._memory[session_id][lowest[0]]


# =============================================================================
# Long-Term Memory
# =============================================================================

class LongTermMemory:
    """
    Long-term memory persisted across sessions.

    Stores:
    - Semantic facts about user
    - Episodic memories (past interactions)
    - Learned preferences
    """

    def __init__(self, dynamodb_table: Optional[str] = None):
        """Initialize long-term memory."""
        self.dynamodb_table = dynamodb_table or "user-memories"
        self._client = None
        self._cache: Dict[str, List[MemoryItem]] = {}

    @property
    def dynamodb(self):
        """Lazy initialization of DynamoDB client."""
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
        """
        Store item in long-term memory.

        Args:
            user_id: User identifier.
            content: Memory content.
            memory_type: Type of memory.
            importance: Importance level.
            context: Optional context.
            tags: Optional tags.
            related_intents: Optional related intents.
            ttl_days: Optional TTL in days.

        Returns:
            Created MemoryItem.
        """
        import asyncio
        import uuid

        memory_id = f"ltm_{user_id}_{uuid.uuid4().hex[:8]}"

        expires_at = None
        if ttl_days:
            expires_at = datetime.utcnow() + timedelta(days=ttl_days)

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
            # Add TTL for DynamoDB
            if expires_at:
                data["ttl"] = int(expires_at.timestamp())

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.dynamodb.put_item(Item=data)
            )

            # Update cache
            if user_id not in self._cache:
                self._cache[user_id] = []
            self._cache[user_id].append(item)

            logger.info(f"Stored long-term memory for user {user_id}: {memory_id}")
            return item

        except Exception as e:
            logger.error(f"Error storing long-term memory: {e}")
            raise

    async def retrieve(
        self,
        user_id: str,
        query: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[MemoryItem]:
        """
        Retrieve memories for a user.

        Args:
            user_id: User identifier.
            query: Optional search query.
            memory_type: Optional type filter.
            tags: Optional tag filter.
            limit: Maximum results.

        Returns:
            List of MemoryItems.
        """
        import asyncio

        try:
            # Build filter expression
            filter_expr = "user_id = :uid"
            expr_values = {":uid": user_id}

            if memory_type:
                filter_expr += " AND memory_type = :mtype"
                expr_values[":mtype"] = memory_type.value

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.dynamodb.scan(
                    FilterExpression=filter_expr,
                    ExpressionAttributeValues=expr_values,
                    Limit=limit * 2  # Get more, then filter
                )
            )

            items = []
            for data in response.get("Items", []):
                item = MemoryItem.from_dict(data)
                if not item.is_expired():
                    # Tag filter
                    if tags and not any(t in item.tags for t in tags):
                        continue
                    items.append(item)

            # Sort by relevance and recency
            items.sort(key=lambda x: (x.importance.value, x.last_accessed), reverse=True)

            # If query provided, do simple relevance scoring
            if query:
                query_lower = query.lower()
                for item in items:
                    if query_lower in item.content.lower():
                        item.relevance_score += 0.5

                items.sort(key=lambda x: x.relevance_score, reverse=True)

            return items[:limit]

        except Exception as e:
            logger.error(f"Error retrieving long-term memories: {e}")
            return []

    async def store_fact(self, fact: SemanticFact) -> None:
        """Store a semantic fact."""
        await self.store(
            user_id=fact.user_id,
            content=fact.to_natural_language(),
            memory_type=MemoryType.SEMANTIC,
            importance=MemoryImportance.HIGH,
            context={
                "fact_type": fact.fact_type,
                "subject": fact.subject,
                "predicate": fact.predicate,
                "object": fact.object,
                "confidence": fact.confidence,
            },
            tags=["fact", fact.fact_type],
        )

    async def store_episode(self, episode: EpisodicMemory) -> None:
        """Store an episodic memory."""
        await self.store(
            user_id=episode.user_id,
            content=episode.summary,
            memory_type=MemoryType.EPISODIC,
            importance=MemoryImportance.MEDIUM,
            context={
                "event_type": episode.event_type,
                "outcome": episode.outcome,
                "details": episode.details,
            },
            related_intents=[episode.intent] if episode.intent else [],
            tags=["episode", episode.event_type],
        )

    async def get_user_facts(self, user_id: str) -> List[SemanticFact]:
        """Get all semantic facts about a user."""
        memories = await self.retrieve(
            user_id=user_id,
            memory_type=MemoryType.SEMANTIC,
            limit=50
        )

        facts = []
        for mem in memories:
            if mem.context.get("fact_type"):
                facts.append(SemanticFact(
                    fact_id=mem.memory_id,
                    user_id=user_id,
                    fact_type=mem.context["fact_type"],
                    subject=mem.context["subject"],
                    predicate=mem.context["predicate"],
                    object=mem.context["object"],
                    confidence=mem.context.get("confidence", 1.0),
                ))

        return facts

    async def get_relevant_history(
        self,
        user_id: str,
        current_intent: str,
        limit: int = 5
    ) -> List[EpisodicMemory]:
        """Get relevant past interactions for current intent."""
        memories = await self.retrieve(
            user_id=user_id,
            memory_type=MemoryType.EPISODIC,
            limit=limit * 2
        )

        # Filter and sort by relevance to current intent
        relevant = [
            m for m in memories
            if current_intent in m.related_intents or
            current_intent.split(".")[0] in [i.split(".")[0] for i in m.related_intents]
        ]

        episodes = []
        for mem in relevant[:limit]:
            episodes.append(EpisodicMemory(
                episode_id=mem.memory_id,
                user_id=user_id,
                session_id=mem.source_session_id or "",
                event_type=mem.context.get("event_type", "unknown"),
                summary=mem.content,
                details=mem.context.get("details", {}),
                outcome=mem.context.get("outcome", "unknown"),
                intent=mem.related_intents[0] if mem.related_intents else None,
                timestamp=mem.created_at,
            ))

        return episodes


# =============================================================================
# Memory Manager (Unified Interface)
# =============================================================================

class MemoryManager:
    """
    Unified memory manager combining short-term and long-term memory.
    """

    def __init__(
        self,
        dynamodb_table: Optional[str] = None,
        short_term_ttl_minutes: int = 30,
        enable_long_term: bool = True
    ):
        """Initialize memory manager."""
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
        """
        Store a memory.

        Args:
            user_id: User identifier.
            session_id: Session identifier.
            key: Memory key.
            content: Memory content.
            persist: Whether to persist to long-term memory.
            importance: Importance level.
            context: Optional context.
            tags: Optional tags.
            related_intents: Optional related intents.

        Returns:
            Created MemoryItem.
        """
        # Always store in short-term
        item = self.short_term.store(
            session_id=session_id,
            key=key,
            content=content,
            context=context,
            importance=importance
        )
        item.tags = tags or []
        item.related_intents = related_intents or []

        # Optionally persist to long-term
        if persist and self.long_term:
            await self.long_term.store(
                user_id=user_id,
                content=content,
                importance=importance,
                context=context,
                tags=tags,
                related_intents=related_intents,
            )

        return item

    async def recall(
        self,
        user_id: str,
        session_id: str,
        query: Optional[str] = None,
        include_long_term: bool = True,
        limit: int = 10
    ) -> List[MemoryItem]:
        """
        Recall memories.

        Args:
            user_id: User identifier.
            session_id: Session identifier.
            query: Optional search query.
            include_long_term: Whether to include long-term memories.
            limit: Maximum results.

        Returns:
            List of relevant MemoryItems.
        """
        memories = []

        # Get short-term memories
        short_term_items = self.short_term.retrieve_all(session_id)
        memories.extend(short_term_items)

        # Get long-term memories
        if include_long_term and self.long_term:
            long_term_items = await self.long_term.retrieve(
                user_id=user_id,
                query=query,
                limit=limit
            )
            memories.extend(long_term_items)

        # Sort by relevance and recency
        memories.sort(
            key=lambda x: (x.relevance_score, x.last_accessed),
            reverse=True
        )

        return memories[:limit]

    async def get_context_for_intent(
        self,
        user_id: str,
        session_id: str,
        intent: str
    ) -> Dict[str, Any]:
        """
        Get relevant context for processing an intent.

        Returns memories and facts relevant to the current intent.
        """
        context = {
            "short_term_memories": [],
            "long_term_memories": [],
            "relevant_facts": [],
            "past_interactions": [],
        }

        # Short-term by intent
        stm_items = self.short_term.retrieve_by_intent(session_id, intent)
        context["short_term_memories"] = [m.content for m in stm_items]

        if self.long_term:
            # Long-term memories
            ltm_items = await self.long_term.retrieve(
                user_id=user_id,
                memory_type=MemoryType.LONG_TERM,
                limit=5
            )
            context["long_term_memories"] = [m.content for m in ltm_items]

            # Semantic facts
            facts = await self.long_term.get_user_facts(user_id)
            context["relevant_facts"] = [f.to_natural_language() for f in facts[:5]]

            # Past interactions with same intent
            episodes = await self.long_term.get_relevant_history(
                user_id=user_id,
                current_intent=intent,
                limit=3
            )
            context["past_interactions"] = [
                {"summary": e.summary, "outcome": e.outcome, "when": e.timestamp.isoformat()}
                for e in episodes
            ]

        return context

    async def learn_fact(
        self,
        user_id: str,
        fact_type: str,
        subject: str,
        predicate: str,
        obj: str,
        confidence: float = 1.0,
        source: str = "stated"
    ) -> None:
        """
        Learn a new fact about the user.

        Args:
            user_id: User identifier.
            fact_type: Type of fact (preference, behavior, etc.)
            subject: Subject of the fact.
            predicate: Relationship/action.
            obj: Object/value.
            confidence: Confidence level (0-1).
            source: Source of the fact (stated, inferred, observed).
        """
        if not self.long_term:
            return

        import uuid

        fact = SemanticFact(
            fact_id=f"fact_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            fact_type=fact_type,
            subject=subject,
            predicate=predicate,
            object=obj,
            confidence=confidence,
            source=source,
        )

        await self.long_term.store_fact(fact)
        logger.info(f"Learned fact for user {user_id}: {fact.to_natural_language()}")

    async def record_interaction(
        self,
        user_id: str,
        session_id: str,
        event_type: str,
        summary: str,
        intent: Optional[str] = None,
        outcome: str = "success",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record an interaction as episodic memory.

        Args:
            user_id: User identifier.
            session_id: Session identifier.
            event_type: Type of event.
            summary: Summary of interaction.
            intent: Related intent.
            outcome: Outcome of interaction.
            details: Additional details.
        """
        if not self.long_term:
            return

        import uuid

        episode = EpisodicMemory(
            episode_id=f"ep_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            summary=summary,
            details=details or {},
            outcome=outcome,
            intent=intent,
        )

        await self.long_term.store_episode(episode)

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
