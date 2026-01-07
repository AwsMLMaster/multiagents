"""
Advanced Guardrails for Digital Bank Chatbot.

Provides enhanced security and safety checks:
- Language appropriateness
- Bias detection and mitigation
- Fraud detection
- Abuse prevention
- Compliance checks
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Types
# =============================================================================

class GuardrailCategory(str, Enum):
    """Categories of guardrail checks."""
    LANGUAGE = "language"
    BIAS = "bias"
    FRAUD = "fraud"
    ABUSE = "abuse"
    COMPLIANCE = "compliance"
    PRIVACY = "privacy"


class RiskLevel(str, Enum):
    """Risk levels for detected issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionType(str, Enum):
    """Actions to take based on guardrail results."""
    ALLOW = "allow"
    WARN = "warn"
    MODIFY = "modify"
    BLOCK = "block"
    ESCALATE = "escalate"
    FLAG_REVIEW = "flag_review"


@dataclass
class GuardrailResult:
    """Result of a guardrail check."""
    passed: bool
    category: GuardrailCategory
    risk_level: RiskLevel
    action: ActionType
    reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    suggested_modification: Optional[str] = None
    flags: List[str] = field(default_factory=list)


@dataclass
class AggregatedGuardrailResult:
    """Aggregated result from all guardrail checks."""
    overall_passed: bool
    overall_action: ActionType
    results: List[GuardrailResult]
    highest_risk: RiskLevel
    blocked_categories: List[GuardrailCategory]
    warnings: List[str]
    modifications: List[str]


# =============================================================================
# Language Guardrail
# =============================================================================

class LanguageGuardrail:
    """
    Checks for language appropriateness.

    Detects:
    - Profanity and offensive language
    - Inappropriate tone
    - Non-professional language
    """

    def __init__(self):
        """Initialize language patterns."""
        # Hebrew profanity patterns (simplified)
        self.hebrew_profanity: Set[str] = {
            "זונה", "מניאק", "חרא", "זין", "כוס",
            # Add more as needed
        }

        # English profanity patterns
        self.english_profanity: Set[str] = {
            "fuck", "shit", "ass", "bitch", "damn",
            # Add more as needed
        }

        # Patterns for aggressive language
        self.aggressive_patterns: List[Pattern] = [
            re.compile(r"(אני\s+אתבע|אני\s+אדווח|אני\s+אהרוג)", re.U),
            re.compile(r"(I\s+will\s+sue|I\s+will\s+kill|I\s+will\s+destroy)", re.I),
            re.compile(r"(תמות|לך\s+למות|תתאבד)", re.U),
        ]

        # Patterns for condescending/rude language
        self.rude_patterns: List[Pattern] = [
            re.compile(r"(אתה\s+טיפש|אתה\s+מטומטם|חסר\s+תועלת)", re.U),
            re.compile(r"(you\s+are\s+stupid|you\s+are\s+useless|idiot)", re.I),
        ]

    def check(self, text: str, is_input: bool = True) -> GuardrailResult:
        """
        Check text for language appropriateness.

        Args:
            text: Text to check.
            is_input: True if user input, False if model output.

        Returns:
            GuardrailResult with check details.
        """
        text_lower = text.lower()
        issues = []
        risk_level = RiskLevel.LOW

        # Check for profanity
        found_profanity = []
        for word in self.hebrew_profanity | self.english_profanity:
            if word in text_lower:
                found_profanity.append(word)

        if found_profanity:
            issues.append(f"Profanity detected: {len(found_profanity)} words")
            risk_level = RiskLevel.MEDIUM

        # Check for aggressive language
        for pattern in self.aggressive_patterns:
            if pattern.search(text):
                issues.append("Aggressive/threatening language detected")
                risk_level = RiskLevel.HIGH
                break

        # Check for rude language
        for pattern in self.rude_patterns:
            if pattern.search(text):
                issues.append("Rude/condescending language detected")
                if risk_level == RiskLevel.LOW:
                    risk_level = RiskLevel.MEDIUM

        # Determine action
        if risk_level == RiskLevel.HIGH:
            action = ActionType.BLOCK if is_input else ActionType.MODIFY
        elif risk_level == RiskLevel.MEDIUM:
            action = ActionType.WARN
        else:
            action = ActionType.ALLOW

        return GuardrailResult(
            passed=risk_level == RiskLevel.LOW,
            category=GuardrailCategory.LANGUAGE,
            risk_level=risk_level,
            action=action,
            reason="; ".join(issues) if issues else None,
            details={"profanity_count": len(found_profanity)},
            flags=["profanity"] if found_profanity else [],
        )


