"""
Product Rules Engine for Digital Bank Chatbot.

Allows product team to define and manage:
- Chat flow behavior (upsell timing, insights placement)
- Intent validation and feedback messages
- User segment-specific rules
- Dynamic content based on user characteristics
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Types
# =============================================================================

class RuleType(str, Enum):
    """Types of rules that can be defined."""
    CHAT_FLOW = "chat_flow"
    INTENT_BEHAVIOR = "intent_behavior"
    UPSELL = "upsell"
    INSIGHT = "insight"
    CONTENT = "content"
    RESTRICTION = "restriction"
    PERSONALIZATION = "personalization"


class FlowPosition(str, Enum):
    """Position in conversation for content injection."""
    CONVERSATION_START = "conversation_start"
    BEFORE_INTENT = "before_intent"
    AFTER_INTENT = "after_intent"
    CONVERSATION_END = "conversation_end"
    MID_CONVERSATION = "mid_conversation"  # After N turns


class UserSegment(str, Enum):
    """Predefined user segments."""
    ALL = "all"
    NEW_CUSTOMER = "new_customer"
    PREMIUM = "premium"
    STANDARD = "standard"
    YOUNG_ADULT = "young_adult"  # 18-25
    ADULT = "adult"  # 26-45
    SENIOR = "senior"  # 46+
    HIGH_VALUE = "high_value"
    AT_RISK = "at_risk"  # Churn risk
    TECH_SAVVY = "tech_savvy"
    TRADITIONAL = "traditional"


class ConditionOperator(str, Enum):
    """Operators for rule conditions."""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_EQUAL = "gte"
    LESS_EQUAL = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    BETWEEN = "between"
    EXISTS = "exists"


# =============================================================================
# Rule Definitions
# =============================================================================

@dataclass
class Condition:
    """Single condition for rule evaluation."""
    field: str  # e.g., "user.age", "user.account_type", "context.time_of_day"
    operator: ConditionOperator
    value: Any

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate this condition against context."""
        actual_value = self._get_nested_value(context, self.field)

        if actual_value is None and self.operator != ConditionOperator.EXISTS:
            return False

        if self.operator == ConditionOperator.EQUALS:
            return actual_value == self.value
        elif self.operator == ConditionOperator.NOT_EQUALS:
            return actual_value != self.value
        elif self.operator == ConditionOperator.GREATER_THAN:
            return actual_value > self.value
        elif self.operator == ConditionOperator.LESS_THAN:
            return actual_value < self.value
        elif self.operator == ConditionOperator.GREATER_EQUAL:
            return actual_value >= self.value
        elif self.operator == ConditionOperator.LESS_EQUAL:
            return actual_value <= self.value
        elif self.operator == ConditionOperator.IN:
            return actual_value in self.value
        elif self.operator == ConditionOperator.NOT_IN:
            return actual_value not in self.value
        elif self.operator == ConditionOperator.CONTAINS:
            return self.value in str(actual_value)
        elif self.operator == ConditionOperator.BETWEEN:
            return self.value[0] <= actual_value <= self.value[1]
        elif self.operator == ConditionOperator.EXISTS:
            return actual_value is not None

        return False

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value


@dataclass
class RuleAction:
    """Action to take when rule matches."""
    action_type: str  # e.g., "inject_content", "modify_response", "set_flag"
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProductRule:
    """
    A product-defined rule that controls chatbot behavior.
    """
    rule_id: str
    name: str
    description: str
    rule_type: RuleType
    priority: int = 100  # Lower = higher priority
    enabled: bool = True

    # Targeting
    segments: List[UserSegment] = field(default_factory=lambda: [UserSegment.ALL])
    conditions: List[Condition] = field(default_factory=list)
    condition_logic: str = "AND"  # "AND" or "OR"

    # Actions
    actions: List[RuleAction] = field(default_factory=list)

    # Timing
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    time_of_day_start: Optional[time] = None
    time_of_day_end: Optional[time] = None
    days_of_week: Optional[List[int]] = None  # 0=Monday, 6=Sunday

    # Frequency control
    max_triggers_per_session: Optional[int] = None
    max_triggers_per_day: Optional[int] = None
    cooldown_minutes: Optional[int] = None

    # Metadata
    created_by: str = "system"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)

    def matches(self, context: Dict[str, Any]) -> bool:
        """Check if rule matches the given context."""
        if not self.enabled:
            return False

        # Check time validity
        now = datetime.utcnow()
        if self.effective_from and now < self.effective_from:
            return False
        if self.effective_until and now > self.effective_until:
            return False

        # Check time of day
        if self.time_of_day_start and self.time_of_day_end:
            current_time = now.time()
            if not (self.time_of_day_start <= current_time <= self.time_of_day_end):
                return False

        # Check day of week
        if self.days_of_week:
            if now.weekday() not in self.days_of_week:
                return False

        # Check segments
        user_segments = context.get("user", {}).get("segments", [UserSegment.ALL])
        if UserSegment.ALL not in self.segments:
            if not any(seg in self.segments for seg in user_segments):
                return False

        # Check conditions
        if not self.conditions:
            return True

        if self.condition_logic == "AND":
            return all(cond.evaluate(context) for cond in self.conditions)
        else:  # OR
            return any(cond.evaluate(context) for cond in self.conditions)


