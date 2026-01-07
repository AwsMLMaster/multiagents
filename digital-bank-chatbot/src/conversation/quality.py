"""
Conversation Quality Manager

Evaluates and scores conversation quality based on product team guidelines.
Provides real-time guidance and post-conversation analysis.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .guidelines import (
    ConversationGuidelines,
    ToneGuideline,
    ResponseLengthGuideline,
    ContentGuideline,
    ToneType,
    ResponseLength,
)
from .flow_templates import ConversationTemplate, FlowStep, StepType

logger = logging.getLogger(__name__)


class QualityMetric(Enum):
    """Quality metrics for evaluation."""
    TONE_APPROPRIATENESS = "tone_appropriateness"
    RESPONSE_LENGTH = "response_length"
    STRUCTURE_ADHERENCE = "structure_adherence"
    CONTENT_ACCURACY = "content_accuracy"
    PERSONALIZATION = "personalization"
    RESPONSE_TIME = "response_time"
    RESOLUTION_RATE = "resolution_rate"
    ESCALATION_HANDLING = "escalation_handling"
    COMPLIANCE = "compliance"
    USER_SATISFACTION = "user_satisfaction"


@dataclass
class QualityScore:
    """Score for a single quality metric."""
    metric: QualityMetric
    score: float  # 0.0 to 1.0
    weight: float = 1.0
    details: str = ""
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    turn_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    response_time_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationEvaluation:
    """Complete evaluation of a conversation."""
    conversation_id: str
    session_id: str
    customer_id: str

    # Scores
    overall_score: float
    metric_scores: List[QualityScore] = field(default_factory=list)

    # Analysis
    total_turns: int = 0
    user_turns: int = 0
    assistant_turns: int = 0
    avg_response_time_ms: float = 0
    was_resolved: bool = False
    was_escalated: bool = False

    # Issues and suggestions
    critical_issues: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)

    # Metadata
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    guidelines_version: str = ""


class ConversationQualityManager:
    """
    Manages conversation quality evaluation.

    Provides:
    - Real-time guidance during conversations
    - Post-conversation evaluation
    - Quality trend analysis
    - Improvement recommendations
    """

    def __init__(
        self,
        guidelines: Optional[ConversationGuidelines] = None,
    ):
        from .guidelines import create_default_guidelines
        self.guidelines = guidelines or create_default_guidelines()

        # Metric weights
        self.metric_weights = {
            QualityMetric.TONE_APPROPRIATENESS: 0.15,
            QualityMetric.RESPONSE_LENGTH: 0.10,
            QualityMetric.STRUCTURE_ADHERENCE: 0.10,
            QualityMetric.CONTENT_ACCURACY: 0.20,
            QualityMetric.PERSONALIZATION: 0.10,
            QualityMetric.RESPONSE_TIME: 0.10,
            QualityMetric.RESOLUTION_RATE: 0.15,
            QualityMetric.COMPLIANCE: 0.10,
        }

    # ==================== Real-time Guidance ====================

    def get_response_guidance(
        self,
        intent: str,
        context: Dict[str, Any],
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Get guidance for generating a response.

        Returns guidelines for tone, length, structure, and content.
        """
        # Find applicable tone guideline
        tone_guideline = self._get_tone_guideline(intent, context)

        # Find applicable length guideline
        length_guideline = self._get_length_guideline(intent, context)

        # Find applicable content guideline
        content_guideline = self._get_content_guideline(intent)

        return {
            "tone": {
                "type": tone_guideline.tone_type.value if tone_guideline else "professional",
                "formality": tone_guideline.formality_level if tone_guideline else 3,
                "empathy": tone_guideline.empathy_level if tone_guideline else 3,
                "use_name": tone_guideline.use_customer_name if tone_guideline else True,
                "acknowledgment_phrases": (
                    tone_guideline.acknowledgment_phrases_he
                    if tone_guideline else []
                ),
            },
            "length": {
                "type": length_guideline.length.value if length_guideline else "standard",
                "min_words": length_guideline.min_words if length_guideline else 15,
                "max_words": length_guideline.max_words if length_guideline else 80,
                "use_bullets": length_guideline.use_bullet_points if length_guideline else False,
            },
            "content": {
                "required_disclaimers": (
                    content_guideline.required_disclaimers
                    if content_guideline else []
                ),
                "confirm_amounts": (
                    content_guideline.always_confirm_amounts
                    if content_guideline else True
                ),
                "show_fees": (
                    content_guideline.always_show_fees
                    if content_guideline else True
                ),
            },
            "timing": {
                "target_ms": self.guidelines.timing_guidelines[0].expected_response_time_ms
                if self.guidelines.timing_guidelines else 2000,
            },
        }

    def validate_response(
        self,
        response: str,
        intent: str,
        context: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Validate a response before sending.

        Returns (is_valid, list of issues).
        """
        issues = []

        # Check length
        word_count = len(response.split())
        length_guideline = self._get_length_guideline(intent, context)
        if length_guideline:
            if word_count < length_guideline.min_words:
                issues.append(f"Response too short ({word_count} words, min {length_guideline.min_words})")
            if word_count > length_guideline.max_words:
                issues.append(f"Response too long ({word_count} words, max {length_guideline.max_words})")

        # Check content requirements
        content_guideline = self._get_content_guideline(intent)
        if content_guideline:
            for disclaimer in content_guideline.required_disclaimers:
                if disclaimer not in response:
                    issues.append(f"Missing required disclaimer: {disclaimer}")

            for prohibited in content_guideline.prohibited_topics:
                if prohibited.lower() in response.lower():
                    issues.append(f"Contains prohibited content: {prohibited}")

        # Check compliance
        if self.guidelines.require_compliance_check:
            compliance_issues = self._check_compliance(response, intent)
            issues.extend(compliance_issues)

        is_valid = len(issues) == 0
        return is_valid, issues

    # ==================== Post-conversation Evaluation ====================

    def evaluate_conversation(
        self,
        conversation_id: str,
        session_id: str,
        customer_id: str,
        turns: List[ConversationTurn],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationEvaluation:
        """
        Evaluate a complete conversation.

        Analyzes all turns and produces quality scores.
        """
        evaluation = ConversationEvaluation(
            conversation_id=conversation_id,
            session_id=session_id,
            customer_id=customer_id,
            overall_score=0.0,
            total_turns=len(turns),
            guidelines_version=self.guidelines.version,
        )

        if not turns:
            return evaluation

        # Count turns
        user_turns = [t for t in turns if t.role == "user"]
        assistant_turns = [t for t in turns if t.role == "assistant"]
        evaluation.user_turns = len(user_turns)
        evaluation.assistant_turns = len(assistant_turns)

        # Calculate average response time
        response_times = [
            t.response_time_ms for t in assistant_turns
            if t.response_time_ms is not None
        ]
        if response_times:
            evaluation.avg_response_time_ms = sum(response_times) / len(response_times)

        # Evaluate each metric
        scores = []

        # Tone appropriateness
        tone_score = self._evaluate_tone(assistant_turns, turns)
        scores.append(tone_score)

        # Response length
        length_score = self._evaluate_length(assistant_turns)
        scores.append(length_score)

        # Response time
        time_score = self._evaluate_response_time(assistant_turns)
        scores.append(time_score)

        # Resolution rate
        resolution_score = self._evaluate_resolution(turns, metadata)
        scores.append(resolution_score)
        evaluation.was_resolved = resolution_score.score >= 0.8

        # Compliance
        compliance_score = self._evaluate_compliance(assistant_turns)
        scores.append(compliance_score)

        evaluation.metric_scores = scores

        # Calculate overall score
        weighted_sum = sum(
            s.score * self.metric_weights.get(s.metric, 0.1)
            for s in scores
        )
        total_weight = sum(
            self.metric_weights.get(s.metric, 0.1)
            for s in scores
        )
        evaluation.overall_score = weighted_sum / total_weight if total_weight > 0 else 0

        # Collect issues and suggestions
        for score in scores:
            if score.score < 0.6:
                evaluation.critical_issues.extend(score.issues)
            evaluation.improvement_suggestions.extend(score.suggestions)

        return evaluation

    # ==================== Private Helper Methods ====================

    def _get_tone_guideline(
        self,
        intent: str,
        context: Dict[str, Any],
    ) -> Optional[ToneGuideline]:
        """Get applicable tone guideline."""
        for guideline in self.guidelines.tone_guidelines:
            if intent in guideline.applies_to_intents:
                return guideline
            for ctx in guideline.applies_to_contexts:
                if ctx in context.get("contexts", []):
                    return guideline

        # Return default
        for guideline in self.guidelines.tone_guidelines:
            if not guideline.applies_to_intents and not guideline.applies_to_contexts:
                return guideline

        return None

    def _get_length_guideline(
        self,
        intent: str,
        context: Dict[str, Any],
    ) -> Optional[ResponseLengthGuideline]:
        """Get applicable length guideline."""
        for guideline in self.guidelines.length_guidelines:
            if intent in guideline.applies_to_intents:
                return guideline

        # Return default
        for guideline in self.guidelines.length_guidelines:
            if not guideline.applies_to_intents:
                return guideline

        return None

    def _get_content_guideline(self, intent: str) -> Optional[ContentGuideline]:
        """Get applicable content guideline."""
        for guideline in self.guidelines.content_guidelines:
            if intent in guideline.applies_to_intents:
                return guideline
        return None

    def _check_compliance(self, response: str, intent: str) -> List[str]:
        """Check response for compliance issues."""
        issues = []

        # Check for financial advice disclaimers for relevant intents
        financial_intents = ["loan", "invest", "savings", "offerings"]
        if any(fi in intent for fi in financial_intents):
            if "guarantee" in response.lower() or "מובטח" in response:
                issues.append("Avoid guaranteed return language")

        return issues

    def _evaluate_tone(
        self,
        assistant_turns: List[ConversationTurn],
        all_turns: List[ConversationTurn],
    ) -> QualityScore:
        """Evaluate tone appropriateness."""
        issues = []
        suggestions = []

        # Simple heuristic checks
        for turn in assistant_turns:
            content = turn.content.lower()

            # Check for negative phrases
            negative_phrases = ["לצערי", "אי אפשר", "אין מה לעשות", "unfortunately"]
            for phrase in negative_phrases:
                if phrase in content:
                    issues.append(f"Negative phrase used: {phrase}")
                    suggestions.append("Use more positive framing")

            # Check for abrupt responses
            if len(turn.content.split()) < 5 and turn.metadata.get("is_error_response"):
                issues.append("Response too abrupt for error handling")
                suggestions.append("Add empathetic acknowledgment for errors")

        # Calculate score based on issues
        score = max(0, 1.0 - (len(issues) * 0.2))

        return QualityScore(
            metric=QualityMetric.TONE_APPROPRIATENESS,
            score=score,
            weight=self.metric_weights[QualityMetric.TONE_APPROPRIATENESS],
            issues=issues,
            suggestions=suggestions,
        )

    def _evaluate_length(
        self,
        assistant_turns: List[ConversationTurn],
    ) -> QualityScore:
        """Evaluate response length appropriateness."""
        issues = []
        suggestions = []

        for turn in assistant_turns:
            word_count = len(turn.content.split())

            if word_count < 5:
                issues.append(f"Response too short: {word_count} words")
                suggestions.append("Provide more complete responses")
            elif word_count > 150:
                issues.append(f"Response too long: {word_count} words")
                suggestions.append("Be more concise")

        # Calculate score
        violation_ratio = len(issues) / max(len(assistant_turns), 1)
        score = max(0, 1.0 - violation_ratio)

        return QualityScore(
            metric=QualityMetric.RESPONSE_LENGTH,
            score=score,
            weight=self.metric_weights[QualityMetric.RESPONSE_LENGTH],
            issues=issues,
            suggestions=suggestions,
        )

    def _evaluate_response_time(
        self,
        assistant_turns: List[ConversationTurn],
    ) -> QualityScore:
        """Evaluate response time."""
        issues = []
        suggestions = []

        target_time = 2000  # Default target
        if self.guidelines.timing_guidelines:
            target_time = self.guidelines.timing_guidelines[0].expected_response_time_ms

        slow_responses = 0
        for turn in assistant_turns:
            if turn.response_time_ms and turn.response_time_ms > target_time * 2:
                slow_responses += 1
                issues.append(f"Slow response: {turn.response_time_ms}ms")

        if slow_responses > 0:
            suggestions.append("Investigate slow response causes")

        # Calculate score
        slow_ratio = slow_responses / max(len(assistant_turns), 1)
        score = max(0, 1.0 - slow_ratio)

        return QualityScore(
            metric=QualityMetric.RESPONSE_TIME,
            score=score,
            weight=self.metric_weights[QualityMetric.RESPONSE_TIME],
            details=f"Avg response time tracked",
            issues=issues,
            suggestions=suggestions,
        )

    def _evaluate_resolution(
        self,
        turns: List[ConversationTurn],
        metadata: Optional[Dict[str, Any]],
    ) -> QualityScore:
        """Evaluate whether the conversation was resolved."""
        issues = []
        suggestions = []

        # Check metadata for resolution flag
        was_resolved = metadata.get("was_resolved", False) if metadata else False

        # Check for escalation
        was_escalated = metadata.get("was_escalated", False) if metadata else False

        # Check last user message for satisfaction indicators
        if turns:
            last_user_turns = [t for t in turns if t.role == "user"]
            if last_user_turns:
                last_message = last_user_turns[-1].content.lower()
                positive_indicators = ["תודה", "thanks", "מעולה", "great", "perfect"]
                negative_indicators = ["לא עזר", "didn't help", "עדיין", "still"]

                if any(p in last_message for p in positive_indicators):
                    was_resolved = True
                if any(n in last_message for n in negative_indicators):
                    was_resolved = False
                    issues.append("Customer indicated issue not resolved")

        score = 1.0 if was_resolved else 0.5 if was_escalated else 0.3

        if not was_resolved and not was_escalated:
            suggestions.append("Ensure clear resolution or escalation")

        return QualityScore(
            metric=QualityMetric.RESOLUTION_RATE,
            score=score,
            weight=self.metric_weights[QualityMetric.RESOLUTION_RATE],
            details=f"Resolved: {was_resolved}, Escalated: {was_escalated}",
            issues=issues,
            suggestions=suggestions,
        )

    def _evaluate_compliance(
        self,
        assistant_turns: List[ConversationTurn],
    ) -> QualityScore:
        """Evaluate compliance with regulations."""
        issues = []
        suggestions = []

        for turn in assistant_turns:
            content = turn.content.lower()

            # Check for guaranteed returns language
            if "guaranteed" in content or "מובטח" in content:
                if "return" in content or "תשואה" in content:
                    issues.append("Avoid guaranteed return promises")

            # Check for missing disclaimers in financial advice
            intent = turn.metadata.get("intent", "")
            if "loan" in intent or "invest" in intent:
                if "כפוף" not in turn.content and "subject to" not in content:
                    suggestions.append("Consider adding 'subject to approval' disclaimer")

        score = max(0, 1.0 - (len(issues) * 0.3))

        return QualityScore(
            metric=QualityMetric.COMPLIANCE,
            score=score,
            weight=self.metric_weights[QualityMetric.COMPLIANCE],
            issues=issues,
            suggestions=suggestions,
        )
