"""
Intent Classifier for Digital Bank Chatbot.

This module provides LLM-based intent classification with structured output,
supporting both Hebrew and English queries.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .registry import (
    INTENT_REGISTRY,
    IntentCategory,
    IntentDefinition,
    get_intent,
)
from ..orchestrator.state import AgentType, IntentResult

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result from intent classification."""
    intent_id: str
    category: IntentCategory
    confidence: float
    parameters: Dict[str, Any]
    requires_auth: bool
    requires_mfa: bool
    target_agent: AgentType
    reasoning: Optional[str] = None


CLASSIFICATION_SYSTEM_PROMPT = """אתה מערכת לזיהוי כוונות (Intent Classification) עבור צ'אטבוט בנקאי.

תפקידך לנתח את הודעת המשתמש ולזהות את הכוונה הספציפית מרשימת הכוונות האפשריות.

## כוונות אפשריות:

{intent_list}

## הוראות:
1. נתח את הודעת המשתמש בעברית או אנגלית
2. זהה את הכוונה המתאימה ביותר מהרשימה
3. חלץ פרמטרים רלוונטיים מההודעה
4. אם לא ברור, בחר "rag.general" עם רמת ביטחון נמוכה
5. התייחס להקשר השיחה אם קיים

## פורמט תשובה (JSON):
{{
    "intent_id": "string - מזהה הכוונה מהרשימה",
    "confidence": "float - רמת ביטחון בין 0 ל-1",
    "parameters": {{
        "param_name": "extracted_value"
    }},
    "reasoning": "string - הסבר קצר לבחירה"
}}

## דוגמאות:

קלט: "מה היתרה שלי?"
תשובה: {{"intent_id": "account.balance", "confidence": 0.95, "parameters": {{}}, "reasoning": "שאלה ישירה על יתרת חשבון"}}

קלט: "העבר 500 שקל לחשבון 123456"
תשובה: {{"intent_id": "transaction.transfer", "confidence": 0.92, "parameters": {{"amount": 500, "currency": "ILS", "to_account": "123456"}}, "reasoning": "בקשה להעברה עם סכום וחשבון יעד"}}

קלט: "מה הריבית על פיקדון?"
תשובה: {{"intent_id": "rag.products", "confidence": 0.88, "parameters": {{"product_type": "deposit"}}, "reasoning": "שאלה על מוצר בנקאי - פיקדון"}}
"""


def build_intent_list() -> str:
    """Build formatted intent list for the prompt."""
    lines = []
    for intent_id, intent in INTENT_REGISTRY.items():
        if not intent.enabled:
            continue

        examples = intent.examples_he[:2]  # First 2 Hebrew examples
        examples_str = ", ".join(f'"{ex}"' for ex in examples)

        params = ", ".join(intent.required_params) if intent.required_params else "none"

        lines.append(
            f"- **{intent_id}** ({intent.category.value}): {intent.description}\n"
            f"  פרמטרים נדרשים: {params}\n"
            f"  דוגמאות: {examples_str}"
        )

    return "\n".join(lines)


