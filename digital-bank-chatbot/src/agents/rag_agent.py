"""
RAG Agent for general knowledge queries.

Uses AWS Bedrock Knowledge Base for retrieval-augmented generation.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .base_agent import BaseAgent, AgentConfig, AgentResponse, AGENT_SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


class RAGAgent(BaseAgent):
    """
    RAG Agent for handling general banking knowledge queries.

    Uses AWS Bedrock Knowledge Base for document retrieval and
    generates responses based on retrieved context.
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        knowledge_base_id: Optional[str] = None
    ):
        """
        Initialize RAG agent.

        Args:
            config: Optional agent configuration.
            knowledge_base_id: AWS Bedrock Knowledge Base ID.
        """
        super().__init__(config)
        self.knowledge_base_id = knowledge_base_id
        self._kb_client = None

    def _default_config(self) -> AgentConfig:
        """Return default configuration."""
        return AgentConfig(
            name="rag_agent",
            description="General banking knowledge and FAQ agent",
            tools=["knowledge_base_query", "product_search"],
            system_prompt=AGENT_SYSTEM_PROMPTS["rag"]
        )

    @property
    def kb_client(self):
        """Lazy initialization of Knowledge Base client."""
        if self._kb_client is None and self.knowledge_base_id:
            from ..integrations.knowledge_base import create_knowledge_base_client
            self._kb_client = create_knowledge_base_client(self.knowledge_base_id)
        return self._kb_client

    async def execute(
        self,
        query: str,
        intent: Dict[str, Any],
        history: Optional[List[BaseMessage]] = None,
        **kwargs
    ) -> AgentResponse:
        """
        Execute RAG query.

        Args:
            query: User query.
            intent: Intent classification result.
            history: Conversation history.
            **kwargs: Additional context.

        Returns:
            AgentResponse with generated answer.
        """
        try:
            tools_used = []
            retrieved_context = ""

            # Try Knowledge Base retrieval if available
            if self.kb_client:
                try:
                    kb_response = await self.kb_client.retrieve_and_generate(
                        query=query,
                        max_results=5
                    )
                    if kb_response.answer:
                        tools_used.append("knowledge_base_query")
                        return AgentResponse(
                            content=kb_response.answer,
                            tools_used=tools_used,
                            data={
                                "citations": [
                                    {"source": c.source, "score": c.score}
                                    for c in kb_response.citations
                                ],
                                "latency_ms": kb_response.latency_ms
                            },
                            success=True
                        )
                except Exception as e:
                    logger.warning(f"Knowledge Base query failed: {e}")
                    # Fall back to direct LLM response

            # Direct LLM response (without RAG)
            messages = self._format_history(history)
            messages.append({"role": "user", "content": query})

            response = await self.bedrock_client.invoke(
                messages=messages,
                system_prompt=self.config.system_prompt,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )

            return AgentResponse(
                content=response.content,
                tools_used=tools_used,
                data={
                    "tokens_in": response.input_tokens,
                    "tokens_out": response.output_tokens,
                    "latency_ms": response.latency_ms,
                    "source": "direct_llm"
                },
                success=True
            )

        except Exception as e:
            return self._build_error_response(
                str(e),
                "מצטער, לא הצלחתי למצוא תשובה לשאלתך. אנא נסה לנסח אחרת או פנה לשירות לקוחות."
            )

    async def search_products(
        self,
        query: str,
        product_type: Optional[str] = None
    ) -> AgentResponse:
        """
        Search for banking products.

        Args:
            query: Search query.
            product_type: Optional product type filter.

        Returns:
            AgentResponse with product information.
        """
        try:
            # This would integrate with a product catalog
            # For now, use KB search with product filter

            if self.kb_client:
                results = await self.kb_client.semantic_search(
                    query=query,
                    document_type="product"
                )

                if results:
                    content = "מצאתי את המוצרים הבאים:\n\n"
                    for i, result in enumerate(results[:3], 1):
                        content += f"{i}. {result.content[:200]}...\n\n"

                    return AgentResponse(
                        content=content,
                        tools_used=["product_search"],
                        data={"results_count": len(results)},
                        success=True
                    )

            return AgentResponse(
                content="לא נמצאו מוצרים מתאימים. לפרטים נוספים פנה לשירות לקוחות.",
                tools_used=["product_search"],
                success=True
            )

        except Exception as e:
            return self._build_error_response(
                str(e),
                "מצטער, לא הצלחתי לחפש מוצרים כרגע."
            )

    async def answer_faq(
        self,
        question: str
    ) -> AgentResponse:
        """
        Answer FAQ-type questions.

        Args:
            question: FAQ question.

        Returns:
            AgentResponse with answer.
        """
        # Common FAQ responses (fallback if KB not available)
        FAQ_RESPONSES = {
            "שעות פעילות": (
                "שעות הפעילות שלנו:\n"
                "• ימים א'-ה': 08:00-18:00\n"
                "• יום ו': 08:00-13:00\n"
                "• שבת וחג: סגור\n\n"
                "השירות הטלפוני זמין 24/7 בטלפון *2874"
            ),
            "פתיחת חשבון": (
                "לפתיחת חשבון חדש תצטרך:\n"
                "• תעודת זהות תקפה\n"
                "• אסמכתא על מקום מגורים\n"
                "• הוכחת הכנסה (תלוש משכורת או דוח שנתי)\n\n"
                "ניתן לפתוח חשבון באפליקציה או בפנייה לשירות הלקוחות."
            ),
            "שחזור סיסמה": (
                "לשחזור סיסמה:\n"
                "1. לחץ על 'שכחתי סיסמה' בדף הכניסה\n"
                "2. הזן את מספר תעודת הזהות\n"
                "3. קוד אימות יישלח לנייד הרשום\n"
                "4. הגדר סיסמה חדשה\n\n"
                "לעזרה נוספת פנה לשירות לקוחות."
            ),
        }

        question_lower = question.lower()

        for keyword, response in FAQ_RESPONSES.items():
            if keyword in question_lower:
                return AgentResponse(
                    content=response,
                    tools_used=["faq_lookup"],
                    success=True
                )

        # If not found in FAQ, use standard execute
        return await self.execute(question, {})
