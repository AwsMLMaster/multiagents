"""
LangGraph-based Multi-Agent Orchestrator for USA Property Finder Assistant.

This module implements the main orchestration graph using LangGraph,
coordinating specialized agents for property search, details, valuation,
mortgage, neighborhood, market trends, scheduling, and general Q&A.
"""

import logging
from typing import Any, Dict, Literal, Optional

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage

from .state import (
    PropertyFinderState,
    AgentType,
    GuardrailStatus,
    CacheResult,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Node Implementations
# ============================================================================

async def input_guard_node(state: PropertyFinderState) -> Dict[str, Any]:
    """
    Input guardrail node - validates and sanitizes user input.

    Checks for prompt injection, PII, and Fair Housing Act compliance
    (blocks discriminatory search steering requests).
    """
    import time
    start = time.time()

    current_input = state["current_input"]
    guardrail_messages = []

    try:
        from ..guardrails.input_validator import InputValidator

        validator = InputValidator()
        result = validator.validate(current_input)

        status = GuardrailStatus.APPROVED.value
        if result.blocked:
            status = GuardrailStatus.BLOCKED.value
            guardrail_messages.append(result.reason)
        elif result.warnings:
            status = GuardrailStatus.WARNING.value
            guardrail_messages.extend(result.warnings)

        latency_ms = int((time.time() - start) * 1000)

        return {
            "input_guardrail_status": status,
            "guardrail_messages": guardrail_messages,
            "input_language": result.detected_language,
            "latency_breakdown": {**state.get("latency_breakdown", {}), "input_guard": latency_ms},
        }

    except Exception as e:
        logger.error(f"Input guard error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "input_guardrail_status": GuardrailStatus.APPROVED.value,
            "guardrail_messages": [],
            "input_language": "en",
            "latency_breakdown": {**state.get("latency_breakdown", {}), "input_guard": latency_ms},
            "errors": state.get("errors", []) + [f"Input guard error: {str(e)}"],
        }


async def cache_check_node(state: PropertyFinderState) -> Dict[str, Any]:
    """
    Cache check node - looks for a cached response to an identical,
    non-personalized query (e.g., repeated general knowledge questions).
    """
    import time
    start = time.time()

    try:
        from ..cache.cache_manager import CacheManager

        cache_manager = CacheManager()
        current_input = state["current_input"]
        user_context = state.get("user_context")

        cache_key = cache_manager.generate_key(
            query=current_input,
            user_id=None,  # only cache non-personalized queries
            intent=state.get("intent_result", {}).get("intent_id") if state.get("intent_result") else None,
        )

        cached = await cache_manager.get(cache_key)
        latency_ms = int((time.time() - start) * 1000)

        if cached and not user_context:
            return {
                "cache_key": cache_key,
                "cache_result": CacheResult.HIT.value,
                "cached_response": cached,
                "latency_breakdown": {**state.get("latency_breakdown", {}), "cache_check": latency_ms},
            }

        return {
            "cache_key": cache_key,
            "cache_result": CacheResult.MISS.value,
            "cached_response": None,
            "latency_breakdown": {**state.get("latency_breakdown", {}), "cache_check": latency_ms},
        }

    except Exception as e:
        logger.error(f"Cache check error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "cache_key": None,
            "cache_result": CacheResult.MISS.value,
            "cached_response": None,
            "latency_breakdown": {**state.get("latency_breakdown", {}), "cache_check": latency_ms},
        }


async def intent_classifier_node(state: PropertyFinderState) -> Dict[str, Any]:
    """
    Intent classification node - determines user intent, extracted
    parameters, and target agent.
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
            user_context=state.get("user_context"),
        )

        latency_ms = int((time.time() - start) * 1000)

        return {
            "intent_result": {
                "intent_id": result.intent_id,
                "category": result.category.value,
                "confidence": result.confidence,
                "parameters": result.parameters,
                "target_agent": result.target_agent.value,
            },
            "selected_agent": result.target_agent.value,
            "latency_breakdown": {**state.get("latency_breakdown", {}), "intent_classification": latency_ms},
        }

    except Exception as e:
        logger.error(f"Intent classification error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "intent_result": {
                "intent_id": "rag.general",
                "category": "rag",
                "confidence": 0.0,
                "parameters": {},
                "target_agent": AgentType.RAG.value,
            },
            "selected_agent": AgentType.RAG.value,
            "latency_breakdown": {**state.get("latency_breakdown", {}), "intent_classification": latency_ms},
            "errors": state.get("errors", []) + [f"Intent classification error: {str(e)}"],
        }


def _make_agent_node(agent_type: AgentType, agent_module: str, agent_class: str, fallback_message: str):
    """Factory for a standard agent-execution node, reducing boilerplate below."""

    async def node(state: PropertyFinderState) -> Dict[str, Any]:
        import time
        start = time.time()

        try:
            module = __import__(f"src.agents.{agent_module}", fromlist=[agent_class])
            agent_cls = getattr(module, agent_class)
            agent = agent_cls()

            memory_context = {}
            try:
                from ..memory.memory_manager import get_memory_manager
                memory = get_memory_manager()
                memory_context["focused_property_id"] = memory.get_focused_property(state["session_id"])
                active_search = memory.get_active_search(state["session_id"])
                if active_search:
                    memory_context["active_search_filters"] = active_search.get("filters")
            except Exception as mem_error:
                logger.debug(f"Memory lookup skipped: {mem_error}")

            response = await agent.execute(
                query=state["current_input"],
                intent=state.get("intent_result", {}),
                history=state.get("messages", []),
                user_context=state.get("user_context"),
                focused_property_id=memory_context.get("focused_property_id")
                or state.get("focused_property_id"),
            )

            latency_ms = int((time.time() - start) * 1000)

            result: Dict[str, Any] = {
                "current_agent_response": {
                    "agent": agent_type.value,
                    "content": response.content,
                    "tools_used": response.tools_used,
                    "data": response.data,
                    "latency_ms": latency_ms,
                    "success": response.success,
                    "error": response.error,
                },
                "agent_responses": state.get("agent_responses", []) + [{
                    "agent": agent_type.value,
                    "content": response.content,
                    "latency_ms": latency_ms,
                }],
                "latency_breakdown": {**state.get("latency_breakdown", {}), agent_type.value: latency_ms},
            }

            # Persist useful domain state for follow-up turns
            if "results" in response.data:
                result["search_results"] = response.data["results"]
                result["active_search_filters"] = response.data.get("filters")
                try:
                    from ..memory.memory_manager import get_memory_manager
                    get_memory_manager().remember_active_search(
                        state["session_id"], response.data.get("filters", {}), response.data["results"]
                    )
                except Exception:
                    pass

            focused_id = (
                response.data.get("focused_property_id")
                or response.data.get("property_id")
            )
            if focused_id:
                result["focused_property_id"] = focused_id
                try:
                    from ..memory.memory_manager import get_memory_manager
                    get_memory_manager().remember_focused_property(state["session_id"], focused_id)
                except Exception:
                    pass

            return result

        except Exception as e:
            logger.error(f"{agent_type.value} error: {e}")
            latency_ms = int((time.time() - start) * 1000)
            return {
                "current_agent_response": {
                    "agent": agent_type.value,
                    "content": fallback_message,
                    "tools_used": [],
                    "data": {},
                    "latency_ms": latency_ms,
                    "success": False,
                    "error": str(e),
                },
                "latency_breakdown": {**state.get("latency_breakdown", {}), agent_type.value: latency_ms},
                "errors": state.get("errors", []) + [f"{agent_type.value} error: {str(e)}"],
            }

    return node


rag_agent_node = _make_agent_node(
    AgentType.RAG, "rag_agent", "RAGAgent",
    "Sorry, I couldn't process that. Please try again.",
)
search_agent_node = _make_agent_node(
    AgentType.SEARCH, "search_agent", "SearchAgent",
    "Sorry, I ran into a problem searching for properties. Please try again.",
)
property_details_agent_node = _make_agent_node(
    AgentType.PROPERTY_DETAILS, "property_details_agent", "PropertyDetailsAgent",
    "Sorry, I couldn't pull up those property details.",
)
valuation_agent_node = _make_agent_node(
    AgentType.VALUATION, "valuation_agent", "ValuationAgent",
    "Sorry, I couldn't retrieve a valuation right now.",
)
mortgage_agent_node = _make_agent_node(
    AgentType.MORTGAGE, "mortgage_agent", "MortgageAgent",
    "Sorry, I couldn't complete that mortgage calculation.",
)
neighborhood_agent_node = _make_agent_node(
    AgentType.NEIGHBORHOOD, "neighborhood_agent", "NeighborhoodAgent",
    "Sorry, I couldn't retrieve neighborhood information right now.",
)
market_trends_agent_node = _make_agent_node(
    AgentType.MARKET_TRENDS, "market_trends_agent", "MarketTrendsAgent",
    "Sorry, I couldn't retrieve market data right now.",
)
scheduling_agent_node = _make_agent_node(
    AgentType.SCHEDULING, "scheduling_agent", "SchedulingAgent",
    "Sorry, I couldn't complete that scheduling request.",
)


async def output_guard_node(state: PropertyFinderState) -> Dict[str, Any]:
    """
    Output guardrail node - validates agent responses for PII leakage,
    Fair Housing Act compliance, and required disclaimers.
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
            intent=state.get("intent_result", {}).get("intent_id"),
        )

        status = GuardrailStatus.APPROVED.value
        final_content = content

        if result.blocked:
            status = GuardrailStatus.BLOCKED.value
            final_content = result.reason or "Sorry, I can't provide that response."
        elif result.modified:
            final_content = result.modified_content
        if result.disclaimer_required:
            final_content = f"{final_content}\n\n{result.disclaimer}"

        latency_ms = int((time.time() - start) * 1000)

        return {
            "output_guardrail_status": status,
            "current_agent_response": {**agent_response, "content": final_content},
            "latency_breakdown": {**state.get("latency_breakdown", {}), "output_guard": latency_ms},
        }

    except Exception as e:
        logger.error(f"Output guard error: {e}")
        latency_ms = int((time.time() - start) * 1000)
        return {
            "output_guardrail_status": GuardrailStatus.APPROVED.value,
            "latency_breakdown": {**state.get("latency_breakdown", {}), "output_guard": latency_ms},
        }