@dataclass
class IntentBehaviorRule:
    """
    Rule defining how an intent should behave.

    Controls:
    - Validation message before execution
    - Feedback message after execution
    - Custom prompts per user segment
    """
    intent_id: str

    # Validation phase (before execution)
    validation_enabled: bool = True
    validation_message_template: str = ""
    validation_requires_confirmation: bool = False

    # Feedback phase (after execution)
    feedback_enabled: bool = True
    feedback_message_template: str = ""
    feedback_include_summary: bool = True

    # Segment-specific overrides
    segment_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Personalization
    personalization_fields: List[str] = field(default_factory=list)

    def get_validation_message(
        self,
        context: Dict[str, Any],
        user_segment: Optional[UserSegment] = None
    ) -> Optional[str]:
        """Get validation message for given context."""
        if not self.validation_enabled:
            return None

        template = self.validation_message_template

        # Check for segment override
        if user_segment and user_segment.value in self.segment_overrides:
            override = self.segment_overrides[user_segment.value]
            template = override.get("validation_message_template", template)

        return self._render_template(template, context)

    def get_feedback_message(
        self,
        context: Dict[str, Any],
        execution_result: Dict[str, Any],
        user_segment: Optional[UserSegment] = None
    ) -> Optional[str]:
        """Get feedback message for given context and result."""
        if not self.feedback_enabled:
            return None

        template = self.feedback_message_template

        # Check for segment override
        if user_segment and user_segment.value in self.segment_overrides:
            override = self.segment_overrides[user_segment.value]
            template = override.get("feedback_message_template", template)

        # Merge execution result into context
        full_context = {**context, "result": execution_result}
        return self._render_template(template, full_context)

    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """Render template with context values."""
        try:
            # Simple placeholder replacement: {{field.path}}
            import re

            def replace_placeholder(match):
                path = match.group(1)
                value = self._get_nested_value(context, path)
                return str(value) if value is not None else ""

            return re.sub(r"\{\{([^}]+)\}\}", replace_placeholder, template)
        except Exception as e:
            logger.warning(f"Template rendering error: {e}")
            return template

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get value from nested dictionary."""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value


@dataclass
class UpsellRule:
    """
    Rule for upsell/cross-sell opportunities.
    """
    rule_id: str
    name: str
    product_id: str
    product_name: str

    # Positioning
    position: FlowPosition = FlowPosition.AFTER_INTENT
    trigger_intents: List[str] = field(default_factory=list)

    # Content
    offer_message_template: str = ""
    call_to_action: str = ""

    # Targeting
    eligible_segments: List[UserSegment] = field(default_factory=list)
    exclude_segments: List[UserSegment] = field(default_factory=list)
    conditions: List[Condition] = field(default_factory=list)

    # Frequency
    max_per_session: int = 1
    max_per_day: int = 3
    cooldown_hours: int = 24

    # Priority
    priority: int = 100

    enabled: bool = True


@dataclass
class InsightRule:
    """
    Rule for showing account insights to users.
    """
    rule_id: str
    name: str
    insight_type: str  # e.g., "spending_alert", "savings_tip", "payment_reminder"

    # Positioning
    position: FlowPosition = FlowPosition.CONVERSATION_START

    # Content
    message_template: str = ""

    # Targeting
    segments: List[UserSegment] = field(default_factory=list)
    conditions: List[Condition] = field(default_factory=list)

    # User preference key (if user can opt out)
    preference_key: Optional[str] = None

    # Frequency
    max_per_session: int = 1
    max_per_day: int = 1

    priority: int = 100
    enabled: bool = True


# =============================================================================
# Rules Engine
# =============================================================================

class RulesEngine:
    """
    Product Rules Engine for managing and evaluating rules.
    """

    def __init__(self):
        """Initialize the rules engine."""
        self._rules: Dict[str, ProductRule] = {}
        self._intent_behaviors: Dict[str, IntentBehaviorRule] = {}
        self._upsell_rules: Dict[str, UpsellRule] = {}
        self._insight_rules: Dict[str, InsightRule] = {}
        self._trigger_counts: Dict[str, Dict[str, int]] = {}  # session_id -> rule_id -> count

        # Load default rules
        self._load_default_rules()

    def _load_default_rules(self):
        """Load default product rules."""
        # Default intent behaviors
        self._intent_behaviors = {
            "account.balance": IntentBehaviorRule(
                intent_id="account.balance",
                validation_message_template=(
                    "אני עומד להציג לך את יתרת החשבון שלך. "
                    "האם זו הפעולה שרצית לבצע?"
                ),
                validation_requires_confirmation=False,
                feedback_message_template=(
                    "הצגתי את יתרת החשבון שלך. "
                    "יתרה נוכחית: {{result.balance}} ₪. "
                    "האם יש משהו נוסף שאוכל לעזור בו?"
                ),
                segment_overrides={
                    "senior": {
                        "validation_message_template": (
                            "אני הולך להראות לך כמה כסף יש לך בחשבון. "
                            "זה מה שביקשת?"
                        ),
                        "feedback_message_template": (
                            "הנה היתרה בחשבון שלך: {{result.balance}} שקלים. "
                            "רוצה לדעת עוד משהו?"
                        ),
                    }
                }
            ),
            "transaction.transfer": IntentBehaviorRule(
                intent_id="transaction.transfer",
                validation_enabled=True,
                validation_message_template=(
                    "אתה מבקש להעביר {{params.amount}} ₪ "
                    "{% if params.to_account_name %}ל{{params.to_account_name}}{% else %}לחשבון {{params.to_account}}{% endif %}. "
                    "האם הפרטים נכונים?"
                ),
                validation_requires_confirmation=True,
                feedback_message_template=(
                    "✅ ההעברה בוצעה בהצלחה!\n\n"
                    "פרטי העברה:\n"
                    "• סכום: {{result.amount}} ₪\n"
                    "• לחשבון: {{result.to_account}}\n"
                    "• מספר אסמכתא: {{result.reference}}\n\n"
                    "היתרה החדשה בחשבון: {{result.new_balance}} ₪"
                ),
            ),
            "loan.calculator": IntentBehaviorRule(
                intent_id="loan.calculator",
                validation_enabled=False,
                feedback_message_template=(
                    "📊 תוצאות החישוב:\n\n"
                    "• סכום הלוואה: {{result.principal}} ₪\n"
                    "• ריבית שנתית: {{result.annual_rate}}%\n"
                    "• תקופה: {{result.tenure_months}} חודשים\n"
                    "• החזר חודשי: {{result.monthly_payment}} ₪\n"
                    "• סה\"כ לתשלום: {{result.total_payment}} ₪\n\n"
                    "⚠️ הערה: זהו חישוב להערכה בלבד. התנאים בפועל עשויים להשתנות."
                ),
            ),
        }

        # Default upsell rules
        self._upsell_rules["savings_after_balance"] = UpsellRule(
            rule_id="savings_after_balance",
            name="Savings Account Upsell After Balance Check",
            product_id="savings_plus",
            product_name="חשבון חיסכון פלוס",
            position=FlowPosition.AFTER_INTENT,
            trigger_intents=["account.balance"],
            offer_message_template=(
                "💡 טיפ: ראינו שיש לך יתרה נזילה של {{user.available_balance}} ₪. "
                "עם חשבון חיסכון פלוס תוכל להרוויח עד {{product.interest_rate}}% ריבית שנתית. "
                "רוצה לשמוע עוד?"
            ),
            call_to_action="כן, ספר לי עוד",
            eligible_segments=[UserSegment.STANDARD, UserSegment.PREMIUM],
            conditions=[
                Condition("user.available_balance", ConditionOperator.GREATER_THAN, 10000),
                Condition("user.has_savings_account", ConditionOperator.EQUALS, False),
            ],
        )

        # Default insight rules
        self._insight_rules["spending_alert"] = InsightRule(
            rule_id="spending_alert",
            name="High Spending Alert",
            insight_type="spending_alert",
            position=FlowPosition.CONVERSATION_START,
            message_template=(
                "📊 תובנה: שמנו לב שההוצאות שלך החודש גבוהות ב-{{insight.percent_increase}}% "
                "בהשוואה לממוצע. הקטגוריה הבולטת: {{insight.top_category}}."
            ),
            preference_key="insights.spending_alerts",
            segments=[UserSegment.ALL],
            conditions=[
                Condition("insights.spending_above_average", ConditionOperator.EQUALS, True),
            ],
        )

    # =========================================================================
    # Rule Management
    # =========================================================================

    def add_rule(self, rule: ProductRule) -> None:
        """Add or update a product rule."""
        self._rules[rule.rule_id] = rule
        logger.info(f"Added/updated rule: {rule.rule_id}")

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info(f"Removed rule: {rule_id}")
            return True
        return False

    def get_rule(self, rule_id: str) -> Optional[ProductRule]:
        """Get a rule by ID."""
        return self._rules.get(rule_id)

    def list_rules(
        self,
        rule_type: Optional[RuleType] = None,
        enabled_only: bool = True
    ) -> List[ProductRule]:
        """List all rules, optionally filtered."""
        rules = list(self._rules.values())

        if rule_type:
            rules = [r for r in rules if r.rule_type == rule_type]

        if enabled_only:
            rules = [r for r in rules if r.enabled]

        return sorted(rules, key=lambda r: r.priority)

    def set_intent_behavior(self, behavior: IntentBehaviorRule) -> None:
        """Set behavior rule for an intent."""
        self._intent_behaviors[behavior.intent_id] = behavior
        logger.info(f"Set intent behavior for: {behavior.intent_id}")

    def get_intent_behavior(self, intent_id: str) -> Optional[IntentBehaviorRule]:
        """Get behavior rule for an intent."""
        return self._intent_behaviors.get(intent_id)

    def add_upsell_rule(self, rule: UpsellRule) -> None:
        """Add an upsell rule."""
        self._upsell_rules[rule.rule_id] = rule

    def add_insight_rule(self, rule: InsightRule) -> None:
        """Add an insight rule."""
        self._insight_rules[rule.rule_id] = rule

    # =========================================================================
    # Rule Evaluation
    # =========================================================================

    def evaluate_rules(
        self,
        context: Dict[str, Any],
        rule_type: Optional[RuleType] = None
    ) -> List[ProductRule]:
        """
        Evaluate all matching rules for given context.

        Args:
            context: Full context including user, session, etc.
            rule_type: Optional filter by rule type.

        Returns:
            List of matching rules, sorted by priority.
        """
        matching = []

        for rule in self._rules.values():
            if rule_type and rule.rule_type != rule_type:
                continue

            if rule.matches(context):
                # Check trigger limits
                if self._check_trigger_limits(rule, context):
                    matching.append(rule)

        return sorted(matching, key=lambda r: r.priority)

    def get_applicable_upsells(
        self,
        context: Dict[str, Any],
        position: FlowPosition,
        current_intent: Optional[str] = None
    ) -> List[UpsellRule]:
        """Get applicable upsell offers for current position."""
        applicable = []

        for rule in self._upsell_rules.values():
            if not rule.enabled:
                continue

            if rule.position != position:
                continue

            # Check if triggered by current intent
            if current_intent and rule.trigger_intents:
                if current_intent not in rule.trigger_intents:
                    continue

            # Check segments
            user_segments = context.get("user", {}).get("segments", [])
            if rule.eligible_segments:
                if not any(seg in rule.eligible_segments for seg in user_segments):
                    continue

            if rule.exclude_segments:
                if any(seg in rule.exclude_segments for seg in user_segments):
                    continue

            # Check conditions
            if rule.conditions:
                if not all(c.evaluate(context) for c in rule.conditions):
                    continue

            # Check frequency limits
            if self._check_upsell_limits(rule, context):
                applicable.append(rule)

        return sorted(applicable, key=lambda r: r.priority)

    def get_applicable_insights(
        self,
        context: Dict[str, Any],
        position: FlowPosition,
        user_preferences: Dict[str, Any]
    ) -> List[InsightRule]:
        """Get applicable insights for current position."""
        applicable = []

        for rule in self._insight_rules.values():
            if not rule.enabled:
                continue

            if rule.position != position:
                continue

            # Check user opt-out
            if rule.preference_key:
                if not user_preferences.get(rule.preference_key, True):
                    continue

            # Check segments
            user_segments = context.get("user", {}).get("segments", [])
            if rule.segments and UserSegment.ALL not in rule.segments:
                if not any(seg in rule.segments for seg in user_segments):
                    continue

            # Check conditions
            if rule.conditions:
                if not all(c.evaluate(context) for c in rule.conditions):
                    continue

            applicable.append(rule)

        return sorted(applicable, key=lambda r: r.priority)

    def _check_trigger_limits(
        self,
        rule: ProductRule,
        context: Dict[str, Any]
    ) -> bool:
        """Check if rule can be triggered based on limits."""
        session_id = context.get("session_id", "default")

        if session_id not in self._trigger_counts:
            self._trigger_counts[session_id] = {}

        current_count = self._trigger_counts[session_id].get(rule.rule_id, 0)

        if rule.max_triggers_per_session:
            if current_count >= rule.max_triggers_per_session:
                return False

        return True

    def _check_upsell_limits(
        self,
        rule: UpsellRule,
        context: Dict[str, Any]
    ) -> bool:
        """Check upsell frequency limits."""
        session_id = context.get("session_id", "default")

        if session_id not in self._trigger_counts:
            self._trigger_counts[session_id] = {}

        current_count = self._trigger_counts[session_id].get(f"upsell_{rule.rule_id}", 0)

        if current_count >= rule.max_per_session:
            return False

        return True

    def record_trigger(
        self,
        rule_id: str,
        session_id: str,
        rule_type: str = "rule"
    ) -> None:
        """Record that a rule was triggered."""
        if session_id not in self._trigger_counts:
            self._trigger_counts[session_id] = {}

        key = f"{rule_type}_{rule_id}" if rule_type != "rule" else rule_id
        self._trigger_counts[session_id][key] = (
            self._trigger_counts[session_id].get(key, 0) + 1
        )

    # =========================================================================
    # Configuration Import/Export
    # =========================================================================

    def export_rules(self) -> Dict[str, Any]:
        """Export all rules to dictionary format."""
        return {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "name": r.name,
                    "description": r.description,
                    "rule_type": r.rule_type.value,
                    "priority": r.priority,
                    "enabled": r.enabled,
                    "segments": [s.value for s in r.segments],
                    "conditions": [
                        {"field": c.field, "operator": c.operator.value, "value": c.value}
                        for c in r.conditions
                    ],
                    "actions": [{"type": a.action_type, "params": a.parameters} for a in r.actions],
                }
                for r in self._rules.values()
            ],
            "intent_behaviors": {
                intent_id: {
                    "validation_enabled": b.validation_enabled,
                    "validation_message_template": b.validation_message_template,
                    "feedback_enabled": b.feedback_enabled,
                    "feedback_message_template": b.feedback_message_template,
                    "segment_overrides": b.segment_overrides,
                }
                for intent_id, b in self._intent_behaviors.items()
            },
        }

    def import_rules(self, data: Dict[str, Any]) -> None:
        """Import rules from dictionary format."""
        # Import product rules
        for rule_data in data.get("rules", []):
            conditions = [
                Condition(
                    field=c["field"],
                    operator=ConditionOperator(c["operator"]),
                    value=c["value"]
                )
                for c in rule_data.get("conditions", [])
            ]

            actions = [
                RuleAction(action_type=a["type"], parameters=a.get("params", {}))
                for a in rule_data.get("actions", [])
            ]

            rule = ProductRule(
                rule_id=rule_data["rule_id"],
                name=rule_data["name"],
                description=rule_data.get("description", ""),
                rule_type=RuleType(rule_data["rule_type"]),
                priority=rule_data.get("priority", 100),
                enabled=rule_data.get("enabled", True),
                segments=[UserSegment(s) for s in rule_data.get("segments", ["all"])],
                conditions=conditions,
                actions=actions,
            )
            self.add_rule(rule)

        # Import intent behaviors
        for intent_id, behavior_data in data.get("intent_behaviors", {}).items():
            behavior = IntentBehaviorRule(
                intent_id=intent_id,
                validation_enabled=behavior_data.get("validation_enabled", True),
                validation_message_template=behavior_data.get("validation_message_template", ""),
                feedback_enabled=behavior_data.get("feedback_enabled", True),
                feedback_message_template=behavior_data.get("feedback_message_template", ""),
                segment_overrides=behavior_data.get("segment_overrides", {}),
            )
            self.set_intent_behavior(behavior)

        logger.info(f"Imported {len(data.get('rules', []))} rules and {len(data.get('intent_behaviors', {}))} intent behaviors")


# Singleton instance
_rules_engine: Optional[RulesEngine] = None


def get_rules_engine() -> RulesEngine:
    """Get the singleton rules engine instance."""
    global _rules_engine
    if _rules_engine is None:
        _rules_engine = RulesEngine()
    return _rules_engine
