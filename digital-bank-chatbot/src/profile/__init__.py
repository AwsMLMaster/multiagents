"""
User Profile and Preferences module for Digital Bank Chatbot.
"""

from .user_profile import (
    UserProfile,
    UserCharacteristics,
    InsightPreferences,
    NotificationPreferences,
    ChatbotPreferences,
    ProfileManager,
    AccountType,
    CommunicationStyle,
    PersonalityType,
    TechSavvyLevel,
    RiskTolerance,
    get_profile_manager,
)

from .preferences_api import (
    PreferencesAPI,
    PreferenceCategory,
    PreferenceOption,
    PreferenceUpdate,
    PreferencesResponse,
    PREFERENCE_OPTIONS,
    get_preferences_api,
)

__all__ = [
    # User Profile
    "UserProfile",
    "UserCharacteristics",
    "InsightPreferences",
    "NotificationPreferences",
    "ChatbotPreferences",
    "ProfileManager",
    "AccountType",
    "CommunicationStyle",
    "PersonalityType",
    "TechSavvyLevel",
    "RiskTolerance",
    "get_profile_manager",
    # Preferences API
    "PreferencesAPI",
    "PreferenceCategory",
    "PreferenceOption",
    "PreferenceUpdate",
    "PreferencesResponse",
    "PREFERENCE_OPTIONS",
    "get_preferences_api",
]
