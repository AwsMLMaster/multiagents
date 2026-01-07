"""
LangGraph-based Multi-Agent Orchestrator for Digital Bank Chatbot.

This module implements the main orchestration graph using LangGraph,
coordinating multiple specialized agents for handling banking queries
and transactions.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Literal, Optional
from functools import lru_cache

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from .state import (
    ChatbotState,
    AuthLevel,
    AgentType,
    GuardrailStatus,
    CacheResult,
    create_initial_state,
    update_latency,
    add_error
)

logger = logging.getLogger(__name__)


# ============================================================================
# Node Implementations
# ============================================================================

async def input_guard_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Input guardrail node - validates and sanitizes user input.

    Checks for:
    - Prompt injection attempts
    - Malicious content
    - PII in input (for logging)
    - Input length limits
    - Language detection
    """
    import time
    start = time.time()

    current_input = state["current_input"]
    guardrail_messages = []

    try:
        # Import guardrails (lazy import to avoid circular deps)
        from ..guardrails.input_validator import InputValidator

        validator = InputValidator()
        result = validator.validate(current_input)

        status = GuardrailStatus.APPROVED.value
        if result.blocked:
            status = GuardrailStatus.BLOCKED.value
            guardrail_messages.append(result.reason)
        elif result.needs_auth:
            status = GuardrailStatus.NEEDS_AUTH.value
        elif result.warnings:
            status = GuardrailStatus.WARNING.value
            guardrail_messages.extend(result.warnings)

        latency_ms = int((time.time() - start) * 1000)

        return {
            "input_guardrail_status": status,
            "guardrail_messages": guardrail_messages,
            "input_language": result.detected_language,
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "input_guard": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"Input guard error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "input_guardrail_status": GuardrailStatus.APPROVED.value,
            "guardrail_messages": [],
            "input_language": "he",
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "input_guard": latency_ms
            },
            "errors": state.get("errors", []) + [f"Input guard error: {str(e)}"]
        }


async def cache_check_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Cache check node - looks for cached responses.

    Implements multi-level cache lookup:
    1. Exact match cache (normalized query)
    2. Semantic similarity cache (embedding-based)
    """
    import time
    start = time.time()

    try:
        from ..cache.cache_manager import CacheManager

        cache_manager = CacheManager()
        current_input = state["current_input"]
        user_context = state.get("user_context")

        # Generate cache key
        cache_key = cache_manager.generate_key(
            query=current_input,
            user_id=user_context.get("user_id") if user_context else None,
            intent=state.get("intent_result", {}).get("intent_id")
        )

        # Try exact match first
        cached = await cache_manager.get(cache_key)
        if cached:
            latency_ms = int((time.time() - start) * 1000)
            return {
                "cache_key": cache_key,
                "cache_result": CacheResult.HIT.value,
                "cached_response": cached,
                "latency_breakdown": {
                    **state.get("latency_breakdown", {}),
                    "cache_check": latency_ms
                }
            }

        # Try semantic cache for general queries
        if not user_context:  # Only for non-personalized queries
            semantic_result = await cache_manager.semantic_search(current_input)
            if semantic_result and semantic_result.similarity > 0.95:
                latency_ms = int((time.time() - start) * 1000)
                return {
                    "cache_key": cache_key,
                    "cache_result": CacheResult.HIT.value,
                    "cached_response": semantic_result.response,
                    "latency_breakdown": {
                        **state.get("latency_breakdown", {}),
                        "cache_check": latency_ms
                    }
                }

        latency_ms = int((time.time() - start) * 1000)
        return {
            "cache_key": cache_key,
            "cache_result": CacheResult.MISS.value,
            "cached_response": None,
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "cache_check": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"Cache check error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "cache_key": None,
            "cache_result": CacheResult.MISS.value,
            "cached_response": None,
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "cache_check": latency_ms
            }
        }


async def intent_classifier_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Intent classification node - determines user intent and target agent.

    Uses LLM-based classification with structured output to identify:
    - Intent category and specific intent
    - Required parameters
    - Target agent for handling
    - Authentication requirements
    """
    import time
    start = time.time()

    try:
        from ..intents.classifier import IntentClassifier

        classifier = IntentClassifier()
        current_input = state["current_input"]
        conversation_history = state.get("messages", [])

        result = await classifier.classify(
            query=current_input,
            history=conversation_history,
            user_context=state.get("user_context")
        )

        latency_ms = int((time.time() - start) * 1000)

        return {
            "intent_result": {
                "intent_id": result.intent_id,
                "category": result.category.value,
                "confidence": result.confidence,
                "parameters": result.parameters,
                "requires_auth": result.requires_auth,
                "requires_mfa": result.requires_mfa,
                "target_agent": result.target_agent.value
            },
            "selected_agent": result.target_agent.value,
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "intent_classification": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"Intent classification error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "intent_result": {
                "intent_id": "unknown",
                "category": "unknown",
                "confidence": 0.0,
                "parameters": {},
                "requires_auth": False,
                "requires_mfa": False,
                "target_agent": AgentType.RAG.value
            },
            "selected_agent": AgentType.RAG.value,
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "intent_classification": latency_ms
            },
            "errors": state.get("errors", []) + [f"Intent classification error: {str(e)}"]
        }


