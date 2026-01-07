"""
Offerings Bank Data Models

Defines the structure for bank product offerings, eligibility criteria,
and customer matching.
"""

from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from decimal import Decimal


class OfferingCategory(Enum):
    """Main categories of bank offerings."""
    SAVINGS = "savings"
    DEPOSITS = "deposits"
    LOANS = "loans"
    CREDIT_CARDS = "credit_cards"
    INVESTMENTS = "investments"
    INSURANCE = "insurance"
    PACKAGES = "packages"  # Bundle offerings


class OfferingType(Enum):
    """Specific offering types within categories."""
    # Savings
    REGULAR_SAVINGS = "regular_savings"
    HIGH_YIELD_SAVINGS = "high_yield_savings"
    GOAL_SAVINGS = "goal_savings"
    KIDS_SAVINGS = "kids_savings"

    # Deposits
    FIXED_DEPOSIT = "fixed_deposit"
    RECURRING_DEPOSIT = "recurring_deposit"
    FLEXI_DEPOSIT = "flexi_deposit"

    # Loans
    PERSONAL_LOAN = "personal_loan"
    HOME_LOAN = "home_loan"
    CAR_LOAN = "car_loan"
    EDUCATION_LOAN = "education_loan"
    OVERDRAFT = "overdraft"

    # Credit Cards
    BASIC_CARD = "basic_card"
    REWARDS_CARD = "rewards_card"
    PREMIUM_CARD = "premium_card"
    CASHBACK_CARD = "cashback_card"

    # Investments
    MUTUAL_FUND = "mutual_fund"
    PENSION_FUND = "pension_fund"
    STRUCTURED_PRODUCT = "structured_product"

    # Insurance
    LIFE_INSURANCE = "life_insurance"
    PROPERTY_INSURANCE = "property_insurance"
    TRAVEL_INSURANCE = "travel_insurance"


class ConsentStatus(Enum):
    """Status of customer consent for an offering."""
    PENDING = "pending"
    INTERESTED = "interested"  # Customer showed interest
    CONSENTED = "consented"  # Customer agreed to proceed
    DECLINED = "declined"
    EXPIRED = "expired"
    FULFILLED = "fulfilled"  # Offering completed


class FulfillmentMode(Enum):
    """How the offering is fulfilled after consent."""
    EMAIL_TO_BANKER = "email_to_banker"  # Phase 1: Email notification
    DIRECT_INTENT = "direct_intent"  # Phase 2: Execute via intent
    HYBRID = "hybrid"  # Both notification and partial automation
    EXTERNAL_REDIRECT = "external_redirect"  # Redirect to external system


@dataclass
class EligibilityCriteria:
    """Criteria for determining customer eligibility."""
    # Age requirements
    min_age: Optional[int] = None
    max_age: Optional[int] = None

    # Account requirements
    min_account_age_months: Optional[int] = None
    required_account_types: List[str] = field(default_factory=list)
    excluded_account_types: List[str] = field(default_factory=list)

    # Financial requirements
    min_balance: Optional[Decimal] = None
    max_balance: Optional[Decimal] = None
    min_monthly_income: Optional[Decimal] = None
    min_credit_score: Optional[int] = None
    max_debt_ratio: Optional[float] = None

    # Behavioral requirements
    min_monthly_transactions: Optional[int] = None
    required_product_holdings: List[str] = field(default_factory=list)
    excluded_product_holdings: List[str] = field(default_factory=list)

    # Segment targeting
    target_segments: List[str] = field(default_factory=list)  # e.g., ["premium", "young_professional"]
    excluded_segments: List[str] = field(default_factory=list)

    # Custom conditions (evaluated dynamically)
    custom_conditions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "min_age": self.min_age,
            "max_age": self.max_age,
            "min_account_age_months": self.min_account_age_months,
            "required_account_types": self.required_account_types,
            "excluded_account_types": self.excluded_account_types,
            "min_balance": str(self.min_balance) if self.min_balance else None,
            "max_balance": str(self.max_balance) if self.max_balance else None,
            "min_monthly_income": str(self.min_monthly_income) if self.min_monthly_income else None,
            "min_credit_score": self.min_credit_score,
            "max_debt_ratio": self.max_debt_ratio,
            "min_monthly_transactions": self.min_monthly_transactions,
            "required_product_holdings": self.required_product_holdings,
            "excluded_product_holdings": self.excluded_product_holdings,
            "target_segments": self.target_segments,
            "excluded_segments": self.excluded_segments,
            "custom_conditions": self.custom_conditions,
        }


@dataclass
class OfferingTerms:
    """Financial terms of an offering."""
    # Interest/Returns
    interest_rate: Optional[Decimal] = None  # Annual rate
    interest_rate_type: str = "fixed"  # fixed, variable, tiered
    bonus_rate: Optional[Decimal] = None  # Promotional bonus
    bonus_rate_duration_months: Optional[int] = None

    # Duration
    min_term_months: Optional[int] = None
    max_term_months: Optional[int] = None
    lock_in_period_months: Optional[int] = None

    # Amounts
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    recommended_amount: Optional[Decimal] = None

    # Fees
    setup_fee: Optional[Decimal] = None
    monthly_fee: Optional[Decimal] = None
    annual_fee: Optional[Decimal] = None
    early_withdrawal_penalty_percent: Optional[Decimal] = None

    # Credit specific
    credit_limit: Optional[Decimal] = None
    apr: Optional[Decimal] = None

    # Rewards
    reward_points_rate: Optional[float] = None  # Points per currency unit
    cashback_rate: Optional[Decimal] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        result = {}
        for key, value in vars(self).items():
            if value is not None:
                if isinstance(value, Decimal):
                    result[key] = str(value)
                else:
                    result[key] = value
        return result


@dataclass
class OfferingPresentation:
    """How to present the offering to customers."""
    # Display text (Hebrew)
    title_he: str = ""
    subtitle_he: str = ""
    description_he: str = ""
    benefits_he: List[str] = field(default_factory=list)
    call_to_action_he: str = ""

    # Display text (English)
    title_en: str = ""
    subtitle_en: str = ""
    description_en: str = ""
    benefits_en: List[str] = field(default_factory=list)
    call_to_action_en: str = ""

    # Visual
    icon: str = ""
    color_scheme: str = "default"
    priority_badge: Optional[str] = None  # e.g., "hot", "limited", "recommended"

    # Personalization templates
    personalized_message_template: str = ""  # Uses {variable} placeholders

    def get_localized(self, language: str = "he") -> Dict[str, Any]:
        """Get presentation in specified language."""
        if language == "he":
            return {
                "title": self.title_he,
                "subtitle": self.subtitle_he,
                "description": self.description_he,
                "benefits": self.benefits_he,
                "call_to_action": self.call_to_action_he,
                "icon": self.icon,
                "color_scheme": self.color_scheme,
                "priority_badge": self.priority_badge,
            }
        else:
            return {
                "title": self.title_en,
                "subtitle": self.subtitle_en,
                "description": self.description_en,
                "benefits": self.benefits_en,
                "call_to_action": self.call_to_action_en,
                "icon": self.icon,
                "color_scheme": self.color_scheme,
                "priority_badge": self.priority_badge,
            }


