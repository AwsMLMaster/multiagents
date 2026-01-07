"""
User Profile and Preferences System for Digital Bank Chatbot.

Manages:
- User characteristics (age, account type, personality)
- User preferences (insights, notifications, communication style)
- Segment classification
- Profile persistence
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class AccountType(str, Enum):
    """Types of bank accounts."""
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    BUSINESS = "business"
    STUDENT = "student"
    SENIOR = "senior"


class CommunicationStyle(str, Enum):
    """Preferred communication style."""
    FORMAL = "formal"
    FRIENDLY = "friendly"
    CONCISE = "concise"
    DETAILED = "detailed"


class PersonalityType(str, Enum):
    """User personality classification."""
    ANALYTICAL = "analytical"  # Wants details and data
    DRIVER = "driver"  # Wants quick results
    AMIABLE = "amiable"  # Values relationships
    EXPRESSIVE = "expressive"  # Values recognition


class TechSavvyLevel(str, Enum):
    """Technology comfort level."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class RiskTolerance(str, Enum):
    """Financial risk tolerance."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


# =============================================================================
# Preference Categories
# =============================================================================

@dataclass
class InsightPreferences:
    """User preferences for receiving insights."""
    # Spending insights
    spending_alerts: bool = True
    spending_summary_weekly: bool = True
    spending_summary_monthly: bool = True
    category_breakdown: bool = True
    unusual_spending_alert: bool = True

    # Savings insights
    savings_tips: bool = True
    savings_goals_reminders: bool = True

    # Account insights
    balance_alerts: bool = True
    low_balance_threshold: float = 500.0
    high_balance_notification: bool = False
    high_balance_threshold: float = 50000.0

    # Loan insights
    loan_payment_reminders: bool = True
    loan_early_payoff_tips: bool = True

    # Investment insights
    investment_updates: bool = False
    market_alerts: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "insights.spending_alerts": self.spending_alerts,
            "insights.spending_summary_weekly": self.spending_summary_weekly,
            "insights.spending_summary_monthly": self.spending_summary_monthly,
            "insights.category_breakdown": self.category_breakdown,
            "insights.unusual_spending_alert": self.unusual_spending_alert,
            "insights.savings_tips": self.savings_tips,
            "insights.savings_goals_reminders": self.savings_goals_reminders,
            "insights.balance_alerts": self.balance_alerts,
            "insights.low_balance_threshold": self.low_balance_threshold,
            "insights.loan_payment_reminders": self.loan_payment_reminders,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InsightPreferences":
        """Create from dictionary."""
        return cls(
            spending_alerts=data.get("insights.spending_alerts", True),
            spending_summary_weekly=data.get("insights.spending_summary_weekly", True),
            spending_summary_monthly=data.get("insights.spending_summary_monthly", True),
            category_breakdown=data.get("insights.category_breakdown", True),
            unusual_spending_alert=data.get("insights.unusual_spending_alert", True),
            savings_tips=data.get("insights.savings_tips", True),
            savings_goals_reminders=data.get("insights.savings_goals_reminders", True),
            balance_alerts=data.get("insights.balance_alerts", True),
            low_balance_threshold=data.get("insights.low_balance_threshold", 500.0),
            loan_payment_reminders=data.get("insights.loan_payment_reminders", True),
        )


@dataclass
class NotificationPreferences:
    """User notification preferences."""
    # Channels
    push_enabled: bool = True
    email_enabled: bool = True
    sms_enabled: bool = False

    # Types
    transaction_alerts: bool = True
    transaction_threshold: float = 100.0  # Alert above this amount
    security_alerts: bool = True
    promotional: bool = False
    service_updates: bool = True

    # Timing
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "notifications.push_enabled": self.push_enabled,
            "notifications.email_enabled": self.email_enabled,
            "notifications.sms_enabled": self.sms_enabled,
            "notifications.transaction_alerts": self.transaction_alerts,
            "notifications.transaction_threshold": self.transaction_threshold,
            "notifications.security_alerts": self.security_alerts,
            "notifications.promotional": self.promotional,
        }


@dataclass
class ChatbotPreferences:
    """User preferences for chatbot interaction."""
    # Communication
    preferred_language: str = "he"
    communication_style: CommunicationStyle = CommunicationStyle.FRIENDLY
    response_verbosity: str = "normal"  # brief, normal, detailed

    # Features
    show_upsell_offers: bool = True
    show_insights_in_chat: bool = True
    show_tips: bool = True
    show_confirmations: bool = True

    # Quick actions
    favorite_actions: List[str] = field(default_factory=list)
    pinned_accounts: List[str] = field(default_factory=list)

    # Accessibility
    large_text: bool = False
    high_contrast: bool = False
    screen_reader_mode: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chatbot.preferred_language": self.preferred_language,
            "chatbot.communication_style": self.communication_style.value,
            "chatbot.response_verbosity": self.response_verbosity,
            "chatbot.show_upsell_offers": self.show_upsell_offers,
            "chatbot.show_insights_in_chat": self.show_insights_in_chat,
            "chatbot.show_tips": self.show_tips,
            "chatbot.show_confirmations": self.show_confirmations,
            "chatbot.favorite_actions": self.favorite_actions,
        }


# =============================================================================
# User Characteristics
# =============================================================================

@dataclass
class UserCharacteristics:
    """
    User characteristics used for segmentation and personalization.
    """
    # Demographics
    age: Optional[int] = None
    age_group: Optional[str] = None  # young_adult, adult, senior
    gender: Optional[str] = None
    location: Optional[str] = None

    # Account
    account_type: AccountType = AccountType.STANDARD
    customer_since: Optional[date] = None
    tenure_months: int = 0

    # Financial
    average_balance: float = 0.0
    monthly_income: Optional[float] = None
    monthly_spending: float = 0.0
    has_loan: bool = False
    has_mortgage: bool = False
    has_savings_account: bool = False
    has_investment_account: bool = False

    # Behavior
    personality_type: PersonalityType = PersonalityType.AMIABLE
    tech_savvy: TechSavvyLevel = TechSavvyLevel.INTERMEDIATE
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    app_usage_frequency: str = "regular"  # rare, occasional, regular, heavy
    preferred_channel: str = "app"  # app, web, phone, branch

    # Engagement
    nps_score: Optional[int] = None
    last_interaction: Optional[datetime] = None
    interaction_count_30d: int = 0
    complaint_history: int = 0
    churn_risk_score: float = 0.0

    def calculate_age_group(self) -> Optional[str]:
        """Calculate age group from age."""
        if self.age is None:
            return None
        if self.age < 26:
            return "young_adult"
        elif self.age < 46:
            return "adult"
        else:
            return "senior"

    def get_segments(self) -> List[str]:
        """Determine user segments based on characteristics."""
        segments = []

        # Age-based
        age_group = self.calculate_age_group()
        if age_group:
            segments.append(age_group)

        # Account type
        if self.account_type == AccountType.PREMIUM:
            segments.append("premium")
        elif self.account_type == AccountType.BUSINESS:
            segments.append("business")
        else:
            segments.append("standard")

        # Value-based
        if self.average_balance > 100000 or (self.monthly_income and self.monthly_income > 30000):
            segments.append("high_value")

        # Tenure
        if self.tenure_months < 6:
            segments.append("new_customer")

        # Risk
        if self.churn_risk_score > 0.7:
            segments.append("at_risk")

        # Tech
        if self.tech_savvy == TechSavvyLevel.ADVANCED:
            segments.append("tech_savvy")
        elif self.tech_savvy == TechSavvyLevel.BEGINNER:
            segments.append("traditional")

        return segments

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "age": self.age,
            "age_group": self.age_group or self.calculate_age_group(),
            "account_type": self.account_type.value,
            "tenure_months": self.tenure_months,
            "average_balance": self.average_balance,
            "personality_type": self.personality_type.value,
            "tech_savvy": self.tech_savvy.value,
            "risk_tolerance": self.risk_tolerance.value,
            "segments": self.get_segments(),
        }


# =============================================================================
# User Profile
# =============================================================================

@dataclass
class UserProfile:
    """
    Complete user profile including characteristics and preferences.
    """
    user_id: str
    customer_id: str

    # Core info
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    # Characteristics and preferences
    characteristics: UserCharacteristics = field(default_factory=UserCharacteristics)
    insight_preferences: InsightPreferences = field(default_factory=InsightPreferences)
    notification_preferences: NotificationPreferences = field(default_factory=NotificationPreferences)
    chatbot_preferences: ChatbotPreferences = field(default_factory=ChatbotPreferences)

    # Custom preferences (key-value)
    custom_preferences: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    profile_version: int = 1

    def get_preference(self, key: str, default: Any = None) -> Any:
        """
        Get a preference value by key.

        Supports dot notation: "insights.spending_alerts"
        """
        # Check custom preferences first
        if key in self.custom_preferences:
            return self.custom_preferences[key]

        # Check insight preferences
        insight_prefs = self.insight_preferences.to_dict()
        if key in insight_prefs:
            return insight_prefs[key]

        # Check notification preferences
        notif_prefs = self.notification_preferences.to_dict()
        if key in notif_prefs:
            return notif_prefs[key]

        # Check chatbot preferences
        chat_prefs = self.chatbot_preferences.to_dict()
        if key in chat_prefs:
            return chat_prefs[key]

        return default

    def set_preference(self, key: str, value: Any) -> None:
        """
        Set a preference value.
        """
        # Route to appropriate preference category
        if key.startswith("insights."):
            attr = key.replace("insights.", "")
            if hasattr(self.insight_preferences, attr):
                setattr(self.insight_preferences, attr, value)
            else:
                self.custom_preferences[key] = value
        elif key.startswith("notifications."):
            attr = key.replace("notifications.", "")
            if hasattr(self.notification_preferences, attr):
                setattr(self.notification_preferences, attr, value)
            else:
                self.custom_preferences[key] = value
        elif key.startswith("chatbot."):
            attr = key.replace("chatbot.", "")
            if hasattr(self.chatbot_preferences, attr):
                setattr(self.chatbot_preferences, attr, value)
            else:
                self.custom_preferences[key] = value
        else:
            self.custom_preferences[key] = value

        self.updated_at = datetime.utcnow()

    def get_all_preferences(self) -> Dict[str, Any]:
        """Get all preferences as flat dictionary."""
        prefs = {}
        prefs.update(self.insight_preferences.to_dict())
        prefs.update(self.notification_preferences.to_dict())
        prefs.update(self.chatbot_preferences.to_dict())
        prefs.update(self.custom_preferences)
        return prefs

    def get_segments(self) -> List[str]:
        """Get user segments."""
        return self.characteristics.get_segments()

    def to_context(self) -> Dict[str, Any]:
        """
        Convert profile to context dictionary for rule evaluation.
        """
        return {
            "user_id": self.user_id,
            "customer_id": self.customer_id,
            "first_name": self.first_name,
            "segments": self.get_segments(),
            **self.characteristics.to_dict(),
            "preferences": self.get_all_preferences(),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "user_id": self.user_id,
            "customer_id": self.customer_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "characteristics": self.characteristics.to_dict(),
            "insight_preferences": self.insight_preferences.to_dict(),
            "notification_preferences": self.notification_preferences.to_dict(),
            "chatbot_preferences": self.chatbot_preferences.to_dict(),
            "custom_preferences": self.custom_preferences,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "profile_version": self.profile_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """Deserialize from dictionary."""
        profile = cls(
            user_id=data["user_id"],
            customer_id=data["customer_id"],
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            email=data.get("email"),
            phone=data.get("phone"),
        )

        # Load characteristics
        if "characteristics" in data:
            char_data = data["characteristics"]
            profile.characteristics = UserCharacteristics(
                age=char_data.get("age"),
                age_group=char_data.get("age_group"),
                account_type=AccountType(char_data.get("account_type", "standard")),
                tenure_months=char_data.get("tenure_months", 0),
                average_balance=char_data.get("average_balance", 0.0),
                personality_type=PersonalityType(char_data.get("personality_type", "amiable")),
                tech_savvy=TechSavvyLevel(char_data.get("tech_savvy", "intermediate")),
                risk_tolerance=RiskTolerance(char_data.get("risk_tolerance", "moderate")),
            )

        # Load preferences
        all_prefs = {
            **data.get("insight_preferences", {}),
            **data.get("notification_preferences", {}),
            **data.get("chatbot_preferences", {}),
        }
        profile.insight_preferences = InsightPreferences.from_dict(all_prefs)
        profile.custom_preferences = data.get("custom_preferences", {})

        return profile


# =============================================================================
# Profile Manager
# =============================================================================

class ProfileManager:
    """
    Manages user profiles with persistence.
    """

    def __init__(self, dynamodb_table: Optional[str] = None):
        """Initialize profile manager."""
        self.dynamodb_table = dynamodb_table or "user-profiles"
        self._client = None
        self._cache: Dict[str, UserProfile] = {}

    @property
    def dynamodb(self):
        """Lazy initialization of DynamoDB client."""
        if self._client is None:
            import boto3
            self._client = boto3.resource("dynamodb").Table(self.dynamodb_table)
        return self._client

    async def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Get user profile by ID.

        Args:
            user_id: User identifier.

        Returns:
            UserProfile or None if not found.
        """
        # Check cache first
        if user_id in self._cache:
            return self._cache[user_id]

        try:
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.dynamodb.get_item(Key={"user_id": user_id})
            )

            item = response.get("Item")
            if item:
                profile = UserProfile.from_dict(item)
                self._cache[user_id] = profile
                return profile

            return None

        except Exception as e:
            logger.error(f"Error getting profile for {user_id}: {e}")
            return None

    async def save_profile(self, profile: UserProfile) -> bool:
        """
        Save user profile.

        Args:
            profile: UserProfile to save.

        Returns:
            Success status.
        """
        try:
            import asyncio
            profile.updated_at = datetime.utcnow()
            data = profile.to_dict()

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.dynamodb.put_item(Item=data)
            )

            self._cache[profile.user_id] = profile
            return True

        except Exception as e:
            logger.error(f"Error saving profile for {profile.user_id}: {e}")
            return False

    async def update_preference(
        self,
        user_id: str,
        key: str,
        value: Any
    ) -> bool:
        """
        Update a single preference.

        Args:
            user_id: User identifier.
            key: Preference key.
            value: New value.

        Returns:
            Success status.
        """
        profile = await self.get_profile(user_id)
        if not profile:
            return False

        profile.set_preference(key, value)
        return await self.save_profile(profile)

    async def update_preferences_bulk(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """
        Update multiple preferences at once.

        Args:
            user_id: User identifier.
            preferences: Dictionary of preference key-values.

        Returns:
            Success status.
        """
        profile = await self.get_profile(user_id)
        if not profile:
            return False

        for key, value in preferences.items():
            profile.set_preference(key, value)

        return await self.save_profile(profile)

    async def get_or_create_profile(
        self,
        user_id: str,
        customer_id: str,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> UserProfile:
        """
        Get existing profile or create new one.

        Args:
            user_id: User identifier.
            customer_id: Customer identifier.
            initial_data: Optional initial data for new profile.

        Returns:
            UserProfile (existing or newly created).
        """
        profile = await self.get_profile(user_id)
        if profile:
            return profile

        # Create new profile
        profile = UserProfile(
            user_id=user_id,
            customer_id=customer_id,
        )

        if initial_data:
            for key, value in initial_data.items():
                profile.set_preference(key, value)

        await self.save_profile(profile)
        return profile

    def clear_cache(self, user_id: Optional[str] = None):
        """Clear profile cache."""
        if user_id:
            self._cache.pop(user_id, None)
        else:
            self._cache.clear()


# Singleton instance
_profile_manager: Optional[ProfileManager] = None


def get_profile_manager() -> ProfileManager:
    """Get singleton profile manager."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager
