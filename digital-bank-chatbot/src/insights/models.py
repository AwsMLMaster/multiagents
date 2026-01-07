"""
Financial Insights Data Models

Defines structures for financial insights, patterns, and recommendations.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


class InsightCategory(Enum):
    """Categories of financial insights."""
    SPENDING = "spending"           # Spending patterns and anomalies
    INCOME = "income"               # Income patterns
    SAVINGS = "savings"             # Savings opportunities
    TRANSFERS = "transfers"         # New or unusual transfers
    FEES = "fees"                   # Bank fees and charges
    SUBSCRIPTIONS = "subscriptions" # Recurring subscriptions
    BILLS = "bills"                 # Bill payment patterns
    CASH_FLOW = "cash_flow"         # Overall cash flow health
    SECURITY = "security"           # Security-related insights
    OPPORTUNITIES = "opportunities" # Financial opportunities


class InsightSeverity(Enum):
    """Severity/importance level of insights."""
    INFO = "info"           # Informational, nice to know
    SUGGESTION = "suggestion"  # Helpful suggestion
    IMPORTANT = "important"    # Should pay attention
    URGENT = "urgent"          # Requires immediate attention
    ALERT = "alert"            # Security or critical alert


class InsightType(Enum):
    """Specific types of insights."""
    # Spending insights
    UNUSUAL_SPENDING = "unusual_spending"
    SPENDING_SPIKE = "spending_spike"
    CATEGORY_OVERSPEND = "category_overspend"
    FIRST_TIME_MERCHANT = "first_time_merchant"
    LARGE_PURCHASE = "large_purchase"

    # Transfer insights
    NEW_PAYEE = "new_payee"
    LARGE_TRANSFER = "large_transfer"
    INTERNATIONAL_TRANSFER = "international_transfer"
    RECURRING_TRANSFER_CHANGE = "recurring_transfer_change"

    # Income insights
    SALARY_RECEIVED = "salary_received"
    SALARY_CHANGE = "salary_change"
    NEW_INCOME_SOURCE = "new_income_source"
    INCOME_DELAY = "income_delay"

    # Savings insights
    IDLE_BALANCE = "idle_balance"
    SAVINGS_GOAL_PROGRESS = "savings_goal_progress"
    SAVINGS_OPPORTUNITY = "savings_opportunity"
    LOW_BALANCE_PREDICTION = "low_balance_prediction"

    # Subscription insights
    NEW_SUBSCRIPTION = "new_subscription"
    SUBSCRIPTION_INCREASE = "subscription_increase"
    UNUSED_SUBSCRIPTION = "unused_subscription"
    SUBSCRIPTION_RENEWAL = "subscription_renewal"

    # Fee insights
    AVOIDABLE_FEE = "avoidable_fee"
    FEE_PATTERN = "fee_pattern"
    OVERDRAFT_RISK = "overdraft_risk"

    # Cash flow insights
    POSITIVE_TREND = "positive_trend"
    NEGATIVE_TREND = "negative_trend"
    END_OF_MONTH_RISK = "end_of_month_risk"
    CASH_FLOW_FORECAST = "cash_flow_forecast"

    # Security insights
    DUPLICATE_CHARGE = "duplicate_charge"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    UNUSUAL_LOCATION = "unusual_location"


class PatternType(Enum):
    """Types of patterns detected in transactions."""
    RECURRING = "recurring"           # Regular recurring transactions
    SEASONAL = "seasonal"             # Seasonal patterns
    TRENDING_UP = "trending_up"       # Increasing over time
    TRENDING_DOWN = "trending_down"   # Decreasing over time
    ANOMALY = "anomaly"               # Outlier/anomaly
    CORRELATION = "correlation"       # Correlated events
    CLUSTER = "cluster"               # Grouped transactions


@dataclass
class DetectedPattern:
    """A detected pattern in transaction data."""
    pattern_id: str
    pattern_type: PatternType
    description: str
    confidence: float  # 0.0 to 1.0

    # Pattern details
    affected_transactions: List[str] = field(default_factory=list)
    merchant_or_category: Optional[str] = None
    average_amount: Optional[Decimal] = None
    frequency_days: Optional[int] = None

    # Time context
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    next_expected: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InsightRecommendation:
    """Actionable recommendation associated with an insight."""
    recommendation_id: str
    title_he: str
    title_en: str
    description_he: str
    description_en: str

    # Action
    action_type: str  # e.g., "transfer_to_savings", "review_subscription", "set_alert"
    action_params: Dict[str, Any] = field(default_factory=dict)

    # Related offering (if applicable)
    related_offering_id: Optional[str] = None

    # Impact
    estimated_benefit: Optional[str] = None  # e.g., "Save ₪1,200/year"
    estimated_benefit_amount: Optional[Decimal] = None

    # Priority
    priority: int = 0  # Higher = more important

    def get_localized(self, language: str = "he") -> Dict[str, str]:
        """Get recommendation in specified language."""
        if language == "he":
            return {
                "title": self.title_he,
                "description": self.description_he,
            }
        return {
            "title": self.title_en,
            "description": self.description_en,
        }


@dataclass
class Insight:
    """A financial insight for the customer."""
    insight_id: str
    insight_type: InsightType
    category: InsightCategory
    severity: InsightSeverity

    # Content
    title_he: str
    title_en: str
    summary_he: str
    summary_en: str
    details_he: str = ""
    details_en: str = ""

    # Data
    amount: Optional[Decimal] = None
    comparison_amount: Optional[Decimal] = None  # For comparisons (e.g., vs last month)
    percentage_change: Optional[float] = None

    # Context
    merchant_name: Optional[str] = None
    category_name: Optional[str] = None
    account_id: Optional[str] = None
    transaction_ids: List[str] = field(default_factory=list)

    # Pattern
    detected_pattern: Optional[DetectedPattern] = None

    # Recommendations
    recommendations: List[InsightRecommendation] = field(default_factory=list)

    # Status
    is_new: bool = True
    is_read: bool = False
    is_dismissed: bool = False
    is_actioned: bool = False

    # Timestamps
    generated_at: datetime = field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None
    read_at: Optional[datetime] = None
    actioned_at: Optional[datetime] = None

    # Confidence and relevance
    confidence: float = 1.0
    relevance_score: float = 1.0

    # Personalization
    personalization_context: Dict[str, Any] = field(default_factory=dict)

    def get_localized(self, language: str = "he") -> Dict[str, Any]:
        """Get insight in specified language."""
        if language == "he":
            return {
                "title": self.title_he,
                "summary": self.summary_he,
                "details": self.details_he,
            }
        return {
            "title": self.title_en,
            "summary": self.summary_en,
            "details": self.details_en,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "insight_id": self.insight_id,
            "insight_type": self.insight_type.value,
            "category": self.category.value,
            "severity": self.severity.value,
            "title_he": self.title_he,
            "title_en": self.title_en,
            "summary_he": self.summary_he,
            "summary_en": self.summary_en,
            "details_he": self.details_he,
            "details_en": self.details_en,
            "amount": str(self.amount) if self.amount else None,
            "comparison_amount": str(self.comparison_amount) if self.comparison_amount else None,
            "percentage_change": self.percentage_change,
            "merchant_name": self.merchant_name,
            "category_name": self.category_name,
            "account_id": self.account_id,
            "transaction_ids": self.transaction_ids,
            "recommendations": [
                {
                    "recommendation_id": r.recommendation_id,
                    "title_he": r.title_he,
                    "title_en": r.title_en,
                    "action_type": r.action_type,
                    "action_params": r.action_params,
                    "related_offering_id": r.related_offering_id,
                    "estimated_benefit": r.estimated_benefit,
                }
                for r in self.recommendations
            ],
            "is_new": self.is_new,
            "is_read": self.is_read,
            "is_dismissed": self.is_dismissed,
            "confidence": self.confidence,
            "relevance_score": self.relevance_score,
            "generated_at": self.generated_at.isoformat(),
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
        }


@dataclass
class InsightConfig:
    """Configuration for insight generation."""
    # Thresholds
    unusual_spending_threshold: float = 1.5  # 50% above average
    large_purchase_threshold: Decimal = Decimal("1000")
    large_transfer_threshold: Decimal = Decimal("5000")
    idle_balance_threshold: Decimal = Decimal("5000")
    idle_balance_days: int = 30
    low_balance_threshold: Decimal = Decimal("500")

    # Feature flags
    enable_spending_insights: bool = True
    enable_transfer_insights: bool = True
    enable_income_insights: bool = True
    enable_savings_insights: bool = True
    enable_subscription_insights: bool = True
    enable_fee_insights: bool = True
    enable_cash_flow_insights: bool = True
    enable_security_insights: bool = True

    # Delivery preferences
    max_insights_per_session: int = 3
    min_confidence_threshold: float = 0.7
    insight_cooldown_hours: int = 24  # Don't repeat same insight type within this window

    # Categories enabled (can be customized per user)
    enabled_categories: List[InsightCategory] = field(
        default_factory=lambda: list(InsightCategory)
    )

    # Severity filter
    min_severity: InsightSeverity = InsightSeverity.SUGGESTION


@dataclass
class CustomerInsightProfile:
    """Customer's insight preferences and history."""
    customer_id: str

    # Preferences
    config: InsightConfig = field(default_factory=InsightConfig)

    # History
    total_insights_generated: int = 0
    total_insights_read: int = 0
    total_insights_actioned: int = 0
    total_recommendations_followed: int = 0

    # Dismissed insight types (don't show again)
    dismissed_insight_types: List[str] = field(default_factory=list)

    # Recent insights (for deduplication)
    recent_insight_types: Dict[str, datetime] = field(default_factory=dict)

    # Engagement metrics
    avg_time_to_read: Optional[float] = None
    preferred_categories: List[InsightCategory] = field(default_factory=list)

    # Last activity
    last_insight_shown_at: Optional[datetime] = None
    last_recommendation_followed_at: Optional[datetime] = None