@dataclass
class Offering:
    """
    A bank product offering.

    Example: "High-Yield Savings Account with 3% interest"
    """
    offering_id: str
    name: str
    category: OfferingCategory
    offering_type: OfferingType

    # Configuration
    eligibility: EligibilityCriteria = field(default_factory=EligibilityCriteria)
    terms: OfferingTerms = field(default_factory=OfferingTerms)
    presentation: OfferingPresentation = field(default_factory=OfferingPresentation)

    # Fulfillment
    fulfillment_mode: FulfillmentMode = FulfillmentMode.EMAIL_TO_BANKER
    fulfillment_intent_id: Optional[str] = None  # Intent to execute for direct fulfillment
    banker_action_required: bool = True

    # Targeting
    priority: int = 0  # Higher = more important
    is_promotional: bool = False
    promotion_start: Optional[datetime] = None
    promotion_end: Optional[datetime] = None

    # Triggers (when to suggest this offering)
    trigger_conditions: List[Dict[str, Any]] = field(default_factory=list)
    # e.g., {"type": "balance_threshold", "min_idle_balance": 10000}
    # e.g., {"type": "intent_completion", "intent": "check_balance"}
    # e.g., {"type": "time_based", "days_since_last_offer": 30}

    # Status
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Analytics
    total_impressions: int = 0
    total_consents: int = 0
    total_fulfillments: int = 0

    def is_promotion_active(self) -> bool:
        """Check if promotional period is active."""
        if not self.is_promotional:
            return True

        now = datetime.utcnow()
        if self.promotion_start and now < self.promotion_start:
            return False
        if self.promotion_end and now > self.promotion_end:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "offering_id": self.offering_id,
            "name": self.name,
            "category": self.category.value,
            "offering_type": self.offering_type.value,
            "eligibility": self.eligibility.to_dict(),
            "terms": self.terms.to_dict(),
            "presentation": {
                "title_he": self.presentation.title_he,
                "title_en": self.presentation.title_en,
                "subtitle_he": self.presentation.subtitle_he,
                "subtitle_en": self.presentation.subtitle_en,
                "description_he": self.presentation.description_he,
                "description_en": self.presentation.description_en,
                "benefits_he": self.presentation.benefits_he,
                "benefits_en": self.presentation.benefits_en,
                "call_to_action_he": self.presentation.call_to_action_he,
                "call_to_action_en": self.presentation.call_to_action_en,
                "icon": self.presentation.icon,
                "color_scheme": self.presentation.color_scheme,
                "priority_badge": self.presentation.priority_badge,
                "personalized_message_template": self.presentation.personalized_message_template,
            },
            "fulfillment_mode": self.fulfillment_mode.value,
            "fulfillment_intent_id": self.fulfillment_intent_id,
            "banker_action_required": self.banker_action_required,
            "priority": self.priority,
            "is_promotional": self.is_promotional,
            "promotion_start": self.promotion_start.isoformat() if self.promotion_start else None,
            "promotion_end": self.promotion_end.isoformat() if self.promotion_end else None,
            "trigger_conditions": self.trigger_conditions,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class CustomerMatch:
    """
    Result of matching a customer to an offering.
    """
    offering_id: str
    offering: Offering
    customer_id: str

    # Match quality
    match_score: float  # 0.0 to 1.0
    match_reasons: List[str] = field(default_factory=list)
    # e.g., ["high_idle_balance", "matches_segment", "no_existing_savings"]

    # Personalized data
    personalized_amount: Optional[Decimal] = None  # Suggested amount based on customer
    personalized_message: str = ""
    projected_benefit: Optional[str] = None  # e.g., "Earn ₪1,200/year in interest"

    # Context
    trigger_type: str = ""  # What triggered this match
    trigger_context: Dict[str, Any] = field(default_factory=dict)

    # Timing
    matched_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


@dataclass
class OfferingConsent:
    """
    Customer consent record for an offering.
    """
    consent_id: str
    offering_id: str
    customer_id: str
    match: CustomerMatch

    # Status tracking
    status: ConsentStatus = ConsentStatus.PENDING
    status_history: List[Dict[str, Any]] = field(default_factory=list)

    # Customer input
    agreed_amount: Optional[Decimal] = None
    agreed_term_months: Optional[int] = None
    customer_notes: Optional[str] = None

    # Fulfillment
    fulfillment_mode: FulfillmentMode = FulfillmentMode.EMAIL_TO_BANKER
    banker_email_sent: bool = False
    banker_email_sent_at: Optional[datetime] = None
    assigned_banker_id: Optional[str] = None
    assigned_banker_name: Optional[str] = None

    # Intent execution (Phase 2)
    intent_executed: bool = False
    intent_execution_id: Optional[str] = None
    intent_result: Optional[Dict[str, Any]] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    consented_at: Optional[datetime] = None
    fulfilled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Conversation context
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None

    def update_status(self, new_status: ConsentStatus, reason: str = "") -> None:
        """Update status with history tracking."""
        self.status_history.append({
            "from_status": self.status.value,
            "to_status": new_status.value,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.status = new_status

        if new_status == ConsentStatus.CONSENTED:
            self.consented_at = datetime.utcnow()
        elif new_status == ConsentStatus.FULFILLED:
            self.fulfilled_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "consent_id": self.consent_id,
            "offering_id": self.offering_id,
            "customer_id": self.customer_id,
            "status": self.status.value,
            "status_history": self.status_history,
            "agreed_amount": str(self.agreed_amount) if self.agreed_amount else None,
            "agreed_term_months": self.agreed_term_months,
            "customer_notes": self.customer_notes,
            "fulfillment_mode": self.fulfillment_mode.value,
            "banker_email_sent": self.banker_email_sent,
            "banker_email_sent_at": self.banker_email_sent_at.isoformat() if self.banker_email_sent_at else None,
            "assigned_banker_id": self.assigned_banker_id,
            "assigned_banker_name": self.assigned_banker_name,
            "intent_executed": self.intent_executed,
            "intent_execution_id": self.intent_execution_id,
            "intent_result": self.intent_result,
            "created_at": self.created_at.isoformat(),
            "consented_at": self.consented_at.isoformat() if self.consented_at else None,
            "fulfilled_at": self.fulfilled_at.isoformat() if self.fulfilled_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
        }