async def auth_verify_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Authentication verification node.

    Checks if user has required authentication level for the detected intent.
    """
    import time
    start = time.time()

    intent_result = state.get("intent_result", {})
    current_auth = AuthLevel(state.get("auth_level", AuthLevel.NONE.value))

    try:
        requires_auth = intent_result.get("requires_auth", False)
        requires_mfa = intent_result.get("requires_mfa", False)

        status = GuardrailStatus.APPROVED.value
        messages = state.get("guardrail_messages", [])

        if requires_mfa and current_auth != AuthLevel.MFA:
            status = GuardrailStatus.NEEDS_MFA.value
            messages.append("נדרש אימות דו-שלבי לביצוע פעולה זו")
        elif requires_auth and current_auth == AuthLevel.NONE:
            status = GuardrailStatus.NEEDS_AUTH.value
            messages.append("נדרשת התחברות לביצוע פעולה זו")

        latency_ms = int((time.time() - start) * 1000)

        return {
            "input_guardrail_status": status,
            "guardrail_messages": messages,
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "auth_verify": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"Auth verification error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "input_guardrail_status": GuardrailStatus.APPROVED.value,
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "auth_verify": latency_ms
            }
        }


async def rag_agent_node(state: ChatbotState) -> Dict[str, Any]:
    """
    RAG Agent node - handles general knowledge queries.

    Uses AWS Bedrock Knowledge Base for retrieval-augmented generation.
    """
    import time
    start = time.time()

    try:
        from ..agents.rag_agent import RAGAgent

        agent = RAGAgent()
        response = await agent.execute(
            query=state["current_input"],
            intent=state.get("intent_result", {}),
            history=state.get("messages", [])
        )

        latency_ms = int((time.time() - start) * 1000)

        return {
            "current_agent_response": {
                "agent": AgentType.RAG.value,
                "content": response.content,
                "tools_used": response.tools_used,
                "data": response.data,
                "latency_ms": latency_ms,
                "success": response.success,
                "error": response.error
            },
            "agent_responses": state.get("agent_responses", []) + [{
                "agent": AgentType.RAG.value,
                "content": response.content,
                "latency_ms": latency_ms
            }],
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "rag_agent": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"RAG agent error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "current_agent_response": {
                "agent": AgentType.RAG.value,
                "content": "מצטער, לא הצלחתי לעבד את הבקשה. אנא נסה שוב.",
                "tools_used": [],
                "data": {},
                "latency_ms": latency_ms,
                "success": False,
                "error": str(e)
            },
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "rag_agent": latency_ms
            },
            "errors": state.get("errors", []) + [f"RAG agent error: {str(e)}"]
        }


async def account_agent_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Account Agent node - handles account-related queries.

    Integrates with TCS Bancs for account information retrieval.
    """
    import time
    start = time.time()

    try:
        from ..agents.account_agent import AccountAgent

        agent = AccountAgent()
        response = await agent.execute(
            query=state["current_input"],
            intent=state.get("intent_result", {}),
            user_context=state.get("user_context"),
            history=state.get("messages", [])
        )

        latency_ms = int((time.time() - start) * 1000)

        return {
            "current_agent_response": {
                "agent": AgentType.ACCOUNT.value,
                "content": response.content,
                "tools_used": response.tools_used,
                "data": response.data,
                "latency_ms": latency_ms,
                "success": response.success,
                "error": response.error
            },
            "agent_responses": state.get("agent_responses", []) + [{
                "agent": AgentType.ACCOUNT.value,
                "content": response.content,
                "latency_ms": latency_ms
            }],
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "account_agent": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"Account agent error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "current_agent_response": {
                "agent": AgentType.ACCOUNT.value,
                "content": "מצטער, לא הצלחתי לאחזר את פרטי החשבון. אנא נסה שוב.",
                "tools_used": [],
                "data": {},
                "latency_ms": latency_ms,
                "success": False,
                "error": str(e)
            },
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "account_agent": latency_ms
            },
            "errors": state.get("errors", []) + [f"Account agent error: {str(e)}"]
        }


