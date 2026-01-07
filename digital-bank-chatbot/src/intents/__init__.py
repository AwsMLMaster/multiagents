"""
Intent management module for Digital Bank Chatbot.
"""

from .registry import (
    INTENT_REGISTRY,
    IntentCategory,
    IntentDefinition,
    get_intent,
    get_intents_by_category,
    get_intents_for_agent,
    get_all_examples,
    add_custom_intent,
    disable_intent,
    enable_intent,
)

from .classifier import (
    IntentClassifier,
    RuleBasedClassifier,
    HybridClassifier,
    ClassificationResult,
)

__all__ = [
    # Registry
    "INTENT_REGISTRY",
    "IntentCategory",
    "IntentDefinition",
    "get_intent",
    "get_intents_by_category",
    "get_intents_for_agent",
    "get_all_examples",
    "add_custom_intent",
    "disable_intent",
    "enable_intent",
    # Classifiers
    "IntentClassifier",
    "RuleBasedClassifier",
    "HybridClassifier",
    "ClassificationResult",
]
