"""
Output Validation and Guardrails for USA Property Finder Assistant.

Provides checks for model outputs:
- PII leakage prevention
- Fair Housing Act compliance (blocks discriminatory language in responses)
- Required disclaimers (AVM estimates, mortgage estimates, not-legal/tax-advice)
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
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
}

# =============================================================================
# Disclaimer Definitions
# =============================================================================

DISCLAIMERS: Dict[str, str] = {
    "avm_estimate": (
        "\U0001F4CB Note: This is an automated valuation model (AVM) estimate, not "
        "a licensed appraisal. Actual market value may differ. Consult a licensed "
        "appraiser or real estate agent for a formal valuation."
    ),
    "mortgage_calculator": (
        "\U0001F4CB Note: This is an estimate only. Actual rate, payment, taxes, "
        "insurance, and PMI depend on your lender, credit profile, and loan program. "
        "Consult a licensed mortgage lender for an accurate quote."
    ),
    "affordability": (
        "\U0001F4CB Note: This affordability estimate is for planning purposes only "
        "and is not a pre-approval or commitment to lend. Speak with a licensed "
        "lender to get pre-qualified."
    ),
    "market_forecast": (
        "\U0001F4CA Note: Market forecasts are based on historical trends and are "
        "not guarantees of future performance."
    ),
    "legal_tax": (
        "⚠️ This information is general in nature and is not legal or tax "
        "advice. Consult a licensed attorney or tax professional for your specific "
        "situation."
    ),
    "fair_housing": (
        "This assistant provides information equally to all users in compliance "
        "with the federal Fair Housing Act and does not filter listings or "
        "neighborhoods based on race, color, religion, sex, disability, familial "
        "status, or national origin."
    ),
}

# Intent to disclaimer mapping
INTENT_DISCLAIMERS: Dict[str, str] = {
    "valuation.estimate": "avm_estimate",
    "valuation.comps": "avm_estimate",
    "mortgage.calculate": "mortgage_calculator",
    "mortgage.affordability": "affordability",
    "market.forecast": "market_forecast",
    "market.trends": "market_forecast",
}

# =============================================================================
# Blocked Output Patterns
# =============================================================================

BLOCKED_OUTPUT_PATTERNS: List[tuple] = [
    (
        re.compile(r"(this|that)\s+(neighborhood|area)\s+is\s+(mostly|primarily)\s+(white|black|asian|hispanic)", re.I),
        "I can't characterize neighborhoods by racial or ethnic composition — that "
        "would violate Fair Housing Act steering prohibitions. I can share objective "
        "data like school ratings, crime statistics, and walkability instead."
    ),
    (
        re.compile(r"(recommend|suggest|better)\s+for\s+(families\s+with\s+kids|singles|christians|muslims|jews)", re.I),
        "I can't recommend properties or neighborhoods based on family status or "
        "religion — that would violate the Fair Housing Act."
    ),
    (
        re.compile(r"(guaranteed|certain)\s+(to\s+)?(appreciate|increase\s+in\s+value)", re.I),
        "I can't guarantee future property value changes — real estate markets are "
        "inherently uncertain."
    ),
    (
        re.compile(r"(legal|lawsuit|sue|court)\s+advice", re.I),
        "I can't provide legal advice. Please consult a licensed real estate attorney."
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

        if not content or not content.strip():
            result.valid = False
            result.blocked = True
            result.reason = "Empty response from model"
            return result

        if self.enable_content_check:
            blocked_result = self._check_blocked_content(content)
            if blocked_result:
                result.blocked = True
                result.valid = False
                result.reason = blocked_result
                return result

        if self.enable_pii_masking:
            masked_content, pii_found = self._mask_pii(content)
            if pii_found:
                modified_content = masked_content
                result.modified = True
                result.pii_detected = pii_found
                warnings.append("PII detected and masked in response")
                logger.info(f"PII masked in output: {[p['type'] for p in pii_found]}")

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
        for pattern, replacement in BLOCKED_OUTPUT_PATTERNS:
            if pattern.search(content):
                return replacement
        return None

    def _mask_pii(self, content: str) -> tuple:
        """Mask PII in content."""
        masked = content
        pii_found = []

        for pii_type, pattern in OUTPUT_PII_PATTERNS.items():
            matches = list(pattern.finditer(masked))
            for match in matches:
                pii_found.append({
                    "type": pii_type,
                    "position": match.start(),
                    "masked": True
                })
            masked = pattern.sub("[redacted]", masked)

        return masked, pii_found


class ResponseQualityChecker:
    """
    Quality checks for model responses.
    """

    def __init__(self, min_length: int = 5, max_length: int = 3000):
        self.min_length = min_length
        self.max_length = max_length

    def check(self, content: str) -> Dict[str, Any]:
        """Check response quality."""
        quality = {"passed": True, "issues": [], "metrics": {}}

        length = len(content)
        quality["metrics"]["length"] = length

        if length < self.min_length:
            quality["passed"] = False
            quality["issues"].append(f"Response too short ({length} chars)")

        if length > self.max_length:
            quality["passed"] = False
            quality["issues"].append(f"Response too long ({length} chars)")

        words = content.split()
        if len(words) > 10:
            unique_ratio = len(set(words)) / len(words)
            quality["metrics"]["unique_word_ratio"] = unique_ratio
            if unique_ratio < 0.3:
                quality["issues"].append("Response contains excessive repetition")

        return quality


class FairHousingComplianceChecker:
    """
    Dedicated Fair Housing Act compliance check for outputs, run in addition
    to the general output validator for extra assurance on discriminatory
    steering language.
    """

    STEERING_PATTERNS: List[Pattern] = [
        re.compile(r"(safer|better)\b.{0,30}\bfor\s+(white|families\s+like\s+yours)", re.I),
        re.compile(r"(avoid|stay\s+away\s+from)\s+.{0,30}(neighborhood|area).{0,30}(because|due\s+to)\s+.{0,30}(race|religion|ethnicity)", re.I),
    ]

    def check(self, content: str) -> Dict[str, Any]:
        """Check content for Fair Housing Act steering language."""
        violations = []
        for pattern in self.STEERING_PATTERNS:
            match = pattern.search(content)
            if match:
                violations.append(match.group())

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
        }


def create_output_validator(
    bedrock_guardrail_id: Optional[str] = None
) -> OutputValidator:
    """Factory function to create output validator."""
    return OutputValidator(bedrock_guardrail_id=bedrock_guardrail_id)