# =============================================================================
# Bias Detection Guardrail
# =============================================================================

class BiasGuardrail:
    """
    Detects and mitigates bias in responses.

    Checks for:
    - Demographic bias (age, gender, ethnicity)
    - Socioeconomic bias
    - Discriminatory language
    - Unfair treatment patterns
    """

    def __init__(self):
        """Initialize bias detection patterns."""
        # Gender-biased language
        self.gender_bias_patterns: List[Tuple[Pattern, str]] = [
            (re.compile(r"נשים\s+(לא\s+מבינות|לא\s+יודעות)", re.U), "gender_stereotype"),
            (re.compile(r"גברים\s+(תמיד|לעולם)", re.U), "gender_stereotype"),
            (re.compile(r"women\s+(can't|don't|shouldn't)", re.I), "gender_stereotype"),
            (re.compile(r"men\s+(always|never)", re.I), "gender_stereotype"),
        ]

        # Age-biased language
        self.age_bias_patterns: List[Tuple[Pattern, str]] = [
            (re.compile(r"(זקנים|קשישים)\s+(לא\s+מבינים|לא\s+יודעים)", re.U), "age_stereotype"),
            (re.compile(r"(צעירים|ילדים)\s+(לא\s+אחראים)", re.U), "age_stereotype"),
            (re.compile(r"old\s+people\s+(can't|don't)", re.I), "age_stereotype"),
            (re.compile(r"young\s+people\s+(are\s+irresponsible)", re.I), "age_stereotype"),
        ]

        # Socioeconomic bias
        self.socioeconomic_patterns: List[Tuple[Pattern, str]] = [
            (re.compile(r"(עניים|חלשים)\s+(לא\s+יכולים)", re.U), "socioeconomic_bias"),
            (re.compile(r"poor\s+people\s+(can't|shouldn't)", re.I), "socioeconomic_bias"),
        ]

        # Discriminatory terms
        self.discriminatory_terms: Set[str] = {
            # Add specific discriminatory terms
        }

    def check(self, text: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """
        Check for bias in text.

        Args:
            text: Text to check.
            context: Optional context including user characteristics.

        Returns:
            GuardrailResult with bias analysis.
        """
        issues = []
        bias_types = []

        # Check gender bias
        for pattern, bias_type in self.gender_bias_patterns:
            if pattern.search(text):
                issues.append(f"Gender bias detected")
                bias_types.append(bias_type)

        # Check age bias
        for pattern, bias_type in self.age_bias_patterns:
            if pattern.search(text):
                issues.append(f"Age bias detected")
                bias_types.append(bias_type)

        # Check socioeconomic bias
        for pattern, bias_type in self.socioeconomic_patterns:
            if pattern.search(text):
                issues.append(f"Socioeconomic bias detected")
                bias_types.append(bias_type)

        # Check for differential treatment based on context
        if context:
            user_characteristics = context.get("user_characteristics", {})
            if self._check_differential_treatment(text, user_characteristics):
                issues.append("Potential differential treatment detected")
                bias_types.append("differential_treatment")

        # Determine risk level
        if len(bias_types) >= 2:
            risk_level = RiskLevel.HIGH
        elif bias_types:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # Determine action
        if risk_level == RiskLevel.HIGH:
            action = ActionType.MODIFY
        elif risk_level == RiskLevel.MEDIUM:
            action = ActionType.FLAG_REVIEW
        else:
            action = ActionType.ALLOW

        return GuardrailResult(
            passed=risk_level == RiskLevel.LOW,
            category=GuardrailCategory.BIAS,
            risk_level=risk_level,
            action=action,
            reason="; ".join(issues) if issues else None,
            details={"bias_types": bias_types},
            flags=bias_types,
        )

    def _check_differential_treatment(
        self,
        text: str,
        user_characteristics: Dict[str, Any]
    ) -> bool:
        """Check if response shows differential treatment."""
        # This would involve more sophisticated analysis
        # comparing responses across different user characteristics
        return False


# =============================================================================
# Fraud Detection Guardrail
# =============================================================================

class FraudGuardrail:
    """
    Detects potential fraud attempts.

    Checks for:
    - Social engineering attempts
    - Unusual transaction patterns
    - Account takeover signals
    - Money laundering indicators
    """

    def __init__(self):
        """Initialize fraud detection patterns."""
        # Social engineering patterns
        self.social_engineering_patterns: List[Tuple[Pattern, str]] = [
            # Urgency tactics
            (re.compile(r"(דחוף|מיידי|עכשיו\s+או\s+לעולם)", re.U), "urgency_tactic"),
            (re.compile(r"(urgent|immediately|act\s+now|limited\s+time)", re.I), "urgency_tactic"),
            # Authority impersonation
            (re.compile(r"(אני\s+מהבנק|נציג\s+הבנק\s+שלך)", re.U), "authority_claim"),
            (re.compile(r"(I\s+am\s+from\s+the\s+bank|bank\s+representative)", re.I), "authority_claim"),
            # Information fishing
            (re.compile(r"(מה\s+הסיסמה|תן\s+לי\s+את\s+הקוד)", re.U), "info_fishing"),
            (re.compile(r"(what\s+is\s+your\s+password|give\s+me\s+the\s+code)", re.I), "info_fishing"),
        ]

        # Suspicious transaction patterns
        self.suspicious_amount_threshold = 50000  # ILS
        self.rapid_transaction_threshold = 5  # transactions in short period

    def check(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        transaction_history: Optional[List[Dict]] = None
    ) -> GuardrailResult:
        """
        Check for fraud indicators.

        Args:
            text: Text to analyze.
            context: Request context.
            transaction_history: Recent transaction history.

        Returns:
            GuardrailResult with fraud analysis.
        """
        fraud_signals = []
        risk_level = RiskLevel.LOW

        # Check social engineering patterns
        for pattern, signal_type in self.social_engineering_patterns:
            if pattern.search(text):
                fraud_signals.append(signal_type)

        # Check for multiple fraud signals
        if "info_fishing" in fraud_signals:
            risk_level = RiskLevel.CRITICAL
        elif len(fraud_signals) >= 2:
            risk_level = RiskLevel.HIGH
        elif fraud_signals:
            risk_level = RiskLevel.MEDIUM

        # Check transaction context
        if context:
            transaction = context.get("pending_transaction", {})
            if transaction:
                amount = transaction.get("amount", 0)
                if amount > self.suspicious_amount_threshold:
                    fraud_signals.append("high_value_transaction")
                    if risk_level == RiskLevel.LOW:
                        risk_level = RiskLevel.MEDIUM

        # Check transaction velocity
        if transaction_history:
            recent_count = self._count_recent_transactions(transaction_history)
            if recent_count > self.rapid_transaction_threshold:
                fraud_signals.append("rapid_transactions")
                risk_level = max(risk_level, RiskLevel.HIGH)

        # Determine action
        if risk_level == RiskLevel.CRITICAL:
            action = ActionType.BLOCK
        elif risk_level == RiskLevel.HIGH:
            action = ActionType.ESCALATE
        elif risk_level == RiskLevel.MEDIUM:
            action = ActionType.FLAG_REVIEW
        else:
            action = ActionType.ALLOW

        return GuardrailResult(
            passed=risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM],
            category=GuardrailCategory.FRAUD,
            risk_level=risk_level,
            action=action,
            reason=f"Fraud signals detected: {', '.join(fraud_signals)}" if fraud_signals else None,
            details={"fraud_signals": fraud_signals},
            flags=fraud_signals,
        )

    def _count_recent_transactions(
        self,
        history: List[Dict],
        minutes: int = 30
    ) -> int:
        """Count transactions in recent time window."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return sum(
            1 for tx in history
            if datetime.fromisoformat(tx.get("timestamp", "")) > cutoff
        )


# =============================================================================
# Abuse Prevention Guardrail
# =============================================================================

class AbuseGuardrail:
    """
    Prevents system abuse and manipulation.

    Detects:
    - Harassment patterns
    - System manipulation attempts
    - Rate abuse
    - Conversation manipulation
    """

    def __init__(self):
        """Initialize abuse detection."""
        # Harassment patterns
        self.harassment_patterns: List[Pattern] = [
            re.compile(r"(אני\s+אמצא\s+אותך|אני\s+יודע\s+איפה)", re.U),
            re.compile(r"(I\s+will\s+find\s+you|I\s+know\s+where)", re.I),
            re.compile(r"(תשלם|תסבול)", re.U),
        ]

        # System manipulation patterns
        self.manipulation_patterns: List[Pattern] = [
            re.compile(r"(hack|exploit|bypass|overflow)", re.I),
            re.compile(r"(לפרוץ|לעקוף|לשנות\s+את\s+המערכת)", re.U),
        ]

        # Rate abuse thresholds
        self.max_requests_per_minute = 30
        self.max_requests_per_hour = 200

    def check(
        self,
        text: str,
        session_context: Optional[Dict[str, Any]] = None
    ) -> GuardrailResult:
        """
        Check for abuse patterns.

        Args:
            text: Text to analyze.
            session_context: Session context including request history.

        Returns:
            GuardrailResult with abuse analysis.
        """
        abuse_signals = []
        risk_level = RiskLevel.LOW

        # Check harassment patterns
        for pattern in self.harassment_patterns:
            if pattern.search(text):
                abuse_signals.append("harassment")
                risk_level = RiskLevel.HIGH
                break

        # Check manipulation patterns
        for pattern in self.manipulation_patterns:
            if pattern.search(text):
                abuse_signals.append("manipulation_attempt")
                risk_level = max(risk_level, RiskLevel.MEDIUM)
                break

        # Check rate abuse
        if session_context:
            request_count = session_context.get("request_count_minute", 0)
            if request_count > self.max_requests_per_minute:
                abuse_signals.append("rate_abuse")
                risk_level = RiskLevel.HIGH

        # Check for repetitive content (bot behavior)
        if session_context:
            recent_messages = session_context.get("recent_messages", [])
            if self._check_repetitive(text, recent_messages):
                abuse_signals.append("repetitive_behavior")
                risk_level = max(risk_level, RiskLevel.MEDIUM)

        # Determine action
        if risk_level == RiskLevel.HIGH:
            action = ActionType.BLOCK
        elif risk_level == RiskLevel.MEDIUM:
            action = ActionType.WARN
        else:
            action = ActionType.ALLOW

        return GuardrailResult(
            passed=risk_level == RiskLevel.LOW,
            category=GuardrailCategory.ABUSE,
            risk_level=risk_level,
            action=action,
            reason=f"Abuse signals: {', '.join(abuse_signals)}" if abuse_signals else None,
            details={"abuse_signals": abuse_signals},
            flags=abuse_signals,
        )

    def _check_repetitive(self, text: str, recent_messages: List[str]) -> bool:
        """Check if message is repetitive."""
        if len(recent_messages) < 3:
            return False

        # Check exact duplicates
        duplicate_count = sum(1 for msg in recent_messages if msg == text)
        if duplicate_count >= 2:
            return True

        # Check high similarity (simplified)
        text_words = set(text.lower().split())
        for msg in recent_messages[-5:]:
            msg_words = set(msg.lower().split())
            if len(text_words & msg_words) / max(len(text_words), 1) > 0.8:
                return True

        return False


# =============================================================================
# Compliance Guardrail
# =============================================================================

class ComplianceGuardrail:
    """
    Ensures regulatory compliance.

    Checks:
    - Financial advice restrictions
    - Disclosure requirements
    - Regulatory language requirements
    """

    def __init__(self):
        """Initialize compliance rules."""
        # Prohibited financial advice patterns
        self.prohibited_advice_patterns: List[Tuple[Pattern, str]] = [
            (re.compile(r"(תקנה|תמכור|תשקיע\s+ב)", re.U), "investment_advice"),
            (re.compile(r"(buy|sell|invest\s+in)\s+\w+\s+(stock|share|crypto)", re.I), "investment_advice"),
            (re.compile(r"(guaranteed|risk-free|certain\s+return)", re.I), "misleading_claim"),
            (re.compile(r"(מובטח|ללא\s+סיכון|תשואה\s+בטוחה)", re.U), "misleading_claim"),
        ]

        # Required disclaimers by topic
        self.required_disclaimers: Dict[str, str] = {
            "investment": "⚠️ מידע זה אינו מהווה המלצה להשקעה. התייעץ עם יועץ השקעות מוסמך.",
            "loan": "📋 החישוב להערכה בלבד. התנאים בפועל עשויים להשתנות.",
            "insurance": "📋 פרטי הביטוח כפופים לתנאי הפוליסה המלאים.",
        }

    def check(
        self,
        text: str,
        topic: Optional[str] = None
    ) -> GuardrailResult:
        """
        Check compliance requirements.

        Args:
            text: Text to analyze.
            topic: Topic of the conversation.

        Returns:
            GuardrailResult with compliance analysis.
        """
        issues = []
        risk_level = RiskLevel.LOW
        suggested_modification = None

        # Check for prohibited advice
        for pattern, issue_type in self.prohibited_advice_patterns:
            if pattern.search(text):
                issues.append(issue_type)
                if issue_type == "misleading_claim":
                    risk_level = RiskLevel.HIGH
                else:
                    risk_level = max(risk_level, RiskLevel.MEDIUM)

        # Check for missing required disclaimers
        if topic and topic in self.required_disclaimers:
            disclaimer = self.required_disclaimers[topic]
            if disclaimer not in text:
                issues.append("missing_disclaimer")
                suggested_modification = f"{text}\n\n{disclaimer}"

        # Determine action
        if risk_level == RiskLevel.HIGH:
            action = ActionType.BLOCK
        elif issues:
            action = ActionType.MODIFY
        else:
            action = ActionType.ALLOW

        return GuardrailResult(
            passed=not issues,
            category=GuardrailCategory.COMPLIANCE,
            risk_level=risk_level,
            action=action,
            reason=f"Compliance issues: {', '.join(issues)}" if issues else None,
            details={"issues": issues},
            suggested_modification=suggested_modification,
            flags=issues,
        )


# =============================================================================
# Advanced Guardrail Manager
# =============================================================================

class AdvancedGuardrailManager:
    """
    Manages all advanced guardrails.
    """

    def __init__(self):
        """Initialize all guardrails."""
        self.language = LanguageGuardrail()
        self.bias = BiasGuardrail()
        self.fraud = FraudGuardrail()
        self.abuse = AbuseGuardrail()
        self.compliance = ComplianceGuardrail()

    def check_input(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AggregatedGuardrailResult:
        """
        Run all guardrail checks on user input.

        Args:
            text: User input text.
            context: Request context.

        Returns:
            AggregatedGuardrailResult with all checks.
        """
        results = []

        # Language check
        results.append(self.language.check(text, is_input=True))

        # Fraud check
        results.append(self.fraud.check(text, context))

        # Abuse check
        session_context = context.get("session", {}) if context else {}
        results.append(self.abuse.check(text, session_context))

        return self._aggregate_results(results)

    def check_output(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        topic: Optional[str] = None
    ) -> AggregatedGuardrailResult:
        """
        Run all guardrail checks on model output.

        Args:
            text: Model output text.
            context: Request context.
            topic: Conversation topic.

        Returns:
            AggregatedGuardrailResult with all checks.
        """
        results = []

        # Language check
        results.append(self.language.check(text, is_input=False))

        # Bias check
        results.append(self.bias.check(text, context))

        # Compliance check
        results.append(self.compliance.check(text, topic))

        return self._aggregate_results(results)

    def _aggregate_results(
        self,
        results: List[GuardrailResult]
    ) -> AggregatedGuardrailResult:
        """Aggregate individual guardrail results."""
        # Determine highest risk
        risk_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        highest_risk = max(results, key=lambda r: risk_order.index(r.risk_level)).risk_level

        # Determine overall action
        action_priority = {
            ActionType.ALLOW: 0,
            ActionType.WARN: 1,
            ActionType.FLAG_REVIEW: 2,
            ActionType.MODIFY: 3,
            ActionType.ESCALATE: 4,
            ActionType.BLOCK: 5,
        }
        overall_action = max(results, key=lambda r: action_priority[r.action]).action

        # Collect blocked categories
        blocked_categories = [
            r.category for r in results
            if r.action == ActionType.BLOCK
        ]

        # Collect warnings
        warnings = [
            r.reason for r in results
            if r.reason and r.action in [ActionType.WARN, ActionType.FLAG_REVIEW]
        ]

        # Collect modifications
        modifications = [
            r.suggested_modification for r in results
            if r.suggested_modification
        ]

        overall_passed = overall_action in [ActionType.ALLOW, ActionType.WARN]

        return AggregatedGuardrailResult(
            overall_passed=overall_passed,
            overall_action=overall_action,
            results=results,
            highest_risk=highest_risk,
            blocked_categories=blocked_categories,
            warnings=warnings,
            modifications=modifications,
        )


# Singleton instance
_guardrail_manager: Optional[AdvancedGuardrailManager] = None


def get_advanced_guardrails() -> AdvancedGuardrailManager:
    """Get singleton guardrail manager."""
    global _guardrail_manager
    if _guardrail_manager is None:
        _guardrail_manager = AdvancedGuardrailManager()
    return _guardrail_manager
