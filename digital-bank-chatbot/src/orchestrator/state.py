"""
State management for the Digital Bank Chatbot LangGraph orchestrator.

This module defines the state schema used throughout the multi-agent workflow,
including conversation history, intent tracking, authentication state, and
transaction management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class AuthLevel(str, Enum):
    """Authentication levels for user sessions."""
    NONE = "none"
    BASIC = "basic"  # Password/token authenticated
    MFA = "mfa"  # Multi-factor authenticated


class AgentType(str, Enum):
    """Types of specialized agents in the system."""
    SUPERVISOR = "supervisor"
    RAG = "rag_agent"
    TRANSACTION = "transaction_agent"
    ACCOUNT = "account_agent"
    LOAN = "loan_agent"
    SUPPORT = "support_agent"
    ANALYTICS = "analytics_agent"


class IntentCategory(str, Enum):
    """High-level intent categories."""
    ACCOUNT = "account"
    TRANSACTION = "transaction"
    LOAN = "loan"
    RAG = "rag"
    SUPPORT = "support"
    ANALYTICS = "analytics"
    UNKNOWN = "unknown"


class GuardrailStatus(str, Enum):
    """Status from guardrail checks."""
    APPROVED = "approved"
    BLOCKED = "blocked"
    NEEDS_AUTH = "needs_auth"
    NEEDS_MFA = "needs_mfa"
    WARNING = "warning"


class CacheResult(str, Enum):
    """Result of cache lookup."""
    HIT = "hit"
    MISS = "miss"
    EXPIRED = "expired"


@dataclass
class UserContext:
    """User context extracted from authentication token."""
    user_id: str
    customer_id: str
    accounts: List[Dict[str, Any]]
    loans: List[Dict[str, Any]]
    preferred_language: str = "he"
    preferences: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_jwt_payload(cls, payload: Dict[str, Any]) -> "UserContext":
        """Create UserContext from JWT payload."""
        return cls(
            user_id=payload.get("sub", ""),
            customer_id=payload.get("customer_id", ""),
            accounts=payload.get("accounts", []),
            loans=payload.get("loans", []),
            preferred_language=payload.get("language", "he"),
            preferences=payload.get("preferences", {})
        )


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent_id: str
    category: IntentCategory
    confidence: float
    parameters: Dict[str, Any]
    requires_auth: bool
    requires_mfa: bool
    target_agent: AgentType

    def is_confident(self, threshold: float = 0.85) -> bool:
        """Check if classification confidence meets threshold."""
        return self.confidence >= threshold


@dataclass
class TransactionRequest:
    """Pending financial transaction request."""
    transaction_id: str
    transaction_type: str  # transfer, payment, loan_payment
    from_account: Optional[str]
    to_account: Optional[str]
    amount: float
    currency: str
    description: Optional[str]
    status: str  # pending, awaiting_mfa, confirmed, executed, failed
    created_at: datetime
    mfa_verified: bool = False
    confirmation_required: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


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


class ChatbotState(TypedDict):
    """
    Main state schema for the LangGraph workflow.

    This state flows through all nodes in the graph and maintains
    the complete context of the conversation.
    """
    # Conversation
    messages: Annotated[List[BaseMessage], add_messages]
    session_id: str
    conversation_turn: int

    # User & Authentication
    user_context: Optional[Dict[str, Any]]
    auth_level: str

    # Current Request
    current_input: str
    input_language: str  # detected language

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

    # Transactions
    pending_transaction: Optional[Dict[str, Any]]
    transaction_confirmed: bool

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
    user_context: Optional[UserContext] = None,
    trace_id: Optional[str] = None
) -> ChatbotState:
    """
    Create an initial state for a new conversation turn.

    Args:
        session_id: Unique session identifier
        user_context: Optional authenticated user context
        trace_id: Optional trace ID for observability

    Returns:
        Initialized ChatbotState
    """
    import uuid

    now = datetime.utcnow().isoformat()

    return ChatbotState(
        messages=[],
        session_id=session_id,
        conversation_turn=0,
        user_context=user_context.__dict__ if user_context else None,
        auth_level=AuthLevel.BASIC.value if user_context else AuthLevel.NONE.value,
        current_input="",
        input_language="he",
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
        pending_transaction=None,
        transaction_confirmed=False,
        final_response=None,
        response_language="he",
        created_at=now,
        last_updated=now,
        trace_id=trace_id or str(uuid.uuid4()),
        latency_breakdown={},
        errors=[]
    )


def update_latency(state: ChatbotState, component: str, latency_ms: int) -> ChatbotState:
    """Update latency breakdown for a component."""
    state["latency_breakdown"][component] = latency_ms
    state["last_updated"] = datetime.utcnow().isoformat()
    return state


def add_error(state: ChatbotState, error: str) -> ChatbotState:
    """Add an error to the state."""
    state["errors"].append(f"{datetime.utcnow().isoformat()}: {error}")
    return state


# Type aliases for cleaner code
StateUpdate = Dict[str, Any]
