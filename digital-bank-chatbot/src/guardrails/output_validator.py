"""
Output Validation and Guardrails for Digital Bank Chatbot.

Provides security checks and content filtering for model outputs:
- PII leakage prevention
- Content safety validation
- Required disclaimers
- Response quality checks
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Pattern

logger = logging.getLogger(__name__)


@dataclass
class OutputValidationResult:
    """Result of output validation."""
    valid: bool
    blocked: bool = False
    reason: Optional[str] = None
    modified: bool = False
    modified_content: Optional[str] = None
    disclaimer_required: bool = False
    disclaimer: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    pii_detected: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# PII Patterns for Output Checking
# =============================================================================

OUTPUT_PII_PATTERNS: Dict[str, Pattern] = {
    "israeli_id": re.compile(r"\b\d{9}\b"),
    "credit_card_full": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "bank_account_full": re.compile(r"\b\d{2,3}[-\s]?\d{3}[-\s]?\d{7}\b"),
    "phone_full": re.compile(r"\b0[5-9]\d[-\s]?\d{3}[-\s]?\d{4}\b"),
}

# Patterns that should be masked in output
MASK_PATTERNS: Dict[str, tuple] = {
    "credit_card": (
        re.compile(r"\b(\d{4})[-\s]?(\d{4})[-\s]?(\d{4})[-\s]?(\d{4})\b"),
        r"\1-****-****-\4"  # Keep first and last 4 digits
    ),
    "bank_account": (
        re.compile(r"\b(\d{2,3})[-\s]?(\d{3})[-\s]?(\d{7})\b"),
        r"\1-***-***\3"  # Partial mask
    ),
}

# =============================================================================
# Disclaimer Definitions
# =============================================================================

DISCLAIMERS: Dict[str, str] = {
    "loan_calculator": (
        "📋 הערה: החישוב הוא הערכה בלבד. התנאים בפועל עשויים להשתנות "
        "בהתאם לבדיקת אשראי ולתנאי הבנק."
    ),
    "investment_info": (
        "⚠️ הבהרה: מידע זה הוא למטרות כלליות בלבד ואינו מהווה ייעוץ השקעות. "
        "ביצועי העבר אינם מעידים על תשואות עתידיות."
    ),
    "exchange_rate": (
        "💱 הערה: שערי החליפין המוצגים הם אינדיקטיביים ועשויים להשתנות."
    ),
    "financial_advice": (
        "📌 הבהרה: מידע זה הוא כללי בלבד ואינו מהווה ייעוץ פיננסי מקצועי. "
        "מומלץ להתייעץ עם יועץ מוסמך לפני קבלת החלטות פיננסיות."
    ),
    "product_info": (
        "ℹ️ המידע המוצג עדכני לתאריך הפרסום ועשוי להשתנות. "
        "לפרטים מלאים ועדכניים פנה לשירות הלקוחות."
    ),
}

# Intent to disclaimer mapping
INTENT_DISCLAIMERS: Dict[str, str] = {
    "loan.calculator": "loan_calculator",
    "loan.status": "loan_calculator",
    "loan.application": "financial_advice",
    "rag.products": "product_info",
    "analytics.spending": "financial_advice",
    "analytics.budget": "financial_advice",
}

# =============================================================================
# Blocked Output Patterns
# =============================================================================

BLOCKED_OUTPUT_PATTERNS: List[tuple] = [
    # Investment recommendations
    (
        re.compile(r"(recommend|suggest|advise).{0,20}(buy|sell|invest)", re.I),
        "אני לא יכול לספק המלצות השקעה ספציפיות."
    ),
    # Competitor mentions
    (
        re.compile(r"(better|worse|switch).{0,30}(bank|competitor)", re.I),
        "אני לא יכול להשוות בין מוסדות פיננסיים."
    ),
    # Legal advice
    (
        re.compile(r"(legal|lawsuit|sue|court)", re.I),
        "אני לא יכול לספק ייעוץ משפטי. מומלץ לפנות לעורך דין."
    ),
]

# Hebrew blocked patterns
HEBREW_BLOCKED_PATTERNS: List[tuple] = [
    (
        re.compile(r"(מומלץ|כדאי|עדיף).{0,20}(לקנות|למכור|להשקיע)", re.U),
        "אני לא יכול לספק המלצות השקעה ספציפיות."
    ),
    (
        re.compile(r"(בנק.{0,10}מתחרה|לעבור.{0,10}בנק)", re.U),
        "אני לא יכול להשוות בין מוסדות פיננסיים."
    ),
]


class OutputValidator:
    """
    Output validator for model responses.
    """

    def __init__(
        self,
        enable_pii_masking: bool = True,
        enable_disclaimers: bool = True,
        enable_content_check: bool = True,
        bedrock_guardrail_id: Optional[str] = None
    ):
        """
        Initialize output validator.

        Args:
            enable_pii_masking: Whether to mask PII in output.
            enable_disclaimers: Whether to add required disclaimers.
            enable_content_check: Whether to check content safety.
            bedrock_guardrail_id: Optional Bedrock guardrail ID.
        """
        self.enable_pii_masking = enable_pii_masking
        self.enable_disclaimers = enable_disclaimers
        self.enable_content_check = enable_content_check
        self.bedrock_guardrail_id = bedrock_guardrail_id

    def validate(
        self,
        content: str,
        intent: Optional[str] = None
    ) -> OutputValidationResult:
        """
        Validate model output.

        Args:
            content: Model output content.
            intent: Optional intent ID for disclaimer selection.

        Returns:
            OutputValidationResult with validation details.
        """
        result = OutputValidationResult(valid=True)
        modified_content = content
        warnings = []

        # Empty content check
        if not content or not content.strip():
            result.valid = False
            result.blocked = True
            result.reason = "תגובה ריקה מהמודל"
            return result

        # Content safety check
        if self.enable_content_check:
            blocked_result = self._check_blocked_content(content)
            if blocked_result:
                result.blocked = True
                result.valid = False
                result.reason = blocked_result
                return result

        # PII masking
        if self.enable_pii_masking:
            masked_content, pii_found = self._mask_pii(content)
            if pii_found:
                modified_content = masked_content
                result.modified = True
                result.pii_detected = pii_found
                warnings.append("PII detected and masked in response")
                logger.info(f"PII masked in output: {[p['type'] for p in pii_found]}")

        # Disclaimer check
        if self.enable_disclaimers and intent:
            disclaimer_key = INTENT_DISCLAIMERS.get(intent)
            if disclaimer_key:
                result.disclaimer_required = True
                result.disclaimer = DISCLAIMERS.get(disclaimer_key, "")

        result.modified_content = modified_content if result.modified else None
        result.warnings = warnings
        return result

    def _check_blocked_content(self, content: str) -> Optional[str]:
        """Check for blocked content patterns."""
        # Check English patterns
        for pattern, replacement in BLOCKED_OUTPUT_PATTERNS:
            if pattern.search(content):
                return replacement

        # Check Hebrew patterns
        for pattern, replacement in HEBREW_BLOCKED_PATTERNS:
            if pattern.search(content):
                return replacement

        return None

    def _mask_pii(self, content: str) -> tuple[str, List[Dict[str, Any]]]:
        """Mask PII in content."""
        masked = content
        pii_found = []

        # Apply masking patterns
        for pii_type, (pattern, replacement) in MASK_PATTERNS.items():
            matches = list(pattern.finditer(masked))
            for match in matches:
                pii_found.append({
                    "type": pii_type,
                    "position": match.start(),
                    "masked": True
                })
            masked = pattern.sub(replacement, masked)

        # Detect but don't mask other PII (for logging)
        for pii_type, pattern in OUTPUT_PII_PATTERNS.items():
            if pii_type not in [p["type"] for p in pii_found]:
                matches = pattern.findall(masked)
                if matches:
                    pii_found.append({
                        "type": pii_type,
                        "count": len(matches),
                        "masked": False
                    })

        return masked, pii_found


class ResponseQualityChecker:
    """
    Quality checks for model responses.
    """

    def __init__(
        self,
        min_length: int = 10,
        max_length: int = 2000,
        required_language: str = "he"
    ):
        """
        Initialize quality checker.

        Args:
            min_length: Minimum response length.
            max_length: Maximum response length.
            required_language: Required response language.
        """
        self.min_length = min_length
        self.max_length = max_length
        self.required_language = required_language

    def check(self, content: str) -> Dict[str, Any]:
        """
        Check response quality.

        Args:
            content: Response content.

        Returns:
            Dictionary with quality metrics.
        """
        quality = {
            "passed": True,
            "issues": [],
            "metrics": {}
        }

        # Length check
        length = len(content)
        quality["metrics"]["length"] = length

        if length < self.min_length:
            quality["passed"] = False
            quality["issues"].append(f"תגובה קצרה מדי ({length} תווים)")

        if length > self.max_length:
            quality["passed"] = False
            quality["issues"].append(f"תגובה ארוכה מדי ({length} תווים)")

        # Language check
        detected_lang = self._detect_language(content)
        quality["metrics"]["detected_language"] = detected_lang

        if detected_lang != self.required_language and detected_lang != "unknown":
            quality["issues"].append(
                f"שפת התגובה ({detected_lang}) לא תואמת את השפה הנדרשת ({self.required_language})"
            )

        # Coherence check (basic)
        if content.count("?") > 5:
            quality["issues"].append("תגובה מכילה יותר מדי סימני שאלה")

        # Repetition check
        words = content.split()
        if len(words) > 10:
            unique_ratio = len(set(words)) / len(words)
            quality["metrics"]["unique_word_ratio"] = unique_ratio
            if unique_ratio < 0.3:
                quality["issues"].append("תגובה מכילה חזרות רבות")

        return quality

    def _detect_language(self, text: str) -> str:
        """Detect primary language."""
        hebrew_chars = sum(
            1 for char in text
            if "\u0590" <= char <= "\u05FF"
        )
        total_alpha = sum(1 for char in text if char.isalpha())

        if total_alpha == 0:
            return "unknown"

        return "he" if hebrew_chars / total_alpha > 0.5 else "en"


class HallucinationDetector:
    """
    Basic hallucination detection for banking responses.
    """

    def __init__(self):
        """Initialize hallucination detector."""
        # Known valid patterns
        self.valid_account_pattern = re.compile(r"\b\d{2}-\d{3}-\d{7}\b")
        self.valid_amount_pattern = re.compile(r"[\d,]+\.?\d*\s*(₪|שקל|ש\"ח|ILS|NIS)", re.U)

    def check(
        self,
        response: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check for potential hallucinations.

        Args:
            response: Model response.
            context: Optional context with ground truth.

        Returns:
            Dictionary with hallucination check results.
        """
        result = {
            "suspected_hallucinations": [],
            "confidence": 1.0
        }

        # If no context, can only do basic checks
        if not context:
            # Check for suspiciously specific numbers without context
            specific_amounts = self.valid_amount_pattern.findall(response)
            if len(specific_amounts) > 3:
                result["suspected_hallucinations"].append({
                    "type": "excessive_specificity",
                    "detail": f"Found {len(specific_amounts)} specific amounts without context"
                })
                result["confidence"] = 0.7

            return result

        # With context, validate against ground truth
        if "user_balance" in context:
            mentioned_amounts = [
                m.group() for m in self.valid_amount_pattern.finditer(response)
            ]
            expected_balance = str(context["user_balance"])

            # Check if mentioned amount matches expected
            if mentioned_amounts:
                amounts_match = any(
                    expected_balance in amt.replace(",", "")
                    for amt in mentioned_amounts
                )
                if not amounts_match:
                    result["suspected_hallucinations"].append({
                        "type": "amount_mismatch",
                        "detail": f"Mentioned amounts don't match expected balance"
                    })
                    result["confidence"] = 0.5

        return result


def create_output_validator(
    bedrock_guardrail_id: Optional[str] = None
) -> OutputValidator:
    """
    Factory function to create output validator.

    Args:
        bedrock_guardrail_id: Optional Bedrock guardrail ID.

    Returns:
        Configured OutputValidator.
    """
    return OutputValidator(
        bedrock_guardrail_id=bedrock_guardrail_id
    )