async def transaction_agent_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Transaction Agent node - handles financial transactions.

    Integrates with TCS Bancs for fund transfers, bill payments, etc.
    Requires MFA for execution.
    """
    import time
    start = time.time()

    try:
        from ..agents.transaction_agent import TransactionAgent

        agent = TransactionAgent()
        response = await agent.execute(
            query=state["current_input"],
            intent=state.get("intent_result", {}),
            user_context=state.get("user_context"),
            pending_transaction=state.get("pending_transaction"),
            history=state.get("messages", [])
        )

        latency_ms = int((time.time() - start) * 1000)

        result = {
            "current_agent_response": {
                "agent": AgentType.TRANSACTION.value,
                "content": response.content,
                "tools_used": response.tools_used,
                "data": response.data,
                "latency_ms": latency_ms,
                "success": response.success,
                "error": response.error
            },
            "agent_responses": state.get("agent_responses", []) + [{
                "agent": AgentType.TRANSACTION.value,
                "content": response.content,
                "latency_ms": latency_ms
            }],
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "transaction_agent": latency_ms
            }
        }

        # Update pending transaction if created
        if response.data.get("pending_transaction"):
            result["pending_transaction"] = response.data["pending_transaction"]

        return result

    except Exception as e:
        logger.error(f"Transaction agent error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "current_agent_response": {
                "agent": AgentType.TRANSACTION.value,
                "content": "מצטער, לא הצלחתי לעבד את הפעולה. אנא נסה שוב או פנה לשירות לקוחות.",
                "tools_used": [],
                "data": {},
                "latency_ms": latency_ms,
                "success": False,
                "error": str(e)
            },
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "transaction_agent": latency_ms
            },
            "errors": state.get("errors", []) + [f"Transaction agent error: {str(e)}"]
        }


async def loan_agent_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Loan Agent node - handles loan-related queries and operations.
    """
    import time
    start = time.time()

    try:
        from ..agents.loan_agent import LoanAgent

        agent = LoanAgent()
        response = await agent.execute(
            query=state["current_input"],
            intent=state.get("intent_result", {}),
            user_context=state.get("user_context"),
            history=state.get("messages", [])
        )

        latency_ms = int((time.time() - start) * 1000)

        return {
            "current_agent_response": {
                "agent": AgentType.LOAN.value,
                "content": response.content,
                "tools_used": response.tools_used,
                "data": response.data,
                "latency_ms": latency_ms,
                "success": response.success,
                "error": response.error
            },
            "agent_responses": state.get("agent_responses", []) + [{
                "agent": AgentType.LOAN.value,
                "content": response.content,
                "latency_ms": latency_ms
            }],
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "loan_agent": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"Loan agent error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "current_agent_response": {
                "agent": AgentType.LOAN.value,
                "content": "מצטער, לא הצלחתי לעבד את בקשת ההלוואה. אנא נסה שוב.",
                "tools_used": [],
                "data": {},
                "latency_ms": latency_ms,
                "success": False,
                "error": str(e)
            },
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "loan_agent": latency_ms
            },
            "errors": state.get("errors", []) + [f"Loan agent error: {str(e)}"]
        }