class IntentClassifier:
    """
    LLM-based intent classifier.

    Uses structured output to classify user queries into predefined intents.
    """

    def __init__(self, bedrock_client=None):
        """
        Initialize the classifier.

        Args:
            bedrock_client: Optional BedrockClient, creates default if not provided.
        """
        self._bedrock_client = bedrock_client
        self._intent_list = build_intent_list()

    @property
    def bedrock_client(self):
        """Lazy initialization of Bedrock client."""
        if self._bedrock_client is None:
            from ..integrations.bedrock_client import create_bedrock_client
            self._bedrock_client = create_bedrock_client()
        return self._bedrock_client

    async def classify(
        self,
        query: str,
        history: Optional[List[BaseMessage]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> ClassificationResult:
        """
        Classify user query into an intent.

        Args:
            query: User's query text.
            history: Optional conversation history.
            user_context: Optional user context for personalization.

        Returns:
            ClassificationResult with intent details.
        """
        try:
            # Build messages for classification
            messages = self._build_messages(query, history)

            # Get system prompt with intent list
            system_prompt = CLASSIFICATION_SYSTEM_PROMPT.format(
                intent_list=self._intent_list
            )

            # Call LLM for classification
            response = await self.bedrock_client.invoke(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.0,  # Deterministic for classification
                max_tokens=500,
            )

            # Parse response
            result = self._parse_response(response.content)

            # Enrich with intent metadata
            return self._enrich_result(result)

        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            # Fallback to RAG agent
            return ClassificationResult(
                intent_id="rag.general",
                category=IntentCategory.RAG,
                confidence=0.0,
                parameters={},
                requires_auth=False,
                requires_mfa=False,
                target_agent=AgentType.RAG,
                reasoning=f"Fallback due to error: {str(e)}"
            )

    def _build_messages(
        self,
        query: str,
        history: Optional[List[BaseMessage]] = None
    ) -> List[Dict[str, str]]:
        """Build messages list for LLM."""
        messages = []

        # Add relevant history for context (last 3 turns)
        if history:
            for msg in history[-6:]:  # Last 3 pairs
                role = "user" if msg.type == "human" else "assistant"
                messages.append({"role": role, "content": msg.content})

        # Add current query
        messages.append({"role": "user", "content": query})

        return messages

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM response JSON."""
        try:
            # Try to extract JSON from response
            content = content.strip()

            # Handle markdown code blocks
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse classification response: {e}")
            return {
                "intent_id": "rag.general",
                "confidence": 0.5,
                "parameters": {},
                "reasoning": "Failed to parse response"
            }

    def _enrich_result(self, parsed: Dict[str, Any]) -> ClassificationResult:
        """Enrich parsed result with intent metadata."""
        intent_id = parsed.get("intent_id", "rag.general")
        intent_def = get_intent(intent_id)

        if intent_def is None:
            # Unknown intent, fallback to RAG
            intent_def = get_intent("rag.general")
            intent_id = "rag.general"

        # Map target agent string to enum
        agent_mapping = {
            "rag_agent": AgentType.RAG,
            "account_agent": AgentType.ACCOUNT,
            "transaction_agent": AgentType.TRANSACTION,
            "loan_agent": AgentType.LOAN,
            "support_agent": AgentType.SUPPORT,
            "analytics_agent": AgentType.ANALYTICS,
        }

        target_agent = agent_mapping.get(
            intent_def.target_agent,
            AgentType.RAG
        )

        return ClassificationResult(
            intent_id=intent_id,
            category=IntentCategory(intent_def.category),
            confidence=parsed.get("confidence", 0.5),
            parameters=parsed.get("parameters", {}),
            requires_auth=intent_def.requires_auth,
            requires_mfa=intent_def.requires_mfa,
            target_agent=target_agent,
            reasoning=parsed.get("reasoning")
        )

    async def classify_batch(
        self,
        queries: List[str]
    ) -> List[ClassificationResult]:
        """
        Classify multiple queries (for batch testing).

        Args:
            queries: List of query strings.

        Returns:
            List of ClassificationResults.
        """
        import asyncio

        tasks = [self.classify(query) for query in queries]
        return await asyncio.gather(*tasks)


class RuleBasedClassifier:
    """
    Simple rule-based classifier as fallback.

    Uses keyword matching for basic intent detection.
    """

    def __init__(self):
        """Initialize keyword rules."""
        self.rules = self._build_rules()

    def _build_rules(self) -> Dict[str, List[str]]:
        """Build keyword rules from intent examples."""
        rules = {}
        for intent_id, intent in INTENT_REGISTRY.items():
            if not intent.enabled:
                continue

            keywords = set()
            for example in intent.examples_he + intent.examples_en:
                # Extract significant words
                words = example.lower().split()
                keywords.update(w for w in words if len(w) > 2)

            rules[intent_id] = list(keywords)

        return rules

    def classify(self, query: str) -> ClassificationResult:
        """
        Classify query using keyword matching.

        Args:
            query: User query.

        Returns:
            ClassificationResult with best match.
        """
        query_lower = query.lower()
        scores = {}

        for intent_id, keywords in self.rules.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                scores[intent_id] = score

        if not scores:
            intent_id = "rag.general"
            confidence = 0.3
        else:
            intent_id = max(scores, key=scores.get)
            max_score = scores[intent_id]
            # Normalize confidence (rough estimate)
            confidence = min(0.9, 0.3 + (max_score * 0.1))

        intent_def = get_intent(intent_id)
        if intent_def is None:
            intent_def = get_intent("rag.general")
            intent_id = "rag.general"

        agent_mapping = {
            "rag_agent": AgentType.RAG,
            "account_agent": AgentType.ACCOUNT,
            "transaction_agent": AgentType.TRANSACTION,
            "loan_agent": AgentType.LOAN,
            "support_agent": AgentType.SUPPORT,
            "analytics_agent": AgentType.ANALYTICS,
        }

        return ClassificationResult(
            intent_id=intent_id,
            category=IntentCategory(intent_def.category),
            confidence=confidence,
            parameters={},
            requires_auth=intent_def.requires_auth,
            requires_mfa=intent_def.requires_mfa,
            target_agent=agent_mapping.get(intent_def.target_agent, AgentType.RAG),
            reasoning="Rule-based classification"
        )


class HybridClassifier:
    """
    Hybrid classifier combining LLM and rule-based approaches.

    Uses LLM for primary classification with rule-based fallback.
    """

    def __init__(self, bedrock_client=None):
        """Initialize both classifiers."""
        self.llm_classifier = IntentClassifier(bedrock_client)
        self.rule_classifier = RuleBasedClassifier()

    async def classify(
        self,
        query: str,
        history: Optional[List[BaseMessage]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        use_llm: bool = True
    ) -> ClassificationResult:
        """
        Classify using hybrid approach.

        Args:
            query: User query.
            history: Conversation history.
            user_context: User context.
            use_llm: Whether to use LLM (can be disabled for testing).

        Returns:
            ClassificationResult.
        """
        if use_llm:
            try:
                result = await self.llm_classifier.classify(
                    query, history, user_context
                )

                # If confidence is too low, try rule-based
                if result.confidence < 0.5:
                    rule_result = self.rule_classifier.classify(query)
                    if rule_result.confidence > result.confidence:
                        return rule_result

                return result

            except Exception as e:
                logger.warning(f"LLM classification failed, using rules: {e}")
                return self.rule_classifier.classify(query)
        else:
            return self.rule_classifier.classify(query)
