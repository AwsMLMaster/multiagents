"""
User Self-Configuration API for Digital Bank Chatbot.

Provides endpoints for users to manage their preferences:
- Insight preferences
- Notification settings
- Chatbot behavior settings
- Privacy settings
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .user_profile import (
    UserProfile,
    ProfileManager,
    InsightPreferences,
    NotificationPreferences,
    ChatbotPreferences,
    CommunicationStyle,
    get_profile_manager,
)

logger = logging.getLogger(__name__)


# =============================================================================
# API Types
# =============================================================================

class PreferenceCategory(str, Enum):
    """Categories of preferences."""
    INSIGHTS = "insights"
    NOTIFICATIONS = "notifications"
    CHATBOT = "chatbot"
    PRIVACY = "privacy"
    ALL = "all"


@dataclass
class PreferenceOption:
    """A configurable preference option."""
    key: str
    name_he: str
    name_en: str
    description_he: str
    description_en: str
    category: PreferenceCategory
    value_type: str  # "boolean", "number", "string", "enum"
    default_value: Any
    current_value: Any = None
    options: Optional[List[Dict[str, str]]] = None  # For enum types
    min_value: Optional[float] = None  # For number types
    max_value: Optional[float] = None
    required: bool = False
    editable: bool = True


@dataclass
class PreferenceUpdate:
    """A preference update request."""
    key: str
    value: Any
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PreferencesResponse:
    """Response containing user preferences."""
    user_id: str
    categories: Dict[str, List[PreferenceOption]]
    last_updated: datetime


# =============================================================================
# Preference Definitions
# =============================================================================

# All available preference options
PREFERENCE_OPTIONS: List[PreferenceOption] = [
    # =========================================================================
    # Insight Preferences
    # =========================================================================
    PreferenceOption(
        key="insights.spending_alerts",
        name_he="התראות הוצאות",
        name_en="Spending Alerts",
        description_he="קבל התראות כשההוצאות שלך גבוהות מהרגיל",
        description_en="Receive alerts when your spending is above normal",
        category=PreferenceCategory.INSIGHTS,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="insights.spending_summary_weekly",
        name_he="סיכום שבועי",
        name_en="Weekly Summary",
        description_he="קבל סיכום הוצאות שבועי",
        description_en="Receive weekly spending summary",
        category=PreferenceCategory.INSIGHTS,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="insights.spending_summary_monthly",
        name_he="סיכום חודשי",
        name_en="Monthly Summary",
        description_he="קבל סיכום הוצאות חודשי",
        description_en="Receive monthly spending summary",
        category=PreferenceCategory.INSIGHTS,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="insights.category_breakdown",
        name_he="פירוט קטגוריות",
        name_en="Category Breakdown",
        description_he="הצג פירוט הוצאות לפי קטגוריה",
        description_en="Show spending breakdown by category",
        category=PreferenceCategory.INSIGHTS,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="insights.unusual_spending_alert",
        name_he="התראת הוצאה חריגה",
        name_en="Unusual Spending Alert",
        description_he="התראה על פעולות חריגות בחשבון",
        description_en="Alert on unusual account activity",
        category=PreferenceCategory.INSIGHTS,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="insights.savings_tips",
        name_he="טיפים לחיסכון",
        name_en="Savings Tips",
        description_he="קבל טיפים לחיסכון מבוססי התנהגות",
        description_en="Receive personalized savings tips",
        category=PreferenceCategory.INSIGHTS,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="insights.balance_alerts",
        name_he="התראות יתרה",
        name_en="Balance Alerts",
        description_he="התראות כשהיתרה נמוכה או גבוהה",
        description_en="Alerts when balance is low or high",
        category=PreferenceCategory.INSIGHTS,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="insights.low_balance_threshold",
        name_he="סף יתרה נמוכה",
        name_en="Low Balance Threshold",
        description_he="סכום מינימלי להתראה (בשקלים)",
        description_en="Minimum balance for alert (in ILS)",
        category=PreferenceCategory.INSIGHTS,
        value_type="number",
        default_value=500,
        min_value=0,
        max_value=10000,
    ),
    PreferenceOption(
        key="insights.loan_payment_reminders",
        name_he="תזכורות הלוואה",
        name_en="Loan Payment Reminders",
        description_he="תזכורות לפני תשלום הלוואה",
        description_en="Reminders before loan payments",
        category=PreferenceCategory.INSIGHTS,
        value_type="boolean",
        default_value=True,
    ),

    # =========================================================================
    # Notification Preferences
    # =========================================================================
    PreferenceOption(
        key="notifications.push_enabled",
        name_he="התראות פוש",
        name_en="Push Notifications",
        description_he="קבל התראות פוש לנייד",
        description_en="Receive push notifications",
        category=PreferenceCategory.NOTIFICATIONS,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="notifications.email_enabled",
        name_he="התראות אימייל",
        name_en="Email Notifications",
        description_he="קבל התראות באימייל",
        description_en="Receive email notifications",
        category=PreferenceCategory.NOTIFICATIONS,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="notifications.sms_enabled",
        name_he="התראות SMS",
        name_en="SMS Notifications",
        description_he="קבל התראות ב-SMS",
        description_en="Receive SMS notifications",
        category=PreferenceCategory.NOTIFICATIONS,
        value_type="boolean",
        default_value=False,
    ),
    PreferenceOption(
        key="notifications.transaction_alerts",
        name_he="התראות תנועות",
        name_en="Transaction Alerts",
        description_he="קבל התראות על תנועות בחשבון",
        description_en="Receive alerts on account transactions",
        category=PreferenceCategory.NOTIFICATIONS,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="notifications.transaction_threshold",
        name_he="סף התראת תנועה",
        name_en="Transaction Alert Threshold",
        description_he="סכום מינימלי להתראת תנועה (בשקלים)",
        description_en="Minimum amount for transaction alert (in ILS)",
        category=PreferenceCategory.NOTIFICATIONS,
        value_type="number",
        default_value=100,
        min_value=0,
        max_value=10000,
    ),
    PreferenceOption(
        key="notifications.security_alerts",
        name_he="התראות אבטחה",
        name_en="Security Alerts",
        description_he="התראות על פעילות חשודה",
        description_en="Alerts on suspicious activity",
        category=PreferenceCategory.NOTIFICATIONS,
        value_type="boolean",
        default_value=True,
        editable=False,  # Security alerts cannot be disabled
    ),
    PreferenceOption(
        key="notifications.promotional",
        name_he="הודעות שיווקיות",
        name_en="Promotional Messages",
        description_he="קבל הצעות ומבצעים",
        description_en="Receive offers and promotions",
        category=PreferenceCategory.NOTIFICATIONS,
        value_type="boolean",
        default_value=False,
    ),

    # =========================================================================
    # Chatbot Preferences
    # =========================================================================
    PreferenceOption(
        key="chatbot.preferred_language",
        name_he="שפה מועדפת",
        name_en="Preferred Language",
        description_he="השפה המועדפת לשיחה",
        description_en="Preferred conversation language",
        category=PreferenceCategory.CHATBOT,
        value_type="enum",
        default_value="he",
        options=[
            {"value": "he", "label_he": "עברית", "label_en": "Hebrew"},
            {"value": "en", "label_he": "אנגלית", "label_en": "English"},
        ],
    ),
    PreferenceOption(
        key="chatbot.communication_style",
        name_he="סגנון תקשורת",
        name_en="Communication Style",
        description_he="סגנון השיחה המועדף",
        description_en="Preferred conversation style",
        category=PreferenceCategory.CHATBOT,
        value_type="enum",
        default_value="friendly",
        options=[
            {"value": "formal", "label_he": "רשמי", "label_en": "Formal"},
            {"value": "friendly", "label_he": "ידידותי", "label_en": "Friendly"},
            {"value": "concise", "label_he": "תמציתי", "label_en": "Concise"},
            {"value": "detailed", "label_he": "מפורט", "label_en": "Detailed"},
        ],
    ),
    PreferenceOption(
        key="chatbot.show_upsell_offers",
        name_he="הצג הצעות",
        name_en="Show Offers",
        description_he="הצג הצעות למוצרים ושירותים",
        description_en="Show product and service offers",
        category=PreferenceCategory.CHATBOT,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="chatbot.show_insights_in_chat",
        name_he="הצג תובנות",
        name_en="Show Insights",
        description_he="הצג תובנות פיננסיות בשיחה",
        description_en="Show financial insights in chat",
        category=PreferenceCategory.CHATBOT,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="chatbot.show_tips",
        name_he="הצג טיפים",
        name_en="Show Tips",
        description_he="הצג טיפים והמלצות",
        description_en="Show tips and recommendations",
        category=PreferenceCategory.CHATBOT,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="chatbot.show_confirmations",
        name_he="אישורי פעולה",
        name_en="Action Confirmations",
        description_he="בקש אישור לפני פעולות",
        description_en="Request confirmation before actions",
        category=PreferenceCategory.CHATBOT,
        value_type="boolean",
        default_value=True,
    ),

    # =========================================================================
    # Privacy Preferences
    # =========================================================================
    PreferenceOption(
        key="privacy.save_conversation_history",
        name_he="שמור היסטוריית שיחות",
        name_en="Save Conversation History",
        description_he="שמור שיחות לשיפור השירות",
        description_en="Save conversations to improve service",
        category=PreferenceCategory.PRIVACY,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="privacy.personalized_recommendations",
        name_he="המלצות מותאמות",
        name_en="Personalized Recommendations",
        description_he="קבל המלצות מותאמות אישית",
        description_en="Receive personalized recommendations",
        category=PreferenceCategory.PRIVACY,
        value_type="boolean",
        default_value=True,
    ),
    PreferenceOption(
        key="privacy.analytics_participation",
        name_he="השתתפות בסטטיסטיקות",
        name_en="Analytics Participation",
        description_he="אפשר שימוש בנתונים לשיפור השירות",
        description_en="Allow data use for service improvement",
        category=PreferenceCategory.PRIVACY,
        value_type="boolean",
        default_value=True,
    ),
]


# =============================================================================
# Preferences API
# =============================================================================

class PreferencesAPI:
    """
    API for user self-configuration of preferences.
    """

    def __init__(self, profile_manager: Optional[ProfileManager] = None):
        """Initialize preferences API."""
        self.profile_manager = profile_manager or get_profile_manager()

    async def get_all_preferences(
        self,
        user_id: str,
        language: str = "he"
    ) -> PreferencesResponse:
        """
        Get all user preferences organized by category.

        Args:
            user_id: User identifier.
            language: Display language (he/en).

        Returns:
            PreferencesResponse with all preferences.
        """
        profile = await self.profile_manager.get_profile(user_id)

        categories: Dict[str, List[PreferenceOption]] = {}

        for option in PREFERENCE_OPTIONS:
            # Get current value
            if profile:
                current_value = profile.get_preference(option.key, option.default_value)
            else:
                current_value = option.default_value

            option_copy = PreferenceOption(
                key=option.key,
                name_he=option.name_he,
                name_en=option.name_en,
                description_he=option.description_he,
                description_en=option.description_en,
                category=option.category,
                value_type=option.value_type,
                default_value=option.default_value,
                current_value=current_value,
                options=option.options,
                min_value=option.min_value,
                max_value=option.max_value,
                required=option.required,
                editable=option.editable,
            )

            category_name = option.category.value
            if category_name not in categories:
                categories[category_name] = []
            categories[category_name].append(option_copy)

        return PreferencesResponse(
            user_id=user_id,
            categories=categories,
            last_updated=profile.updated_at if profile else datetime.utcnow(),
        )

    async def get_preferences_by_category(
        self,
        user_id: str,
        category: PreferenceCategory,
        language: str = "he"
    ) -> List[PreferenceOption]:
        """
        Get preferences for a specific category.

        Args:
            user_id: User identifier.
            category: Preference category.
            language: Display language.

        Returns:
            List of preference options.
        """
        response = await self.get_all_preferences(user_id, language)
        return response.categories.get(category.value, [])

    async def update_preference(
        self,
        user_id: str,
        key: str,
        value: Any
    ) -> Dict[str, Any]:
        """
        Update a single preference.

        Args:
            user_id: User identifier.
            key: Preference key.
            value: New value.

        Returns:
            Result dictionary.
        """
        # Validate preference key
        option = self._get_option(key)
        if option is None:
            return {"success": False, "error": "Invalid preference key"}

        # Check if editable
        if not option.editable:
            return {"success": False, "error": "This preference cannot be modified"}

        # Validate value
        validation_result = self._validate_value(option, value)
        if not validation_result["valid"]:
            return {"success": False, "error": validation_result["error"]}

        # Update profile
        success = await self.profile_manager.update_preference(user_id, key, value)

        if success:
            logger.info(f"Updated preference {key} for user {user_id}")
            return {"success": True, "key": key, "value": value}
        else:
            return {"success": False, "error": "Failed to update preference"}

    async def update_preferences_bulk(
        self,
        user_id: str,
        updates: List[PreferenceUpdate]
    ) -> Dict[str, Any]:
        """
        Update multiple preferences at once.

        Args:
            user_id: User identifier.
            updates: List of preference updates.

        Returns:
            Result dictionary.
        """
        results = []
        preferences = {}

        for update in updates:
            option = self._get_option(update.key)
            if option is None:
                results.append({
                    "key": update.key,
                    "success": False,
                    "error": "Invalid preference key"
                })
                continue

            if not option.editable:
                results.append({
                    "key": update.key,
                    "success": False,
                    "error": "Not editable"
                })
                continue

            validation = self._validate_value(option, update.value)
            if not validation["valid"]:
                results.append({
                    "key": update.key,
                    "success": False,
                    "error": validation["error"]
                })
                continue

            preferences[update.key] = update.value
            results.append({
                "key": update.key,
                "success": True,
            })

        # Apply valid updates
        if preferences:
            success = await self.profile_manager.update_preferences_bulk(
                user_id, preferences
            )

            if not success:
                return {
                    "success": False,
                    "error": "Failed to save preferences",
                    "results": results
                }

        return {
            "success": True,
            "updated_count": len(preferences),
            "results": results
        }

    async def reset_preferences(
        self,
        user_id: str,
        category: Optional[PreferenceCategory] = None
    ) -> Dict[str, Any]:
        """
        Reset preferences to defaults.

        Args:
            user_id: User identifier.
            category: Optional category to reset (all if None).

        Returns:
            Result dictionary.
        """
        defaults = {}

        for option in PREFERENCE_OPTIONS:
            if category and option.category != category:
                continue

            if option.editable:
                defaults[option.key] = option.default_value

        success = await self.profile_manager.update_preferences_bulk(user_id, defaults)

        return {
            "success": success,
            "reset_count": len(defaults),
            "category": category.value if category else "all"
        }

    async def get_preference_value(
        self,
        user_id: str,
        key: str
    ) -> Optional[Any]:
        """
        Get a single preference value.

        Args:
            user_id: User identifier.
            key: Preference key.

        Returns:
            Preference value or None.
        """
        profile = await self.profile_manager.get_profile(user_id)
        if not profile:
            # Return default
            option = self._get_option(key)
            return option.default_value if option else None

        return profile.get_preference(key)

    def _get_option(self, key: str) -> Optional[PreferenceOption]:
        """Get preference option by key."""
        for option in PREFERENCE_OPTIONS:
            if option.key == key:
                return option
        return None

    def _validate_value(
        self,
        option: PreferenceOption,
        value: Any
    ) -> Dict[str, Any]:
        """Validate preference value."""
        if option.value_type == "boolean":
            if not isinstance(value, bool):
                return {"valid": False, "error": "Value must be boolean"}

        elif option.value_type == "number":
            if not isinstance(value, (int, float)):
                return {"valid": False, "error": "Value must be a number"}
            if option.min_value is not None and value < option.min_value:
                return {"valid": False, "error": f"Value must be at least {option.min_value}"}
            if option.max_value is not None and value > option.max_value:
                return {"valid": False, "error": f"Value must be at most {option.max_value}"}

        elif option.value_type == "enum":
            valid_values = [opt["value"] for opt in (option.options or [])]
            if value not in valid_values:
                return {"valid": False, "error": f"Value must be one of: {valid_values}"}

        elif option.value_type == "string":
            if not isinstance(value, str):
                return {"valid": False, "error": "Value must be a string"}

        return {"valid": True}


# Singleton instance
_preferences_api: Optional[PreferencesAPI] = None


def get_preferences_api() -> PreferencesAPI:
    """Get singleton preferences API."""
    global _preferences_api
    if _preferences_api is None:
        _preferences_api = PreferencesAPI()
    return _preferences_api