async def response_synthesis_node(state: PropertyFinderState) -> Dict[str, Any]:
    """Response synthesis node - prepares the final response."""
    import time
    start = time.time()

    try:
        agent_response = state.get("current_agent_response", {})
        content = agent_response.get("content", "Sorry, I couldn't process that request.")

        messages = state.get("messages", [])
        messages.append(AIMessage(content=content))

        latency_ms = int((time.time() - start) * 1000)

        return {
            "final_response": content,
            "messages": messages,
            "conversation_turn": state.get("conversation_turn", 0) + 1,
            "latency_breakdown": {**state.get("latency_breakdown", {}), "response_synthesis": latency_ms},
        }

    except Exception as e:
        logger.error(f"Response synthesis error: {e}")
        fallback = "Sorry, something went wrong. Please try again."
        return {
            "final_response": fallback,
            "messages": state.get("messages", []) + [AIMessage(content=fallback)],
        }


async def cache_update_node(state: PropertyFinderState) -> Dict[str, Any]:
    """Cache update node - stores successful, non-personalized responses."""
    try:
        from ..cache.cache_manager import CacheManager

        agent_response = state.get("current_agent_response", {})
        if not agent_response.get("success", False):
            return {}

        # Don't cache personalized or transactional responses
        intent_id = state.get("intent_result", {}).get("intent_id", "")
        non_cacheable_prefixes = ("scheduling.", "property.favorite", "search.save")
        if state.get("user_context") or intent_id.startswith(non_cacheable_prefixes):
            return {}

        cache_manager = CacheManager()
        cache_key = state.get("cache_key")
        final_response = state.get("final_response")

        if cache_key and final_response:
            await cache_manager.set(key=cache_key, value=final_response, ttl=900)

        return {}

    except Exception as e:
        logger.error(f"Cache update error: {e}")
        return {}


