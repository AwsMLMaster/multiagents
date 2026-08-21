"""
Input Validation and Guardrails for USA Property Finder Assistant.

Provides security and compliance checks for user inputs:
- Prompt injection detection
- PII detection
- Fair Housing Act compliance (blocks steering/discriminatory search requests)
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
    detected_language: str = "en"
    warnings: List[str] = field(default_factory=list)
    sanitized_input: Optional[str] = None
    detected_pii: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0


# =============================================================================
# Pattern Definitions
# =============================================================================

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

# PII patterns (US formats) - collected only to warn/mask, never required for search
PII_PATTERNS: Dict[str, Pattern] = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "bank_account": re.compile(r"\b\d{8,17}\b"),
    "phone": re.compile(r"\b(\+1[-\s]?)?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
}

# =============================================================================
# Fair Housing Act (42 U.S.C. 3601 et seq.) Compliance
#
# It is illegal to make, print, or publish any statement that indicates a
# preference, limitation, or discrimination based on race, color, religion,
# sex, disability, familial status, or national origin ("steering"). The
# assistant must refuse to filter or recommend properties/neighborhoods on
# these bases, regardless of how the request is phrased.
# =============================================================================

FAIR_HOUSING_PROTECTED_CLASS_PATTERNS: List[Pattern] = [
    re.compile(r"\bno\s+(kids|children)\b", re.I),
    re.compile(
        r"\b(white|black|asian|hispanic|latino)\s+"
        r"(neighborhoods?|areas?|communit(?:y|ies)|families?|people)\b", re.I
    ),
    re.compile(r"\b(christian|muslim|jewish)[-\s]only\b", re.I),
    re.compile(r"\b(no|not|don'?t|avoid|exclude|refuse)\b.{0,60}\bsection\s*8\b", re.I),
    re.compile(r"\b(no|not|don'?t|avoid|exclude)\b.{0,40}\bdisab(?:led|ilit(?:y|ies))\b", re.I),
    re.compile(
        r"\bavoid\s+(neighborhoods?|areas?)\s+with\s+.{0,30}"
        r"(immigrants?|muslims?|jews?|blacks?|hispanics?)\b", re.I
    ),
    re.compile(r"\bsteer\s+(me\s+)?away\s+from\b", re.I),
    re.compile(r"\bkeep\s+out\s+(minorities|immigrants)\b", re.I),
]

FAIR_HOUSING_REFUSAL_MESSAGE = (
    "I can't filter or recommend properties or neighborhoods based on race, color, "
    "religion, sex, disability, familial status, or national origin — that's "
    "prohibited by the federal Fair Housing Act. I'm happy to help you search by "
    "objective criteria like price, size, location, school ratings, or amenities."
)

# Blocked topics/keywords
BLOCKED_KEYWORDS: Set[str] = {
    "social security number",
    "credit card number",
    "wire transfer instructions",
}

SUSPICIOUS_PATTERNS: List[Pattern] = [
    re.compile(r"admin|administrator|root|sudo", re.I),
    re.compile(r"sql|database|query", re.I),
    re.compile(r"<script|javascript|onclick", re.I),
]


class InputValidator:
    """
    Input validator with security and Fair Housing compliance checks.
    """

    def __init__(
        self,
        max_length: int = 2000,
        enable_pii_detection: bool = True,
        enable_injection_detection: bool = True,
        enable_fair_housing_guard: bool = True,
        bedrock_guardrail_id: Optional[str] = None
    ):
        """
        Initialize input validator.

        Args:
            max_length: Maximum input length.
            enable_pii_detection: Whether to detect PII.
            enable_injection_detection: Whether to detect prompt injection.
            enable_fair_housing_guard: Whether to enforce Fair Housing Act compliance.
            bedrock_guardrail_id: Optional Bedrock guardrail ID.
        """
        self.max_length = max_length
        self.enable_pii_detection = enable_pii_detection
        self.enable_injection_detection = enable_injection_detection
        self.enable_fair_housing_guard = enable_fair_housing_guard
        self.bedrock_guardrail_id = bedrock_guardrail_id

    def validate(self, input_text: str) -> ValidationResult:
        """
        Validate user input.

        Args:
            input_text: Raw user input.

        Returns:
            ValidationResult with validation details.
        """
        result = ValidationResult(valid=True)
        warnings = []

        if not input_text or not input_text.strip():
            result.sanitized_input = ""
            result.detected_language = "unknown"
            return result

        if len(input_text) > self.max_length:
            result.blocked = True
            result.valid = False
            result.reason = f"Input too long (max {self.max_length} characters)"
            return result

        sanitized = self._sanitize(input_text)
        result.sanitized_input = sanitized
        result.detected_language = self._detect_language(sanitized)

        if self.enable_injection_detection:
            injection_result = self._check_injection(sanitized)
            if injection_result:
                result.blocked = True
                result.valid = False
                result.reason = "This request appears to try to override system instructions."
                logger.warning(f"Prompt injection detected: {injection_result}")
                return result

        # Fair Housing Act compliance - highest priority domain guardrail
        if self.enable_fair_housing_guard:
            violation = self._check_fair_housing(sanitized)
            if violation:
                result.blocked = True
                result.valid = False
                result.reason = FAIR_HOUSING_REFUSAL_MESSAGE
                logger.warning(f"Fair Housing Act guardrail triggered: {violation}")
                return result

        if self.enable_pii_detection:
            pii_found = self._detect_pii(sanitized)
            if pii_found:
                result.detected_pii = pii_found
                warnings.append("Sensitive personal information detected in input")
                logger.info(f"PII detected: {[p['type'] for p in pii_found]}")

        blocked = self._check_blocked_keywords(sanitized)
        if blocked:
            result.blocked = True
            result.valid = False
            result.reason = "Input contains blocked content"
            return result

        suspicious = self._check_suspicious(sanitized)
        if suspicious:
            warnings.extend(suspicious)

        result.warnings = warnings
        return result

    def _sanitize(self, text: str) -> str:
        """Sanitize input text."""
        text = text.replace("\x00", "")
        text = " ".join(text.split())
        text = "".join(
            char for char in text
            if char == "\n" or not (0 <= ord(char) < 32)
        )
        text = text.replace("<", "&lt;").replace(">", "&gt;")
        return text.strip()

    def _detect_language(self, text: str) -> str:
        """Detect primary language of text (defaults to English)."""
        # Placeholder for multi-language support (e.g., Spanish for US real estate)
        spanish_markers = ["¿", "¡", " el ", " la ", " casa ", " cuánto "]
        if any(marker in text.lower() for marker in spanish_markers):
            return "es"
        return "en"

    def _check_injection(self, text: str) -> Optional[str]:
        """Check for prompt injection patterns."""
        for pattern in INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                return f"injection pattern: {match.group()}"
        return None

    def _check_fair_housing(self, text: str) -> Optional[str]:
        """Check for Fair Housing Act steering/discrimination requests."""
        for pattern in FAIR_HOUSING_PROTECTED_CLASS_PATTERNS:
            match = pattern.search(text)
            if match:
                return f"protected-class filtering request: {match.group()}"
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
        return any(keyword in text_lower for keyword in BLOCKED_KEYWORDS)

    def _check_suspicious(self, text: str) -> List[str]:
        """Check for suspicious patterns (warnings only)."""
        warnings = []
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(text):
                warnings.append("Suspicious pattern detected in input")
                break
        return warnings


class BedrockGuardrailValidator:
    """
    AWS Bedrock Guardrails integration for input validation.
    """

    def __init__(self, guardrail_id: str, guardrail_version: str = "DRAFT"):
        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("bedrock-runtime")
        return self._client

    async def validate(self, text: str) -> ValidationResult:
        """Validate input using Bedrock Guardrails."""
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

            reason = None
            if blocked:
                for assessment in response.get("assessments", []):
                    for policy in assessment.get("topicPolicy", {}).get("topics", []):
                        if policy.get("action") == "BLOCKED":
                            reason = f"Blocked topic: {policy.get('name', 'unknown')}"
                            break
                    for filter_result in assessment.get("contentPolicy", {}).get("filters", []):
                        if filter_result.get("action") == "BLOCKED":
                            reason = f"Inappropriate content: {filter_result.get('type', 'unknown')}"
                            break

            return ValidationResult(
                valid=not blocked,
                blocked=blocked,
                reason=reason,
                confidence=response.get("guardrailCoverage", {}).get("textCharacters", {}).get("guarded", 0) / 100
            )

        except Exception as e:
            logger.error(f"Bedrock guardrail validation error: {e}")
            return ValidationResult(
                valid=True,
                warnings=[f"Guardrail check unavailable: {str(e)}"]
            )


def create_input_validator(
    bedrock_guardrail_id: Optional[str] = None,
    max_length: int = 2000,
    enable_fair_housing_guard: bool = True,
) -> InputValidator:
    """Factory function to create input validator."""
    return InputValidator(
        max_length=max_length,
        bedrock_guardrail_id=bedrock_guardrail_id,
        enable_fair_housing_guard=enable_fair_housing_guard,
    )
