"""
Product Rules Engine module for Digital Bank Chatbot.
"""

from .engine import (
    RulesEngine,
    ProductRule,
    IntentBehaviorRule,
    UpsellRule,
    InsightRule,
    Condition,
    RuleAction,
    RuleType,
    FlowPosition,
    UserSegment,
    ConditionOperator,
    get_rules_engine,
)

from .flow_controller import (
    IntentFlowController,
    ConversationFlowManager,
    FlowContent,
    FlowDecision,
    get_flow_manager,
)

__all__ = [
    # Rules Engine
    "RulesEngine",
    "ProductRule",
    "IntentBehaviorRule",
    "UpsellRule",
    "InsightRule",
    "Condition",
    "RuleAction",
    "RuleType",
    "FlowPosition",
    "UserSegment",
    "ConditionOperator",
    "get_rules_engine",
    # Flow Controller
    "IntentFlowController",
    "ConversationFlowManager",
    "FlowContent",
    "FlowDecision",
    "get_flow_manager",
]