async def support_agent_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Support Agent node - handles customer support queries.
    """
    import time
    start = time.time()

    try:
        from ..agents.support_agent import SupportAgent

        agent = SupportAgent()
        response = await agent.execute(
            query=state["current_input"],
            intent=state.get("intent_result", {}),
            user_context=state.get("user_context"),
            history=state.get("messages", [])
        )

        latency_ms = int((time.time() - start) * 1000)

        return {
            "current_agent_response": {
                "agent": AgentType.SUPPORT.value,
                "content": response.content,
                "tools_used": response.tools_used,
                "data": response.data,
                "latency_ms": latency_ms,
                "success": response.success,
                "error": response.error
            },
            "agent_responses": state.get("agent_responses", []) + [{
                "agent": AgentType.SUPPORT.value,
                "content": response.content,
                "latency_ms": latency_ms
            }],
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "support_agent": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"Support agent error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "current_agent_response": {
                "agent": AgentType.SUPPORT.value,
                "content": "מצטער, לא הצלחתי לעבד את הבקשה. אנא נסה שוב או התקשר לשירות לקוחות.",
                "tools_used": [],
                "data": {},
                "latency_ms": latency_ms,
                "success": False,
                "error": str(e)
            },
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "support_agent": latency_ms
            },
            "errors": state.get("errors", []) + [f"Support agent error: {str(e)}"]
        }


async def analytics_agent_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Analytics Agent node - handles spending analysis and insights.
    """
    import time
    start = time.time()

    try:
        from ..agents.analytics_agent import AnalyticsAgent

        agent = AnalyticsAgent()
        response = await agent.execute(
            query=state["current_input"],
            intent=state.get("intent_result", {}),
            user_context=state.get("user_context"),
            history=state.get("messages", [])
        )

        latency_ms = int((time.time() - start) * 1000)

        return {
            "current_agent_response": {
                "agent": AgentType.ANALYTICS.value,
                "content": response.content,
                "tools_used": response.tools_used,
                "data": response.data,
                "latency_ms": latency_ms,
                "success": response.success,
                "error": response.error
            },
            "agent_responses": state.get("agent_responses", []) + [{
                "agent": AgentType.ANALYTICS.value,
                "content": response.content,
                "latency_ms": latency_ms
            }],
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "analytics_agent": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"Analytics agent error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "current_agent_response": {
                "agent": AgentType.ANALYTICS.value,
                "content": "מצטער, לא הצלחתי להפיק את הניתוח. אנא נסה שוב.",
                "tools_used": [],
                "data": {},
                "latency_ms": latency_ms,
                "success": False,
                "error": str(e)
            },
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "analytics_agent": latency_ms
            },
            "errors": state.get("errors", []) + [f"Analytics agent error: {str(e)}"]
        }


async def output_guard_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Output guardrail node - validates and sanitizes agent responses.

    Checks for:
    - PII leakage
    - Appropriate content
    - Required disclaimers
    - Response quality
    """
    import time
    start = time.time()

    try:
        from ..guardrails.output_validator import OutputValidator

        validator = OutputValidator()
        agent_response = state.get("current_agent_response", {})
        content = agent_response.get("content", "")

        result = validator.validate(
            content=content,
            intent=state.get("intent_result", {}).get("intent_id")
        )

        status = GuardrailStatus.APPROVED.value
        final_content = content

        if result.blocked:
            status = GuardrailStatus.BLOCKED.value
            final_content = "מצטער, לא ניתן להציג תשובה זו. אנא נסה שאלה אחרת."
        elif result.modified:
            final_content = result.modified_content
        elif result.disclaimer_required:
            final_content = f"{content}\n\n{result.disclaimer}"

        latency_ms = int((time.time() - start) * 1000)

        return {
            "output_guardrail_status": status,
            "current_agent_response": {
                **agent_response,
                "content": final_content
            },
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "output_guard": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"Output guard error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "output_guardrail_status": GuardrailStatus.APPROVED.value,
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "output_guard": latency_ms
            }
        }


async def response_synthesis_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Response synthesis node - prepares final response.

    Combines agent responses, applies formatting, and prepares
    the response in the user's preferred language.
    """
    import time
    start = time.time()

    try:
        agent_response = state.get("current_agent_response", {})
        content = agent_response.get("content", "מצטער, לא הצלחתי לעבד את הבקשה.")

        # Add AI message to conversation history
        messages = state.get("messages", [])
        messages.append(AIMessage(content=content))

        latency_ms = int((time.time() - start) * 1000)

        return {
            "final_response": content,
            "messages": messages,
            "conversation_turn": state.get("conversation_turn", 0) + 1,
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "response_synthesis": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"Response synthesis error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        fallback = "מצטער, אירעה שגיאה. אנא נסה שוב."
        return {
            "final_response": fallback,
            "messages": state.get("messages", []) + [AIMessage(content=fallback)],
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "response_synthesis": latency_ms
            }
        }


