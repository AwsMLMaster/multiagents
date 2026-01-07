"""
Intent Flow Controller for Digital Bank Chatbot.

Controls the conversation flow based on product rules:
- Validation messages before intent execution
- Feedback messages after intent execution
- Upsell/cross-sell injection
- Insight injection
- User segment-specific behavior
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .engine import (
    RulesEngine,
    IntentBehaviorRule,
    UpsellRule,
    InsightRule,
    FlowPosition,
    UserSegment,
    get_rules_engine,
)
from ..profile.user_profile import UserProfile, get_profile_manager
from ..memory.memory_manager import MemoryManager, get_memory_manager

logger = logging.getLogger(__name__)


@dataclass
class FlowContent:
    """Content to inject into the conversation flow."""
    content_type: str  # "validation", "feedback", "upsell", "insight", "tip"
    message: str
    priority: int = 100
    requires_response: bool = False
    action_buttons: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FlowDecision:
    """Decision about how to handle current flow position."""
    allow_proceed: bool = True
    pre_content: List[FlowContent] = field(default_factory=list)
    post_content: List[FlowContent] = field(default_factory=list)
    require_confirmation: bool = False
    modified_response: Optional[str] = None
    skip_intent: bool = False
    redirect_intent: Optional[str] = None


class IntentFlowController:
    """
    Controls conversation flow based on product rules and user preferences.
    """

    def __init__(
        self,
        rules_engine: Optional[RulesEngine] = None,
        memory_manager: Optional[MemoryManager] = None
    ):
        """Initialize flow controller."""
        self.rules_engine = rules_engine or get_rules_engine()
        self.memory_manager = memory_manager or get_memory_manager()

    async def get_pre_intent_content(
        self,
        intent_id: str,
        user_profile: UserProfile,
        context: Dict[str, Any],
        params: Dict[str, Any]
    ) -> FlowDecision:
        """
        Get content to show before intent execution.

        Args:
            intent_id: Intent to execute.
            user_profile: User profile.
            context: Current context.
            params: Intent parameters.

        Returns:
            FlowDecision with pre-content.
        """
        decision = FlowDecision()

        # Get user segment
        user_segment = self._get_primary_segment(user_profile)

        # Get intent behavior rules
        behavior = self.rules_engine.get_intent_behavior(intent_id)

        if behavior and behavior.validation_enabled:
            # Get validation message
            validation_context = {
                **context,
                "params": params,
                "user": user_profile.to_context(),
            }

            validation_message = behavior.get_validation_message(
                validation_context,
                user_segment
            )

            if validation_message:
                decision.pre_content.append(FlowContent(
                    content_type="validation",
                    message=validation_message,
                    requires_response=behavior.validation_requires_confirmation,
                    priority=10,
                ))

                if behavior.validation_requires_confirmation:
                    decision.require_confirmation = True

        # Check for conversation start insights
        if context.get("conversation_turn", 0) == 0:
            insights = await self._get_applicable_insights(
                user_profile,
                context,
                FlowPosition.CONVERSATION_START
            )
            decision.pre_content.extend(insights)

        # Check for before-intent content
        before_intent_content = await self._get_applicable_insights(
            user_profile,
            context,
            FlowPosition.BEFORE_INTENT
        )
        decision.pre_content.extend(before_intent_content)

        # Sort by priority
        decision.pre_content.sort(key=lambda x: x.priority)

        return decision

    async def get_post_intent_content(
        self,
        intent_id: str,
        user_profile: UserProfile,
        context: Dict[str, Any],
        execution_result: Dict[str, Any]
    ) -> FlowDecision:
        """
        Get content to show after intent execution.

        Args:
            intent_id: Executed intent.
            user_profile: User profile.
            context: Current context.
            execution_result: Result from intent execution.

        Returns:
            FlowDecision with post-content.
        """
        decision = FlowDecision()

        # Get user segment
        user_segment = self._get_primary_segment(user_profile)

        # Get intent behavior rules
        behavior = self.rules_engine.get_intent_behavior(intent_id)

        if behavior and behavior.feedback_enabled:
            # Get feedback message
            feedback_context = {
                **context,
                "user": user_profile.to_context(),
            }

            feedback_message = behavior.get_feedback_message(
                feedback_context,
                execution_result,
                user_segment
            )

            if feedback_message:
                decision.post_content.append(FlowContent(
                    content_type="feedback",
                    message=feedback_message,
                    priority=10,
                ))

        # Check for upsell opportunities
        if user_profile.chatbot_preferences.show_upsell_offers:
            upsells = await self._get_applicable_upsells(
                user_profile,
                context,
                intent_id
            )
            decision.post_content.extend(upsells)

        # Check for after-intent insights
        insights = await self._get_applicable_insights(
            user_profile,
            context,
            FlowPosition.AFTER_INTENT
        )
        decision.post_content.extend(insights)

        # Sort by priority
        decision.post_content.sort(key=lambda x: x.priority)

        # Record this interaction in memory
        await self._record_interaction(
            user_profile.user_id,
            context.get("session_id", ""),
            intent_id,
            execution_result
        )

        return decision

    async def get_conversation_end_content(
        self,
        user_profile: UserProfile,
        context: Dict[str, Any]
    ) -> List[FlowContent]:
        """
        Get content to show at conversation end.

        Args:
            user_profile: User profile.
            context: Current context.

        Returns:
            List of content to show.
        """
        content = []

        # Get end-of-conversation insights
        insights = await self._get_applicable_insights(
            user_profile,
            context,
            FlowPosition.CONVERSATION_END
        )
        content.extend(insights)

        # Get end-of-conversation upsells
        if user_profile.chatbot_preferences.show_upsell_offers:
            upsells = await self._get_applicable_upsells(
                user_profile,
                context,
                position=FlowPosition.CONVERSATION_END
            )
            content.extend(upsells)

        return content

    async def _get_applicable_insights(
        self,
        user_profile: UserProfile,
        context: Dict[str, Any],
        position: FlowPosition
    ) -> List[FlowContent]:
        """Get applicable insights for current position."""
        content = []

        if not user_profile.chatbot_preferences.show_insights_in_chat:
            return content

        # Build context for rule evaluation
        rule_context = {
            **context,
            "user": user_profile.to_context(),
        }

        # Get applicable insight rules
        user_preferences = user_profile.get_all_preferences()
        insight_rules = self.rules_engine.get_applicable_insights(
            rule_context,
            position,
            user_preferences
        )

        for rule in insight_rules[:2]:  # Max 2 insights per position
            # Render message template
            message = self._render_template(rule.message_template, rule_context)

            content.append(FlowContent(
                content_type="insight",
                message=message,
                priority=rule.priority,
                metadata={"insight_type": rule.insight_type}
            ))

            # Record trigger
            self.rules_engine.record_trigger(
                rule.rule_id,
                context.get("session_id", ""),
                "insight"
            )

        return content

    async def _get_applicable_upsells(
        self,
        user_profile: UserProfile,
        context: Dict[str, Any],
        current_intent: Optional[str] = None,
        position: FlowPosition = FlowPosition.AFTER_INTENT
    ) -> List[FlowContent]:
        """Get applicable upsell offers."""
        content = []

        # Build context for rule evaluation
        rule_context = {
            **context,
            "user": user_profile.to_context(),
        }

        # Get applicable upsell rules
        upsell_rules = self.rules_engine.get_applicable_upsells(
            rule_context,
            position,
            current_intent
        )

        for rule in upsell_rules[:1]:  # Max 1 upsell per position
            # Render message template
            message = self._render_template(rule.offer_message_template, rule_context)

            content.append(FlowContent(
                content_type="upsell",
                message=message,
                priority=rule.priority,
                requires_response=True,
                action_buttons=[
                    {"label": rule.call_to_action, "action": f"learn_more:{rule.product_id}"},
                    {"label": "לא תודה", "action": "dismiss_upsell"},
                ],
                metadata={
                    "product_id": rule.product_id,
                    "product_name": rule.product_name,
                }
            ))

            # Record trigger
            self.rules_engine.record_trigger(
                rule.rule_id,
                context.get("session_id", ""),
                "upsell"
            )

        return content

    def _get_primary_segment(self, user_profile: UserProfile) -> Optional[UserSegment]:
        """Get user's primary segment."""
        segments = user_profile.get_segments()

        # Priority order for segment selection
        priority_segments = [
            "premium", "high_value", "senior", "young_adult",
            "new_customer", "at_risk", "standard"
        ]

        for seg in priority_segments:
            if seg in segments:
                try:
                    return UserSegment(seg)
                except ValueError:
                    continue

        return UserSegment.STANDARD

    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """Render template with context values."""
        import re

        def replace_placeholder(match):
            path = match.group(1)
            value = self._get_nested_value(context, path)
            return str(value) if value is not None else ""

        return re.sub(r"\{\{([^}]+)\}\}", replace_placeholder, template)

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

    async def _record_interaction(
        self,
        user_id: str,
        session_id: str,
        intent_id: str,
        result: Dict[str, Any]
    ) -> None:
        """Record interaction in memory for future reference."""
        try:
            # Create summary
            summary = f"Executed {intent_id}"
            if result.get("success"):
                summary += " successfully"
            else:
                summary += " with errors"

            await self.memory_manager.record_interaction(
                user_id=user_id,
                session_id=session_id,
                event_type="intent_execution",
                summary=summary,
                intent=intent_id,
                outcome="success" if result.get("success") else "failure",
                details={
                    "intent": intent_id,
                    "result_data": result.get("data", {}),
                }
            )
        except Exception as e:
            logger.warning(f"Failed to record interaction: {e}")


