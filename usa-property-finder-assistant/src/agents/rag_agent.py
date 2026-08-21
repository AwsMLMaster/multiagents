"""
RAG Agent for USA Property Finder Assistant.

Handles general real estate knowledge questions (terminology, process
guidance, FAQ) using AWS Bedrock Knowledge Base, with a direct-LLM fallback.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .base_agent import BaseAgent, AgentConfig, AgentResponse, AGENT_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)

# Fallback FAQ used when the knowledge base is not configured/available.
FAQ_RESPONSES = {
    "escrow": (
        "Escrow is a neutral third party that holds funds and documents during "
        "a real estate transaction until all conditions of the sale are met."
    ),
    "earnest money": (
        "Earnest money is a deposit made to show you're serious about "
        "purchasing a home. It's typically 1-3% of the purchase price and is "
        "credited toward your down payment/closing costs at closing."
    ),
    "pre-approved": (
        "Being pre-approved means a lender has reviewed your financials and "
        "credit and has conditionally agreed to lend you up to a certain "
        "amount. Pre-qualified is a less rigorous, informal estimate."
    ),
    "pmi": (
        "PMI (Private Mortgage Insurance) is typically required when your "
        "down payment is less than 20% of the home's price. It protects the "
        "lender, not you, and can usually be removed once you reach 20% equity."
    ),
    "hoa": (
        "An HOA (Homeowners Association) is an organization that manages "
        "shared amenities and enforces community rules in some neighborhoods "
        "and condo/townhome developments, funded by monthly or annual dues."
    ),
    "contingent": (
        "A 'contingent' listing means the seller has accepted an offer, but "
        "the sale depends on certain conditions being met (e.g., financing, "
        "inspection, or the buyer selling their current home)."
    ),
    "1031 exchange": (
        "A 1031 exchange lets an investor defer capital gains tax by "
        "reinvesting proceeds from a sold property into a similar "
        "('like-kind') property, under IRS rules and strict timelines. This "
        "is general information, not tax advice - consult a tax professional."
    ),
}


class RAGAgent(BaseAgent):
    """
    RAG Agent for handling general real estate knowledge queries.
    """

    def __init__(self, config: Optional[AgentConfig] = None, knowledge_base_id: Optional[str] = None):
        super().__init__(config)
        self.knowledge_base_id = knowledge_base_id
        self._kb_client = None

    def _default_config(self) -> AgentConfig:
        return AgentConfig(
            name="rag_agent",
            description="General real estate knowledge and FAQ agent",
            tools=["knowledge_base_query"],
            system_prompt=AGENT_SYSTEM_PROMPTS["rag"],
        )

    @property
    def kb_client(self):
        if self._kb_client is None and self.knowledge_base_id:
            from ..integrations.knowledge_base import create_knowledge_base_client
            self._kb_client = create_knowledge_base_client(self.knowledge_base_id)
        return self._kb_client

    async def execute(
        self,
        query: str,
        intent: Dict[str, Any],
        history: Optional[List[BaseMessage]] = None,
        **kwargs,
    ) -> AgentResponse:
        """
        Answer a general real estate knowledge question.
        """
        try:
            faq_hit = self._check_faq(query)
            if faq_hit:
                return AgentResponse(content=faq_hit, tools_used=["faq_lookup"], success=True)

            if self.kb_client:
                try:
                    kb_response = await self.kb_client.retrieve_and_generate(query=query)
                    if kb_response.answer:
                        return AgentResponse(
                            content=kb_response.answer,
                            tools_used=["knowledge_base_query"],
                            data={
                                "citations": [
                                    {"source": c.source, "score": c.score}
                                    for c in kb_response.citations
                                ],
                            },
                            success=True,
                        )
                except Exception as e:
                    logger.warning(f"Knowledge Base query failed: {e}")

            messages = self._format_history(history)
            messages.append({"role": "user", "content": query})

            response = await self.bedrock_client.invoke(
                messages=messages,
                system_prompt=self.config.system_prompt,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            return AgentResponse(
                content=response.content,
                tools_used=[],
                data={
                    "tokens_in": response.input_tokens,
                    "tokens_out": response.output_tokens,
                    "source": "direct_llm",
                },
                success=True,
            )

        except Exception as e:
            return self._build_error_response(
                str(e),
                "Sorry, I couldn't find an answer to that. Could you try rephrasing?",
            )

    def _check_faq(self, question: str) -> Optional[str]:
        """Check the static FAQ fallback for a direct keyword match."""
        question_lower = question.lower()
        for keyword, response in FAQ_RESPONSES.items():
            if keyword in question_lower:
                return response
        return None
