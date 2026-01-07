"""
Input Validation and Guardrails for Digital Bank Chatbot.

Provides security checks and content filtering for user inputs:
- Prompt injection detection
- PII detection
- Content safety
- Input sanitization
- Language detection
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Pattern, Set

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of input validation."""
    valid: bool
    blocked: bool = False
    reason: Optional[str] = None
    needs_auth: bool = False
    detected_language: str = "he"
    warnings: List[str] = field(default_factory=list)
    sanitized_input: Optional[str] = None
    detected_pii: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0


# =============================================================================
# Pattern Definitions
# =============================================================================

# Prompt injection patterns
INJECTION_PATTERNS: List[Pattern] = [
    re.compile(r"ignore\s+(previous|above|all)\s+(instructions?|prompts?)", re.I),
    re.compile(r"disregard\s+(previous|above|all)", re.I),
    re.compile(r"forget\s+(everything|all|previous)", re.I),
    re.compile(r"you\s+are\s+(now|a)\s+", re.I),
    re.compile(r"pretend\s+(you|to\s+be)", re.I),
    re.compile(r"act\s+as\s+(if|a)", re.I),
    re.compile(r"new\s+instruction", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"\[system\]", re.I),
    re.compile(r"<\s*system\s*>", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"DAN\s+mode", re.I),
]

# Hebrew prompt injection patterns
HEBREW_INJECTION_PATTERNS: List[Pattern] = [
    re.compile(r"התעלם\s+מ(הנחיות|כל)", re.U),
    re.compile(r"שכח\s+(הכל|את)", re.U),
    re.compile(r"הוראות\s+חדשות", re.U),
]

# PII patterns (Israeli formats)
PII_PATTERNS: Dict[str, Pattern] = {
    "israeli_id": re.compile(r"\b\d{9}\b"),  # Israeli ID number
    "credit_card": re.compile(
        r"\b(?:\d{4}[-\s]?){3}\d{4}\b"  # Credit card with optional separators
    ),
    "bank_account": re.compile(
        r"\b\d{2,3}[-\s]?\d{3}[-\s]?\d{7}\b"  # Israeli bank account
    ),
    "phone": re.compile(
        r"\b0[5-9]\d[-\s]?\d{3}[-\s]?\d{4}\b"  # Israeli phone
    ),
    "email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    ),
}

# Blocked topics/keywords
BLOCKED_KEYWORDS: Set[str] = {
    "password",
    "סיסמה",
    "pin",
    "פין",
    "cvv",
    "security code",
    "קוד אבטחה",
}

# Suspicious patterns that warrant warning
SUSPICIOUS_PATTERNS: List[Pattern] = [
    re.compile(r"(all|every)\s+(account|customer|user)", re.I),
    re.compile(r"הכל|כולם", re.U),  # Hebrew: all/everyone
    re.compile(r"admin|administrator|root|sudo", re.I),
    re.compile(r"sql|database|query", re.I),
    re.compile(r"<script|javascript|onclick", re.I),
]