async def cache_update_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Cache update node - stores successful responses in cache.
    """
    import time
    start = time.time()

    try:
        from ..cache.cache_manager import CacheManager

        # Only cache successful, non-personalized responses
        agent_response = state.get("current_agent_response", {})
        if not agent_response.get("success", False):
            return {}

        # Don't cache personalized data
        intent = state.get("intent_result", {})
        if intent.get("requires_auth", False):
            return {}

        cache_manager = CacheManager()
        cache_key = state.get("cache_key")
        final_response = state.get("final_response")

        if cache_key and final_response:
            await cache_manager.set(
                key=cache_key,
                value=final_response,
                ttl=86400  # 24 hours for general knowledge
            )

            # Also update semantic cache
            await cache_manager.add_semantic_entry(
                query=state["current_input"],
                response=final_response
            )

        latency_ms = int((time.time() - start) * 1000)

        return {
            "latency_breakdown": {
                **state.get("latency_breakdown", {}),
                "cache_update": latency_ms
            }
        }

    except Exception as e:
        logger.error(f"Cache update error: {e}")
        return {}


async def rejection_response_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Rejection response node - handles blocked requests.
    """
    guardrail_messages = state.get("guardrail_messages", [])
    status = state.get("input_guardrail_status", "")

    if status == GuardrailStatus.NEEDS_AUTH.value:
        content = "אנא התחבר לחשבונך כדי לבצע פעולה זו."
    elif status == GuardrailStatus.NEEDS_MFA.value:
        content = "נדרש אימות דו-שלבי לביצוע פעולה זו. אנא אשר את הקוד שנשלח אליך."
    else:
        content = "מצטער, לא ניתן לעבד בקשה זו."
        if guardrail_messages:
            content += f"\nסיבה: {guardrail_messages[0]}"

    return {
        "final_response": content,
        "messages": state.get("messages", []) + [AIMessage(content=content)]
    }


async def cache_return_node(state: ChatbotState) -> Dict[str, Any]:
    """
    Cache return node - returns cached response directly.
    """
    cached_response = state.get("cached_response", "")

    return {
        "final_response": cached_response,
        "messages": state.get("messages", []) + [AIMessage(content=cached_response)],
        "current_agent_response": {
            "agent": "cache",
            "content": cached_response,
            "tools_used": [],
            "data": {"cache_hit": True},
            "latency_ms": 0,
            "success": True
        }
    }


# ============================================================================
# Routing Functions
# ============================================================================

def route_after_input_guard(
    state: ChatbotState
) -> Literal["cache_check", "rejection_response", "auth_verify"]:
    """Route based on input guardrail result."""
    status = state.get("input_guardrail_status", GuardrailStatus.APPROVED.value)

    if status == GuardrailStatus.BLOCKED.value:
        return "rejection_response"
    elif status in [GuardrailStatus.NEEDS_AUTH.value, GuardrailStatus.NEEDS_MFA.value]:
        return "auth_verify"
    else:
        return "cache_check"


def route_after_cache_check(
    state: ChatbotState
) -> Literal["cache_return", "intent_classifier"]:
    """Route based on cache check result."""
    cache_result = state.get("cache_result", CacheResult.MISS.value)

    if cache_result == CacheResult.HIT.value:
        return "cache_return"
    else:
        return "intent_classifier"


def route_after_auth_verify(
    state: ChatbotState
) -> Literal["cache_check", "rejection_response"]:
    """Route based on authentication verification."""
    status = state.get("input_guardrail_status", GuardrailStatus.APPROVED.value)

    if status in [GuardrailStatus.NEEDS_AUTH.value, GuardrailStatus.NEEDS_MFA.value]:
        return "rejection_response"
    else:
        return "cache_check"


