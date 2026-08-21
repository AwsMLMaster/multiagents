"""
State management for the USA Property Finder Assistant LangGraph orchestrator.

This module defines the state schema used throughout the multi-agent workflow,
including conversation history, intent tracking, search context, and
buyer preference management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class AgentType(str, Enum):
    """Types of specialized agents in the system."""
    SUPERVISOR = "supervisor"
    RAG = "rag_agent"
    SEARCH = "search_agent"
    PROPERTY_DETAILS = "property_details_agent"
    VALUATION = "valuation_agent"
    MORTGAGE = "mortgage_agent"
    NEIGHBORHOOD = "neighborhood_agent"
    MARKET_TRENDS = "market_trends_agent"
    SCHEDULING = "scheduling_agent"


class IntentCategory(str, Enum):
    """High-level intent categories."""
    SEARCH = "search"
    PROPERTY = "property"
    VALUATION = "valuation"
    MORTGAGE = "mortgage"
    NEIGHBORHOOD = "neighborhood"
    MARKET = "market"
    SCHEDULING = "scheduling"
    RAG = "rag"
    GENERAL = "general"
    UNKNOWN = "unknown"


class GuardrailStatus(str, Enum):
    """Status from guardrail checks."""
    APPROVED = "approved"
    BLOCKED = "blocked"
    WARNING = "warning"


class CacheResult(str, Enum):
    """Result of cache lookup."""
    HIT = "hit"
    MISS = "miss"
    EXPIRED = "expired"


@dataclass
class BuyerProfile:
    """Buyer/renter context used to personalize search and recommendations."""
    user_id: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    preferred_locations: List[str] = field(default_factory=list)
    property_types: List[str] = field(default_factory=list)  # single_family, condo, townhouse, multi_family
    min_bedrooms: Optional[int] = None
    min_bathrooms: Optional[float] = None
    must_haves: List[str] = field(default_factory=list)  # e.g. ["garage", "pool", "pet_friendly"]
    is_pre_approved: bool = False
    pre_approval_amount: Optional[float] = None
    preferred_language: str = "en"
    saved_property_ids: List[str] = field(default_factory=list)
    saved_search_ids: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_context(cls, payload: Dict[str, Any]) -> "BuyerProfile":
        """Create BuyerProfile from a session/user context payload."""
        return cls(
            user_id=payload.get("user_id", ""),
            budget_min=payload.get("budget_min"),
            budget_max=payload.get("budget_max"),
            preferred_locations=payload.get("preferred_locations", []),
            property_types=payload.get("property_types", []),
            min_bedrooms=payload.get("min_bedrooms"),
            min_bathrooms=payload.get("min_bathrooms"),
            must_haves=payload.get("must_haves", []),
            is_pre_approved=payload.get("is_pre_approved", False),
            pre_approval_amount=payload.get("pre_approval_amount"),
            preferred_language=payload.get("preferred_language", "en"),
            saved_property_ids=payload.get("saved_property_ids", []),
            saved_search_ids=payload.get("saved_search_ids", []),
            preferences=payload.get("preferences", {}),
        )


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent_id: str
    category: IntentCategory
    confidence: float
    parameters: Dict[str, Any]
    target_agent: AgentType

    def is_confident(self, threshold: float = 0.85) -> bool:
        """Check if classification confidence meets threshold."""
        return self.confidence >= threshold


@dataclass
class SearchFilters:
    """Structured search filters extracted from a property search request."""
    location: Optional[str] = None  # city, zip, neighborhood, or "lat,lng"
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    bedrooms_min: Optional[int] = None
    bathrooms_min: Optional[float] = None
    property_types: List[str] = field(default_factory=list)
    min_sqft: Optional[int] = None
    max_sqft: Optional[int] = None
    year_built_min: Optional[int] = None
    features: List[str] = field(default_factory=list)
    sort_by: str = "relevance"  # relevance, price_asc, price_desc, newest
    radius_miles: Optional[float] = None
    max_results: int = 20


@dataclass
class AgentResponse:
    """Response from an agent execution."""
    agent: AgentType
    content: str
    tools_used: List[str]
    data: Dict[str, Any]
    latency_ms: int
    success: bool
    error: Optional[str] = None
    needs_followup: bool = False
    followup_agent: Optional[AgentType] = None


class PropertyFinderState(TypedDict):
    """
    Main state schema for the LangGraph workflow.

    This state flows through all nodes in the graph and maintains
    the complete context of the conversation.
    """
    # Conversation
    messages: Annotated[List[BaseMessage], add_messages]
    session_id: str
    conversation_turn: int

    # User (optional - property search works without login)
    user_context: Optional[Dict[str, Any]]

    # Current Request
    current_input: str
    input_language: str

    # Intent & Routing
    intent_result: Optional[Dict[str, Any]]
    selected_agent: Optional[str]

    # Cache
    cache_key: Optional[str]
    cache_result: Optional[str]
    cached_response: Optional[str]

    # Guardrails
    input_guardrail_status: Optional[str]
    output_guardrail_status: Optional[str]
    guardrail_messages: List[str]

    # Agent Execution
    agent_responses: List[Dict[str, Any]]
    current_agent_response: Optional[Dict[str, Any]]

    # Search / Domain State
    active_search_filters: Optional[Dict[str, Any]]
    search_results: List[Dict[str, Any]]
    focused_property_id: Optional[str]

    # Final Response
    final_response: Optional[str]
    response_language: str

    # Metadata
    created_at: str
    last_updated: str
    trace_id: str
    latency_breakdown: Dict[str, int]
    errors: List[str]


def create_initial_state(
    session_id: str,
    user_context: Optional[BuyerProfile] = None,
    trace_id: Optional[str] = None
) -> PropertyFinderState:
    """
    Create an initial state for a new conversation turn.

    Args:
        session_id: Unique session identifier
        user_context: Optional buyer profile
        trace_id: Optional trace ID for observability

    Returns:
        Initialized PropertyFinderState
    """
    import uuid

    now = datetime.utcnow().isoformat()

    return PropertyFinderState(
        messages=[],
        session_id=session_id,
        conversation_turn=0,
        user_context=user_context.__dict__ if user_context else None,
        current_input="",
        input_language="en",
        intent_result=None,
        selected_agent=None,
        cache_key=None,
        cache_result=None,
        cached_response=None,
        input_guardrail_status=None,
        output_guardrail_status=None,
        guardrail_messages=[],
        agent_responses=[],
        current_agent_response=None,
        active_search_filters=None,
        search_results=[],
        focused_property_id=None,
        final_response=None,
        response_language="en",
        created_at=now,
        last_updated=now,
        trace_id=trace_id or str(uuid.uuid4()),
        latency_breakdown={},
        errors=[]
    )


def update_latency(state: PropertyFinderState, component: str, latency_ms: int) -> PropertyFinderState:
    """Update latency breakdown for a component."""
    state["latency_breakdown"][component] = latency_ms
    state["last_updated"] = datetime.utcnow().isoformat()
    return state


def add_error(state: PropertyFinderState, error: str) -> PropertyFinderState:
    """Add an error to the state."""
    state["errors"].append(f"{datetime.utcnow().isoformat()}: {error}")
    return state


# Type aliases for cleaner code
StateUpdate = Dict[str, Any]
