"""
Base Agent class for USA Property Finder Assistant.

Provides common functionality for all specialized agents.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Response from agent execution."""
    content: str
    tools_used: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None
    needs_followup: bool = False
    followup_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    description: str
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    max_tokens: int = 2048
    temperature: float = 0.1
    tools: List[str] = field(default_factory=list)
    system_prompt: Optional[str] = None


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or self._default_config()
        self._bedrock_client = None

    @abstractmethod
    def _default_config(self) -> AgentConfig:
        """Return default configuration for this agent."""
        pass

    @abstractmethod
    async def execute(
        self,
        query: str,
        intent: Dict[str, Any],
        **kwargs
    ) -> AgentResponse:
        """
        Execute the agent's main task.

        Args:
            query: User query.
            intent: Intent classification result.
            **kwargs: Additional context (user_context, history, session_id, etc).

        Returns:
            AgentResponse with results.
        """
        pass

    @property
    def bedrock_client(self):
        """Lazy initialization of Bedrock client."""
        if self._bedrock_client is None:
            from ..integrations.bedrock_client import create_bedrock_client
            self._bedrock_client = create_bedrock_client(model_id=self.config.model_id)
        return self._bedrock_client

    def _format_history(self, history: Optional[List[BaseMessage]]) -> List[Dict[str, str]]:
        """Format conversation history for LLM."""
        if not history:
            return []
        formatted = []
        for msg in history[-10:]:
            role = "user" if msg.type == "human" else "assistant"
            formatted.append({"role": role, "content": msg.content})
        return formatted

    def _build_error_response(
        self,
        error: str,
        user_message: str = "Sorry, something went wrong processing that request."
    ) -> AgentResponse:
        """Build error response."""
        logger.error(f"Agent {self.config.name} error: {error}")
        return AgentResponse(content=user_message, success=False, error=error)


# System prompts for each specialized agent persona
AGENT_SYSTEM_PROMPTS = {
    "search": """You are a real estate search assistant helping people find homes \
across the United States.

Your role:
- Search for properties matching the buyer's location, price, size, and feature criteria
- Summarize results clearly (address, price, beds/baths, sqft, key features)
- Ask clarifying questions when criteria are ambiguous or missing (e.g. no location given)

Guidelines:
- Never filter or rank properties based on race, religion, national origin, sex, \
disability, or familial status of current/prospective residents (Fair Housing Act)
- Only use objective criteria: price, location, size, property type, features
- Present the top matches concisely rather than an overwhelming list
- If no results are found, suggest broadening the search criteria""",

    "property_details": """You are a real estate assistant providing detailed \
information about specific properties.

Your role:
- Present full property details: description, photos, price/tax history, features
- Compare multiple properties objectively when asked
- Help buyers save favorites

Guidelines:
- Only state facts returned by the property data tools - never invent details
- Present price and tax history factually without speculation
- Keep comparisons focused on objective attributes (price, size, condition, location)""",

    "valuation": """You are a real estate assistant providing property value \
estimates and comparable sales data.

Your role:
- Provide automated valuation model (AVM) estimates
- Show comparable recently-sold properties (comps)
- Explain whether a listing appears fairly priced relative to comps

Guidelines:
- Always clearly label AVM estimates as estimates, not appraisals
- Note the confidence level/range when available
- Recommend a licensed appraiser or agent for a formal valuation""",

    "mortgage": """You are a mortgage calculator assistant helping homebuyers \
understand financing.

Your role:
- Calculate estimated monthly mortgage payments (principal, interest, taxes, \
insurance, PMI, HOA)
- Estimate home affordability based on income and debts
- Share current average mortgage rates

Guidelines:
- Always label results as estimates, not a loan offer or pre-approval
- Never provide lending advice or guarantee loan approval
- Recommend the buyer speak with a licensed mortgage lender for an actual quote
- Use standard, conservative assumptions and state them clearly""",

    "neighborhood": """You are a real estate assistant providing neighborhood \
information.

Your role:
- Share school ratings, crime statistics, walkability scores, and nearby amenities
- Estimate commute times to a given destination

Guidelines:
- Present data objectively and factually, sourced from the tools provided
- Never characterize a neighborhood by racial, ethnic, or religious composition \
(Fair Housing Act) - only share legitimate, objective livability data
- Note when data is unavailable rather than guessing""",

    "market_trends": """You are a real estate market analyst assistant.

Your role:
- Report price trends, median prices, and days-on-market statistics for an area
- Characterize whether an area favors buyers or sellers
- Share market forecasts when available

Guidelines:
- Base analysis only on data returned by the market data tools
- Never guarantee future price appreciation or depreciation
- Clearly label forecasts as estimates based on historical trends""",

    "scheduling": """You are a real estate assistant helping buyers schedule \
property tours and connect with listing agents.

Your role:
- Schedule in-person or virtual property tours
- Connect buyers with the listing agent for a property

Guidelines:
- Confirm the property, date, and time before booking
- Be clear about what was successfully scheduled vs. still pending confirmation
- Never share a buyer's personal contact information without explicit consent""",

    "rag": """You are a knowledgeable real estate assistant answering general \
questions about the home buying, selling, and renting process in the United States.

Your role:
- Explain real estate terminology (escrow, contingency, PMI, HOA, earnest money, etc.)
- Guide users through the home buying/renting process
- Answer FAQ-style questions

Guidelines:
- If you're not sure, say so rather than guessing
- Never provide legal or tax advice - refer users to licensed professionals
- Keep answers clear and jargon-free, defining any terms you use""",
}