async def rejection_response_node(state: PropertyFinderState) -> Dict[str, Any]:
    """Rejection response node - handles blocked requests."""
    guardrail_messages = state.get("guardrail_messages", [])
    content = guardrail_messages[0] if guardrail_messages else "Sorry, I can't process that request."

    return {
        "final_response": content,
        "messages": state.get("messages", []) + [AIMessage(content=content)],
    }


async def cache_return_node(state: PropertyFinderState) -> Dict[str, Any]:
    """Cache return node - returns a cached response directly."""
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
            "success": True,
        },
    }


# ============================================================================
# Routing Functions
# ============================================================================

def route_after_input_guard(state: PropertyFinderState) -> Literal["cache_check", "rejection_response"]:
    """Route based on input guardrail result."""
    status = state.get("input_guardrail_status", GuardrailStatus.APPROVED.value)
    return "rejection_response" if status == GuardrailStatus.BLOCKED.value else "cache_check"


def route_after_cache_check(state: PropertyFinderState) -> Literal["cache_return", "intent_classifier"]:
    """Route based on cache check result."""
    cache_result = state.get("cache_result", CacheResult.MISS.value)
    return "cache_return" if cache_result == CacheResult.HIT.value else "intent_classifier"


def route_to_agent(state: PropertyFinderState) -> Literal[
    "rag_agent", "search_agent", "property_details_agent", "valuation_agent",
    "mortgage_agent", "neighborhood_agent", "market_trends_agent", "scheduling_agent",
]:
    """Route to the appropriate agent based on intent classification."""
    selected_agent = state.get("selected_agent", AgentType.RAG.value)

    agent_mapping = {
        AgentType.RAG.value: "rag_agent",
        AgentType.SEARCH.value: "search_agent",
        AgentType.PROPERTY_DETAILS.value: "property_details_agent",
        AgentType.VALUATION.value: "valuation_agent",
        AgentType.MORTGAGE.value: "mortgage_agent",
        AgentType.NEIGHBORHOOD.value: "neighborhood_agent",
        AgentType.MARKET_TRENDS.value: "market_trends_agent",
        AgentType.SCHEDULING.value: "scheduling_agent",
    }

    return agent_mapping.get(selected_agent, "rag_agent")