def route_to_agent(
    state: ChatbotState
) -> Literal[
    "rag_agent", "account_agent", "transaction_agent",
    "loan_agent", "support_agent", "analytics_agent"
]:
    """Route to appropriate agent based on intent classification."""
    selected_agent = state.get("selected_agent", AgentType.RAG.value)

    agent_mapping = {
        AgentType.RAG.value: "rag_agent",
        AgentType.ACCOUNT.value: "account_agent",
        AgentType.TRANSACTION.value: "transaction_agent",
        AgentType.LOAN.value: "loan_agent",
        AgentType.SUPPORT.value: "support_agent",
        AgentType.ANALYTICS.value: "analytics_agent",
    }

    return agent_mapping.get(selected_agent, "rag_agent")


# ============================================================================
# Graph Builder
# ============================================================================

def build_chatbot_graph() -> StateGraph:
    """
    Build the main LangGraph workflow for the digital bank chatbot.

    Returns:
        Compiled StateGraph ready for execution.
    """
    # Create the graph
    workflow = StateGraph(ChatbotState)

    # Add all nodes
    workflow.add_node("input_guard", input_guard_node)
    workflow.add_node("cache_check", cache_check_node)
    workflow.add_node("intent_classifier", intent_classifier_node)
    workflow.add_node("auth_verify", auth_verify_node)
    workflow.add_node("rag_agent", rag_agent_node)
    workflow.add_node("account_agent", account_agent_node)
    workflow.add_node("transaction_agent", transaction_agent_node)
    workflow.add_node("loan_agent", loan_agent_node)
    workflow.add_node("support_agent", support_agent_node)
    workflow.add_node("analytics_agent", analytics_agent_node)
    workflow.add_node("output_guard", output_guard_node)
    workflow.add_node("response_synthesis", response_synthesis_node)
    workflow.add_node("cache_update", cache_update_node)
    workflow.add_node("rejection_response", rejection_response_node)
    workflow.add_node("cache_return", cache_return_node)

    # Add edges from START
    workflow.add_edge(START, "input_guard")

    # Add conditional edges after input guard
    workflow.add_conditional_edges(
        "input_guard",
        route_after_input_guard,
        {
            "cache_check": "cache_check",
            "rejection_response": "rejection_response",
            "auth_verify": "auth_verify"
        }
    )

    # Add conditional edges after auth verify
    workflow.add_conditional_edges(
        "auth_verify",
        route_after_auth_verify,
        {
            "cache_check": "cache_check",
            "rejection_response": "rejection_response"
        }
    )

    # Add conditional edges after cache check
    workflow.add_conditional_edges(
        "cache_check",
        route_after_cache_check,
        {
            "cache_return": "cache_return",
            "intent_classifier": "intent_classifier"
        }
    )

    # Add conditional edges after intent classifier to route to agents
    workflow.add_conditional_edges(
        "intent_classifier",
        route_to_agent,
        {
            "rag_agent": "rag_agent",
            "account_agent": "account_agent",
            "transaction_agent": "transaction_agent",
            "loan_agent": "loan_agent",
            "support_agent": "support_agent",
            "analytics_agent": "analytics_agent"
        }
    )

    # All agents go to output guard
    for agent in ["rag_agent", "account_agent", "transaction_agent",
                  "loan_agent", "support_agent", "analytics_agent"]:
        workflow.add_edge(agent, "output_guard")

    # Output guard to response synthesis
    workflow.add_edge("output_guard", "response_synthesis")

    # Response synthesis to cache update
    workflow.add_edge("response_synthesis", "cache_update")

    # Cache update to END
    workflow.add_edge("cache_update", END)

    # Rejection and cache return go directly to END
    workflow.add_edge("rejection_response", END)
    workflow.add_edge("cache_return", END)

    return workflow


def create_chatbot_app(checkpointer: Optional[MemorySaver] = None):
    """
    Create the compiled chatbot application.

    Args:
        checkpointer: Optional checkpointer for conversation persistence.

    Returns:
        Compiled LangGraph application.
    """
    workflow = build_chatbot_graph()

    if checkpointer is None:
        checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)


# Singleton instance
_chatbot_app = None


def get_chatbot_app():
    """Get or create the singleton chatbot application."""
    global _chatbot_app
    if _chatbot_app is None:
        _chatbot_app = create_chatbot_app()
    return _chatbot_app