class InputValidator:
    """
    Input validator with multiple security checks.
    """

    def __init__(
        self,
        max_length: int = 2000,
        enable_pii_detection: bool = True,
        enable_injection_detection: bool = True,
        bedrock_guardrail_id: Optional[str] = None
    ):
        """
        Initialize input validator.

        Args:
            max_length: Maximum input length.
            enable_pii_detection: Whether to detect PII.
            enable_injection_detection: Whether to detect prompt injection.
            bedrock_guardrail_id: Optional Bedrock guardrail ID.
        """
        self.max_length = max_length
        self.enable_pii_detection = enable_pii_detection
        self.enable_injection_detection = enable_injection_detection
        self.bedrock_guardrail_id = bedrock_guardrail_id

    def validate(self, input_text: str) -> ValidationResult:
        """
        Validate user input.

        Args:
            input_text: Raw user input.

        Returns:
            ValidationResult with validation details.
        """
        # Initialize result
        result = ValidationResult(valid=True)
        warnings = []

        # Check for empty input
        if not input_text or not input_text.strip():
            result.sanitized_input = ""
            result.detected_language = "unknown"
            return result

        # Length check
        if len(input_text) > self.max_length:
            result.blocked = True
            result.valid = False
            result.reason = f"קלט ארוך מדי (מקסימום {self.max_length} תווים)"
            return result

        # Sanitize input
        sanitized = self._sanitize(input_text)
        result.sanitized_input = sanitized

        # Detect language
        result.detected_language = self._detect_language(sanitized)

        # Prompt injection detection
        if self.enable_injection_detection:
            injection_result = self._check_injection(sanitized)
            if injection_result:
                result.blocked = True
                result.valid = False
                result.reason = "זוהתה ניסיון לעקוף מגבלות המערכת"
                logger.warning(f"Prompt injection detected: {injection_result}")
                return result

        # PII detection
        if self.enable_pii_detection:
            pii_found = self._detect_pii(sanitized)
            if pii_found:
                result.detected_pii = pii_found
                warnings.append("זוהה מידע אישי רגיש בקלט")
                logger.info(f"PII detected: {[p['type'] for p in pii_found]}")

        # Blocked keywords check
        blocked = self._check_blocked_keywords(sanitized)
        if blocked:
            result.blocked = True
            result.valid = False
            result.reason = "הקלט מכיל מילים חסומות"
            return result

        # Suspicious patterns check
        suspicious = self._check_suspicious(sanitized)
        if suspicious:
            warnings.extend(suspicious)

        result.warnings = warnings
        return result

    def _sanitize(self, text: str) -> str:
        """Sanitize input text."""
        # Remove null bytes
        text = text.replace("\x00", "")

        # Normalize whitespace
        text = " ".join(text.split())

        # Remove control characters (except newlines)
        text = "".join(
            char for char in text
            if char == "\n" or not (0 <= ord(char) < 32)
        )

        # Basic XSS prevention
        text = text.replace("<", "&lt;").replace(">", "&gt;")

        return text.strip()

    def _detect_language(self, text: str) -> str:
        """Detect primary language of text."""
        # Count Hebrew vs non-Hebrew characters
        hebrew_chars = sum(
            1 for char in text
            if "\u0590" <= char <= "\u05FF"  # Hebrew Unicode block
        )

        total_alpha = sum(1 for char in text if char.isalpha())

        if total_alpha == 0:
            return "unknown"

        hebrew_ratio = hebrew_chars / total_alpha

        if hebrew_ratio > 0.5:
            return "he"
        else:
            return "en"

    def _check_injection(self, text: str) -> Optional[str]:
        """Check for prompt injection patterns."""
        # Check English patterns
        for pattern in INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                return f"English injection: {match.group()}"

        # Check Hebrew patterns
        for pattern in HEBREW_INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                return f"Hebrew injection: {match.group()}"

        return None

    def _detect_pii(self, text: str) -> List[Dict[str, Any]]:
        """Detect PII in text."""
        found = []

        for pii_type, pattern in PII_PATTERNS.items():
            matches = pattern.findall(text)
            for match in matches:
                found.append({
                    "type": pii_type,
                    "value": self._mask_pii(match),
                    "original_length": len(match)
                })

        return found

    def _mask_pii(self, value: str) -> str:
        """Mask PII value for logging."""
        if len(value) <= 4:
            return "****"
        return value[:2] + "*" * (len(value) - 4) + value[-2:]

    def _check_blocked_keywords(self, text: str) -> bool:
        """Check for blocked keywords."""
        text_lower = text.lower()
        for keyword in BLOCKED_KEYWORDS:
            if keyword in text_lower:
                return True
        return False

    def _check_suspicious(self, text: str) -> List[str]:
        """Check for suspicious patterns (warnings only)."""
        warnings = []

        for pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(text):
                warnings.append("זוהה דפוס חשוד בקלט")
                break

        return warnings


class BedrockGuardrailValidator:
    """
    AWS Bedrock Guardrails integration for input validation.
    """

    def __init__(self, guardrail_id: str, guardrail_version: str = "DRAFT"):
        """
        Initialize Bedrock guardrail validator.

        Args:
            guardrail_id: Bedrock guardrail identifier.
            guardrail_version: Guardrail version.
        """
        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Bedrock client."""
        if self._client is None:
            import boto3
            self._client = boto3.client("bedrock-runtime")
        return self._client

    async def validate(self, text: str) -> ValidationResult:
        """
        Validate input using Bedrock Guardrails.

        Args:
            text: Input text to validate.

        Returns:
            ValidationResult with guardrail assessment.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.apply_guardrail(
                    guardrailIdentifier=self.guardrail_id,
                    guardrailVersion=self.guardrail_version,
                    source="INPUT",
                    content=[{"text": {"text": text}}]
                )
            )

            action = response.get("action", "")
            blocked = action == "GUARDRAIL_INTERVENED"

            warnings = []
            reason = None

            if blocked:
                # Extract reason from assessments
                for assessment in response.get("assessments", []):
                    for policy in assessment.get("topicPolicy", {}).get("topics", []):
                        if policy.get("action") == "BLOCKED":
                            reason = f"נושא חסום: {policy.get('name', 'לא ידוע')}"
                            break

                    for filter_result in assessment.get("contentPolicy", {}).get("filters", []):
                        if filter_result.get("action") == "BLOCKED":
                            reason = f"תוכן לא הולם: {filter_result.get('type', 'לא ידוע')}"
                            break

            return ValidationResult(
                valid=not blocked,
                blocked=blocked,
                reason=reason,
                warnings=warnings,
                confidence=response.get("guardrailCoverage", {}).get("textCharacters", {}).get("guarded", 0) / 100
            )

        except Exception as e:
            logger.error(f"Bedrock guardrail validation error: {e}")
            # Fail open - allow through but log
            return ValidationResult(
                valid=True,
                warnings=[f"לא ניתן לבצע בדיקת guardrail: {str(e)}"]
            )


def create_input_validator(
    bedrock_guardrail_id: Optional[str] = None,
    max_length: int = 2000
) -> InputValidator:
    """
    Factory function to create input validator.

    Args:
        bedrock_guardrail_id: Optional Bedrock guardrail ID.
        max_length: Maximum input length.

    Returns:
        Configured InputValidator.
    """
    return InputValidator(
        max_length=max_length,
        bedrock_guardrail_id=bedrock_guardrail_id
    )
