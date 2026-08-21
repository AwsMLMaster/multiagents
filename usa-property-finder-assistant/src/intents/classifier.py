"""
Intent Classifier for USA Property Finder Assistant.

This module provides LLM-based intent classification with structured output
for real estate search, property, valuation, mortgage, neighborhood, market,
and scheduling queries.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .registry import (
    INTENT_REGISTRY,
    IntentCategory,
    get_intent,
)
from ..orchestrator.state import AgentType

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result from intent classification."""
    intent_id: str
    category: IntentCategory
    confidence: float
    parameters: Dict[str, Any]
    target_agent: AgentType
    reasoning: Optional[str] = None


CLASSIFICATION_SYSTEM_PROMPT = """You are the intent classification system for a USA property finder assistant.

Your job is to analyze the user's message and identify the specific intent from the list below.

## Available intents:

{intent_list}

## Instructions:
1. Analyze the user's message.
2. Identify the best matching intent from the list.
3. Extract relevant parameters mentioned in the message (locations, prices, bedrooms, dates, property references, etc).
4. If unclear, choose "rag.general" with low confidence.
5. Consider conversation context if provided.
6. Never infer or apply protected-class preferences (race, religion, national origin, sex, disability, familial status) into search parameters, even if implied by user phrasing — extract only legitimate, non-discriminatory criteria (price, size, location, features).

## Response format (JSON only, no markdown fences):
{{
    "intent_id": "string - the intent id from the list",
    "confidence": "float between 0 and 1",
    "parameters": {{
        "param_name": "extracted_value"
    }},
    "reasoning": "string - brief explanation"
}}

## Examples:

Input: "Find 3 bedroom homes in Austin under $500k"
Output: {{"intent_id": "search.properties", "confidence": 0.95, "parameters": {{"location": "Austin, TX", "bedrooms_min": 3, "price_max": 500000}}, "reasoning": "Direct search request with location, bedroom, and price criteria"}}

Input: "What's this house worth?"
Output: {{"intent_id": "valuation.estimate", "confidence": 0.9, "parameters": {{}}, "reasoning": "Asking for a value estimate on the currently discussed property"}}

Input: "What would my payment be with 10% down?"
Output: {{"intent_id": "mortgage.calculate", "confidence": 0.88, "parameters": {{"down_payment_percent": 10}}, "reasoning": "Mortgage payment calculation request"}}
"""


def build_intent_list() -> str:
    """Build formatted intent list for the classification prompt."""
    lines = []
    for intent_id, intent in INTENT_REGISTRY.items():
        if not intent.enabled:
            continue

        examples = intent.examples[:2]
        examples_str = ", ".join(f'"{ex}"' for ex in examples)
        params = ", ".join(intent.required_params) if intent.required_params else "none"

        lines.append(
            f"- **{intent_id}** ({intent.category.value}): {intent.description}\n"
            f"  required params: {params}\n"
            f"  examples: {examples_str}"
        )

    return "\n".join(lines)


class IntentClassifier:
    """
    LLM-based intent classifier for real estate queries.
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
            user_context: Optional buyer profile for personalization.

        Returns:
            ClassificationResult with intent details.
        """
        try:
            messages = self._build_messages(query, history)

            system_prompt = CLASSIFICATION_SYSTEM_PROMPT.format(
                intent_list=self._intent_list
            )

            response = await self.bedrock_client.invoke(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.0,
                max_tokens=500,
            )

            result = self._parse_response(response.content)
            return self._enrich_result(result)

        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            return ClassificationResult(
                intent_id="rag.general",
                category=IntentCategory.RAG,
                confidence=0.0,
                parameters={},
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

        if history:
            for msg in history[-6:]:
                role = "user" if msg.type == "human" else "assistant"
                messages.append({"role": role, "content": msg.content})

        messages.append({"role": "user", "content": query})
        return messages

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM response JSON."""
        try:
            content = content.strip()
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
            intent_def = get_intent("rag.general")
            intent_id = "rag.general"

        agent_mapping = {
            "rag_agent": AgentType.RAG,
            "search_agent": AgentType.SEARCH,
            "property_details_agent": AgentType.PROPERTY_DETAILS,
            "valuation_agent": AgentType.VALUATION,
            "mortgage_agent": AgentType.MORTGAGE,
            "neighborhood_agent": AgentType.NEIGHBORHOOD,
            "market_trends_agent": AgentType.MARKET_TRENDS,
            "scheduling_agent": AgentType.SCHEDULING,
        }

        target_agent = agent_mapping.get(intent_def.target_agent, AgentType.RAG)

        return ClassificationResult(
            intent_id=intent_id,
            category=IntentCategory(intent_def.category),
            confidence=parsed.get("confidence", 0.5),
            parameters=parsed.get("parameters", {}),
            target_agent=target_agent,
            reasoning=parsed.get("reasoning")
        )

    async def classify_batch(self, queries: List[str]) -> List[ClassificationResult]:
        """Classify multiple queries (for batch testing)."""
        import asyncio
        tasks = [self.classify(query) for query in queries]
        return await asyncio.gather(*tasks)


class RuleBasedClassifier:
    """
    Simple rule-based classifier used as a fast-path / fallback.
    """

    def __init__(self):
        self.rules = self._build_rules()

    def _build_rules(self) -> Dict[str, List[str]]:
        rules = {}
        for intent_id, intent in INTENT_REGISTRY.items():
            if not intent.enabled:
                continue
            keywords = set()
            for example in intent.examples:
                words = example.lower().split()
                keywords.update(w.strip("?.,!") for w in words if len(w) > 3)
            rules[intent_id] = list(keywords)
        return rules

    def classify(self, query: str) -> ClassificationResult:
        """Classify query using keyword matching."""
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
            confidence = min(0.9, 0.3 + (scores[intent_id] * 0.1))

        intent_def = get_intent(intent_id)
        if intent_def is None:
            intent_def = get_intent("rag.general")
            intent_id = "rag.general"

        agent_mapping = {
            "rag_agent": AgentType.RAG,
            "search_agent": AgentType.SEARCH,
            "property_details_agent": AgentType.PROPERTY_DETAILS,
            "valuation_agent": AgentType.VALUATION,
            "mortgage_agent": AgentType.MORTGAGE,
            "neighborhood_agent": AgentType.NEIGHBORHOOD,
            "market_trends_agent": AgentType.MARKET_TRENDS,
            "scheduling_agent": AgentType.SCHEDULING,
        }

        return ClassificationResult(
            intent_id=intent_id,
            category=IntentCategory(intent_def.category),
            confidence=confidence,
            parameters={},
            target_agent=agent_mapping.get(intent_def.target_agent, AgentType.RAG),
            reasoning="Rule-based classification"
        )


class HybridClassifier:
    """
    Hybrid classifier combining LLM and rule-based approaches.
    """

    def __init__(self, bedrock_client=None):
        self.llm_classifier = IntentClassifier(bedrock_client)
        self.rule_classifier = RuleBasedClassifier()

    async def classify(
        self,
        query: str,
        history: Optional[List[BaseMessage]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        use_llm: bool = True
    ) -> ClassificationResult:
        """Classify using hybrid approach."""
        if use_llm:
            try:
                result = await self.llm_classifier.classify(query, history, user_context)
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