class ConversationFlowManager:
    """
    High-level conversation flow manager.

    Integrates all flow control components.
    """

    def __init__(self):
        """Initialize flow manager."""
        self.flow_controller = IntentFlowController()
        self.profile_manager = get_profile_manager()
        self.memory_manager = get_memory_manager()

    async def prepare_turn(
        self,
        user_id: str,
        session_id: str,
        detected_intent: str,
        intent_params: Dict[str, Any],
        conversation_turn: int
    ) -> Tuple[FlowDecision, Dict[str, Any]]:
        """
        Prepare for a conversation turn.

        Returns flow decision and enriched context.
        """
        # Get user profile
        profile = await self.profile_manager.get_profile(user_id)
        if not profile:
            profile = await self.profile_manager.get_or_create_profile(
                user_id, user_id
            )

        # Get memory context
        memory_context = await self.memory_manager.get_context_for_intent(
            user_id, session_id, detected_intent
        )

        # Build context
        context = {
            "session_id": session_id,
            "conversation_turn": conversation_turn,
            "memory": memory_context,
        }

        # Get pre-intent content
        decision = await self.flow_controller.get_pre_intent_content(
            detected_intent,
            profile,
            context,
            intent_params
        )

        return decision, context

    async def finalize_turn(
        self,
        user_id: str,
        session_id: str,
        executed_intent: str,
        execution_result: Dict[str, Any],
        context: Dict[str, Any]
    ) -> FlowDecision:
        """
        Finalize a conversation turn.

        Returns flow decision with post-content.
        """
        # Get user profile
        profile = await self.profile_manager.get_profile(user_id)
        if not profile:
            return FlowDecision()

        # Get post-intent content
        decision = await self.flow_controller.get_post_intent_content(
            executed_intent,
            profile,
            context,
            execution_result
        )

        return decision


# Singleton instance
_flow_manager: Optional[ConversationFlowManager] = None


def get_flow_manager() -> ConversationFlowManager:
    """Get singleton flow manager."""
    global _flow_manager
    if _flow_manager is None:
        _flow_manager = ConversationFlowManager()
    return _flow_manager