# ============================================================================
# Graph Builder
# ============================================================================

AGENT_NODES = {
    "rag_agent": rag_agent_node,
    "search_agent": search_agent_node,
    "property_details_agent": property_details_agent_node,
    "valuation_agent": valuation_agent_node,
    "mortgage_agent": mortgage_agent_node,
    "neighborhood_agent": neighborhood_agent_node,
    "market_trends_agent": market_trends_agent_node,
    "scheduling_agent": scheduling_agent_node,
}


def build_property_finder_graph() -> StateGraph:
    """
    Build the main LangGraph workflow for the USA Property Finder Assistant.

    Returns:
        Unompiled StateGraph ready to be compiled with a checkpointer.
    """
    workflow = StateGraph(PropertyFinderState)

    workflow.add_node("input_guard", input_guard_node)
    workflow.add_node("cache_check", cache_check_node)
    workflow.add_node("intent_classifier", intent_classifier_node)
    for name, node in AGENT_NODES.items():
        workflow.add_node(name, node)
    workflow.add_node("output_guard", output_guard_node)
    workflow.add_node("response_synthesis", response_synthesis_node)
    workflow.add_node("cache_update", cache_update_node)
    workflow.add_node("rejection_response", rejection_response_node)
    workflow.add_node("cache_return", cache_return_node)

    workflow.add_edge(START, "input_guard")

    workflow.add_conditional_edges(
        "input_guard",
        route_after_input_guard,
        {"cache_check": "cache_check", "rejection_response": "rejection_response"},
    )

    workflow.add_conditional_edges(
        "cache_check",
        route_after_cache_check,
        {"cache_return": "cache_return", "intent_classifier": "intent_classifier"},
    )

    workflow.add_conditional_edges(
        "intent_classifier",
        route_to_agent,
        {name: name for name in AGENT_NODES},
    )

    for name in AGENT_NODES:
        workflow.add_edge(name, "output_guard")

    workflow.add_edge("output_guard", "response_synthesis")
    workflow.add_edge("response_synthesis", "cache_update")
    workflow.add_edge("cache_update", END)
    workflow.add_edge("rejection_response", END)
    workflow.add_edge("cache_return", END)

    return workflow


def create_property_finder_app(checkpointer: Optional[MemorySaver] = None):
    """
    Create the compiled property finder application.

    Args:
        checkpointer: Optional checkpointer for conversation persistence.

    Returns:
        Compiled LangGraph application.
    """
    workflow = build_property_finder_graph()
    return workflow.compile(checkpointer=checkpointer or MemorySaver())


# Singleton instance
_property_finder_app = None


def get_property_finder_app():
    """Get or create the singleton property finder application."""
    global _property_finder_app
    if _property_finder_app is None:
        _property_finder_app = create_property_finder_app()
    return _property_finder_app
