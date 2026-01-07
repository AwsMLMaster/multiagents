"""
Conversation Flow Templates

Product team-defined templates for conversation flows.
Templates define the ideal structure and content of conversations
for different intents and scenarios.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class StepType(Enum):
    """Types of flow steps."""
    GREETING = "greeting"
    ACKNOWLEDGMENT = "acknowledgment"
    CLARIFICATION = "clarification"
    INFORMATION = "information"
    CONFIRMATION = "confirmation"
    ACTION = "action"
    RESULT = "result"
    UPSELL = "upsell"
    INSIGHT = "insight"
    FEEDBACK = "feedback"
    CLOSING = "closing"
    ESCALATION = "escalation"


class StepCondition(Enum):
    """Conditions for step execution."""
    ALWAYS = "always"
    IF_AUTHENTICATED = "if_authenticated"
    IF_FIRST_INTERACTION = "if_first_interaction"
    IF_RETURNING_USER = "if_returning_user"
    IF_ERROR = "if_error"
    IF_SUCCESS = "if_success"
    IF_USER_SEGMENT = "if_user_segment"
    IF_TIME_OF_DAY = "if_time_of_day"
    CUSTOM = "custom"


@dataclass
class ResponseGuideline:
    """Guideline for a specific response in the flow."""
    # Content templates
    template_he: str
    template_en: str

    # Variables that can be substituted
    variables: List[str] = field(default_factory=list)
    # e.g., {customer_name}, {amount}, {account_number}

    # Alternatives (for variation)
    alternatives_he: List[str] = field(default_factory=list)
    alternatives_en: List[str] = field(default_factory=list)

    # Formatting
    max_length: int = 200
    use_markdown: bool = False
    include_links: bool = False

    # Personalization
    adapt_to_expertise: bool = True  # Simplify for new users
    adapt_to_segment: bool = True    # Different messaging per segment


@dataclass
class FlowStep:
    """A single step in a conversation flow."""
    step_id: str
    step_type: StepType
    name: str
    description: str = ""

    # Response content
    response: Optional[ResponseGuideline] = None

    # Conditions
    condition: StepCondition = StepCondition.ALWAYS
    condition_params: Dict[str, Any] = field(default_factory=dict)

    # Timing
    delay_ms: int = 0
    timeout_ms: int = 30000  # Max time to wait for user input

    # User input
    expects_user_input: bool = False
    valid_input_patterns: List[str] = field(default_factory=list)
    input_validation_error_he: str = ""
    input_validation_error_en: str = ""

    # Branching
    next_step_on_success: Optional[str] = None
    next_step_on_failure: Optional[str] = None
    next_step_on_timeout: Optional[str] = None

    # Actions
    action_before: Optional[str] = None  # Action to execute before response
    action_after: Optional[str] = None   # Action to execute after response

    # Metadata
    is_optional: bool = False
    is_skippable: bool = False
    analytics_event: Optional[str] = None


@dataclass
class ConversationTemplate:
    """
    Template for a complete conversation flow.

    Product teams define these templates to control how
    conversations should progress for different intents.
    """
    template_id: str
    name: str
    description: str = ""
    version: str = "1.0"

    # When to use this template
    applies_to_intents: List[str] = field(default_factory=list)
    applies_to_contexts: List[str] = field(default_factory=list)

    # Flow definition
    steps: List[FlowStep] = field(default_factory=list)
    entry_step_id: str = ""

    # Global settings
    max_steps: int = 20
    max_duration_seconds: int = 600  # 10 minutes
    allow_interruption: bool = True
    allow_topic_change: bool = True

    # Quality requirements
    required_confirmations: int = 0  # How many confirmations needed
    required_acknowledgments: int = 0

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    is_active: bool = True

    def get_step(self, step_id: str) -> Optional[FlowStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None


class ConversationFlowTemplateManager:
    """
    Manages conversation flow templates.

    Provides:
    - Template storage and retrieval
    - Flow execution guidance
    - Default templates for common scenarios
    """

    def __init__(self):
        self._templates: Dict[str, ConversationTemplate] = {}
        self._load_default_templates()

    def _load_default_templates(self) -> None:
        """Load default conversation templates."""
        # Balance check flow
        self.add_template(self._create_balance_check_template())

        # Transfer flow
        self.add_template(self._create_transfer_template())

        # Offering presentation flow
        self.add_template(self._create_offering_template())

        # Complaint handling flow
        self.add_template(self._create_complaint_template())

        # Insights delivery flow
        self.add_template(self._create_insights_template())

    def add_template(self, template: ConversationTemplate) -> None:
        """Add a template to the manager."""
        self._templates[template.template_id] = template
        logger.info(f"Added conversation template: {template.template_id}")

    def get_template(self, template_id: str) -> Optional[ConversationTemplate]:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def get_template_for_intent(self, intent_id: str) -> Optional[ConversationTemplate]:
        """Get the best matching template for an intent."""
        for template in self._templates.values():
            if intent_id in template.applies_to_intents and template.is_active:
                return template
        return None

    def get_all_templates(self) -> List[ConversationTemplate]:
        """Get all templates."""
        return list(self._templates.values())

    def _create_balance_check_template(self) -> ConversationTemplate:
        """Create template for balance check conversations."""
        return ConversationTemplate(
            template_id="flow-balance-check",
            name="Balance Check Flow",
            applies_to_intents=["account.balance"],
            entry_step_id="greet",
            steps=[
                FlowStep(
                    step_id="greet",
                    step_type=StepType.ACKNOWLEDGMENT,
                    name="Acknowledge Request",
                    response=ResponseGuideline(
                        template_he="רגע, בודק את היתרה שלך...",
                        template_en="One moment, checking your balance...",
                    ),
                    delay_ms=500,
                    next_step_on_success="show_balance",
                ),
                FlowStep(
                    step_id="show_balance",
                    step_type=StepType.RESULT,
                    name="Show Balance",
                    response=ResponseGuideline(
                        template_he="היתרה הנוכחית בחשבון {account_type} היא {balance} ₪",
                        template_en="Your current {account_type} balance is ₪{balance}",
                        variables=["account_type", "balance"],
                    ),
                    next_step_on_success="offer_insight",
                ),
                FlowStep(
                    step_id="offer_insight",
                    step_type=StepType.INSIGHT,
                    name="Offer Insight",
                    condition=StepCondition.CUSTOM,
                    condition_params={"has_idle_balance": True},
                    response=ResponseGuideline(
                        template_he="לידיעתך, יש לך {idle_amount} ₪ שיושבים בחשבון מעל חודש. רוצה לשמוע על אפשרויות חיסכון?",
                        template_en="FYI, you have ₪{idle_amount} sitting idle for over a month. Want to hear about savings options?",
                        variables=["idle_amount"],
                    ),
                    is_optional=True,
                    expects_user_input=True,
                    next_step_on_success="show_offering",
                ),
                FlowStep(
                    step_id="show_offering",
                    step_type=StepType.UPSELL,
                    name="Show Savings Offering",
                    condition=StepCondition.CUSTOM,
                    condition_params={"user_interested": True},
                    response=ResponseGuideline(
                        template_he="יש לנו חיסכון בריבית של {interest_rate}%. תרצה לשמוע פרטים?",
                        template_en="We have a savings account with {interest_rate}% interest. Want details?",
                        variables=["interest_rate"],
                    ),
                    is_optional=True,
                    next_step_on_success="closing",
                ),
                FlowStep(
                    step_id="closing",
                    step_type=StepType.CLOSING,
                    name="Close Conversation",
                    response=ResponseGuideline(
                        template_he="אשמח לעזור בכל שאלה נוספת.",
                        template_en="Happy to help with anything else.",
                    ),
                ),
            ],
        )

    def _create_transfer_template(self) -> ConversationTemplate:
        """Create template for transfer conversations."""
        return ConversationTemplate(
            template_id="flow-transfer",
            name="Transfer Flow",
            applies_to_intents=["transaction.transfer"],
            entry_step_id="acknowledge",
            required_confirmations=1,
            steps=[
                FlowStep(
                    step_id="acknowledge",
                    step_type=StepType.ACKNOWLEDGMENT,
                    name="Acknowledge Transfer Request",
                    response=ResponseGuideline(
                        template_he="בוא נבצע את ההעברה.",
                        template_en="Let's make that transfer.",
                    ),
                    next_step_on_success="collect_details",
                ),
                FlowStep(
                    step_id="collect_details",
                    step_type=StepType.CLARIFICATION,
                    name="Collect Missing Details",
                    condition=StepCondition.CUSTOM,
                    condition_params={"missing_params": True},
                    response=ResponseGuideline(
                        template_he="לאיזה חשבון תרצה להעביר?",
                        template_en="Which account would you like to transfer to?",
                    ),
                    expects_user_input=True,
                    timeout_ms=60000,
                    next_step_on_success="confirm",
                ),
                FlowStep(
                    step_id="confirm",
                    step_type=StepType.CONFIRMATION,
                    name="Confirm Transfer Details",
                    response=ResponseGuideline(
                        template_he="אני עומד להעביר {amount} ₪ לחשבון {to_account}.\n\nעמלה: {fee} ₪\n\nלאשר?",
                        template_en="I'm about to transfer ₪{amount} to account {to_account}.\n\nFee: ₪{fee}\n\nConfirm?",
                        variables=["amount", "to_account", "fee"],
                    ),
                    expects_user_input=True,
                    valid_input_patterns=["כן", "לא", "אשר", "בטל", "yes", "no"],
                    input_validation_error_he="אנא אמור 'כן' לאישור או 'לא' לביטול",
                    input_validation_error_en="Please say 'yes' to confirm or 'no' to cancel",
                    next_step_on_success="execute",
                    next_step_on_failure="cancelled",
                ),
                FlowStep(
                    step_id="execute",
                    step_type=StepType.ACTION,
                    name="Execute Transfer",
                    action_before="execute_transfer",
                    response=ResponseGuideline(
                        template_he="מבצע את ההעברה...",
                        template_en="Processing the transfer...",
                    ),
                    delay_ms=1000,
                    next_step_on_success="success",
                    next_step_on_failure="failure",
                ),
                FlowStep(
                    step_id="success",
                    step_type=StepType.RESULT,
                    name="Transfer Success",
                    response=ResponseGuideline(
                        template_he="ההעברה בוצעה בהצלחה! ✓\n\nמספר אסמכתא: {reference_id}",
                        template_en="Transfer completed successfully! ✓\n\nReference: {reference_id}",
                        variables=["reference_id"],
                    ),
                    analytics_event="transfer_completed",
                    next_step_on_success="feedback",
                ),
                FlowStep(
                    step_id="failure",
                    step_type=StepType.RESULT,
                    name="Transfer Failed",
                    response=ResponseGuideline(
                        template_he="לצערי ההעברה לא הצליחה: {error_message}\n\nתרצה לנסות שוב או לדבר עם נציג?",
                        template_en="Unfortunately the transfer failed: {error_message}\n\nWant to try again or speak to an agent?",
                        variables=["error_message"],
                    ),
                    next_step_on_success="escalation",
                ),
                FlowStep(
                    step_id="cancelled",
                    step_type=StepType.RESULT,
                    name="Transfer Cancelled",
                    response=ResponseGuideline(
                        template_he="בסדר, ביטלתי את ההעברה. איך אפשר לעזור?",
                        template_en="OK, I've cancelled the transfer. How else can I help?",
                    ),
                ),
                FlowStep(
                    step_id="feedback",
                    step_type=StepType.FEEDBACK,
                    name="Ask for Feedback",
                    is_optional=True,
                    condition=StepCondition.CUSTOM,
                    condition_params={"show_feedback": True},
                    response=ResponseGuideline(
                        template_he="איך היה התהליך? 👍 / 👎",
                        template_en="How was the process? 👍 / 👎",
                    ),
                    expects_user_input=True,
                    timeout_ms=10000,
                ),
                FlowStep(
                    step_id="escalation",
                    step_type=StepType.ESCALATION,
                    name="Offer Escalation",
                    response=ResponseGuideline(
                        template_he="אני יכול לחבר אותך לנציג שירות. האם תרצה?",
                        template_en="I can connect you to a service agent. Would you like that?",
                    ),
                    expects_user_input=True,
                ),
            ],
        )

    def _create_offering_template(self) -> ConversationTemplate:
        """Create template for offering presentation."""
        return ConversationTemplate(
            template_id="flow-offering",
            name="Offering Presentation Flow",
            applies_to_intents=["offerings.view", "offerings.interest"],
            entry_step_id="intro",
            steps=[
                FlowStep(
                    step_id="intro",
                    step_type=StepType.INFORMATION,
                    name="Introduce Offering",
                    response=ResponseGuideline(
                        template_he="יש לי הצעה שעשויה לעניין אותך:",
                        template_en="I have an offer that might interest you:",
                    ),
                    delay_ms=500,
                    next_step_on_success="present_offering",
                ),
                FlowStep(
                    step_id="present_offering",
                    step_type=StepType.INFORMATION,
                    name="Present Offering Details",
                    response=ResponseGuideline(
                        template_he="{offering_title}\n\n{offering_description}\n\nיתרונות:\n{benefits}",
                        template_en="{offering_title}\n\n{offering_description}\n\nBenefits:\n{benefits}",
                        variables=["offering_title", "offering_description", "benefits"],
                    ),
                    next_step_on_success="personalized_message",
                ),
                FlowStep(
                    step_id="personalized_message",
                    step_type=StepType.INFORMATION,
                    name="Personalized Value",
                    response=ResponseGuideline(
                        template_he="בהתבסס על החשבון שלך, תוכל {projected_benefit}.",
                        template_en="Based on your account, you could {projected_benefit}.",
                        variables=["projected_benefit"],
                    ),
                    next_step_on_success="ask_interest",
                ),
                FlowStep(
                    step_id="ask_interest",
                    step_type=StepType.CONFIRMATION,
                    name="Ask if Interested",
                    response=ResponseGuideline(
                        template_he="האם תרצה לשמוע עוד או להתקדם עם ההצעה?",
                        template_en="Would you like to hear more or proceed with the offer?",
                    ),
                    expects_user_input=True,
                    next_step_on_success="process_interest",
                    next_step_on_failure="respect_decline",
                ),
                FlowStep(
                    step_id="process_interest",
                    step_type=StepType.ACTION,
                    name="Process Interest",
                    action_before="record_offering_interest",
                    response=ResponseGuideline(
                        template_he="מעולה! אני מעביר את הפרטים לנציג שלנו שיצור איתך קשר בקרוב.",
                        template_en="Excellent! I'm forwarding the details to our representative who will contact you soon.",
                    ),
                    next_step_on_success="next_steps",
                ),
                FlowStep(
                    step_id="respect_decline",
                    step_type=StepType.ACKNOWLEDGMENT,
                    name="Respect Decline",
                    response=ResponseGuideline(
                        template_he="בסדר גמור, אני כאן אם תשנה את דעתך. איך אפשר לעזור?",
                        template_en="Absolutely fine, I'm here if you change your mind. How can I help?",
                    ),
                ),
                FlowStep(
                    step_id="next_steps",
                    step_type=StepType.INFORMATION,
                    name="Explain Next Steps",
                    response=ResponseGuideline(
                        template_he="מה עכשיו?\n• נציג ייצור איתך קשר תוך יום עסקים\n• תוכל לשאול כל שאלה\n• ההחלטה תמיד שלך",
                        template_en="What's next?\n• An agent will contact you within 1 business day\n• You can ask any questions\n• The decision is always yours",
                    ),
                ),
            ],
        )

    def _create_complaint_template(self) -> ConversationTemplate:
        """Create template for complaint handling."""
        return ConversationTemplate(
            template_id="flow-complaint",
            name="Complaint Handling Flow",
            applies_to_intents=["support.complaint"],
            applies_to_contexts=["complaint", "frustration"],
            entry_step_id="empathize",
            steps=[
                FlowStep(
                    step_id="empathize",
                    step_type=StepType.ACKNOWLEDGMENT,
                    name="Show Empathy",
                    response=ResponseGuideline(
                        template_he="אני מצטער לשמוע שיש לך חוויה לא טובה. אני כאן כדי לעזור לפתור את זה.",
                        template_en="I'm sorry to hear you're having a bad experience. I'm here to help resolve this.",
                    ),
                    next_step_on_success="understand",
                ),
                FlowStep(
                    step_id="understand",
                    step_type=StepType.CLARIFICATION,
                    name="Understand the Issue",
                    response=ResponseGuideline(
                        template_he="אנא ספר לי יותר על מה שקרה, כדי שאוכל לעזור בצורה הטובה ביותר.",
                        template_en="Please tell me more about what happened so I can help in the best way.",
                    ),
                    expects_user_input=True,
                    next_step_on_success="acknowledge_issue",
                ),
                FlowStep(
                    step_id="acknowledge_issue",
                    step_type=StepType.ACKNOWLEDGMENT,
                    name="Acknowledge the Issue",
                    response=ResponseGuideline(
                        template_he="הבנתי. {issue_summary}. אני מבין למה זה מתסכל.",
                        template_en="I understand. {issue_summary}. I can see why this is frustrating.",
                        variables=["issue_summary"],
                    ),
                    next_step_on_success="offer_solution",
                ),
                FlowStep(
                    step_id="offer_solution",
                    step_type=StepType.INFORMATION,
                    name="Offer Solution",
                    response=ResponseGuideline(
                        template_he="הנה מה שאני יכול לעשות:\n{solution_options}",
                        template_en="Here's what I can do:\n{solution_options}",
                        variables=["solution_options"],
                    ),
                    next_step_on_success="check_satisfaction",
                ),
                FlowStep(
                    step_id="check_satisfaction",
                    step_type=StepType.CONFIRMATION,
                    name="Check Satisfaction",
                    response=ResponseGuideline(
                        template_he="האם זה עוזר? או שתרצה לדבר עם נציג אנושי?",
                        template_en="Does this help? Or would you prefer to speak with a human agent?",
                    ),
                    expects_user_input=True,
                    next_step_on_success="resolved",
                    next_step_on_failure="escalate",
                ),
                FlowStep(
                    step_id="escalate",
                    step_type=StepType.ESCALATION,
                    name="Escalate to Human",
                    action_before="escalate_to_human",
                    response=ResponseGuideline(
                        template_he="אני מעביר אותך לנציג שירות שיוכל לעזור. תודה על הסבלנות.",
                        template_en="I'm transferring you to a service agent who can help. Thank you for your patience.",
                    ),
                ),
                FlowStep(
                    step_id="resolved",
                    step_type=StepType.CLOSING,
                    name="Close Resolved",
                    response=ResponseGuideline(
                        template_he="שמח שיכולתי לעזור. אם יש עוד משהו, אני כאן.",
                        template_en="Glad I could help. If there's anything else, I'm here.",
                    ),
                ),
            ],
        )

    def _create_insights_template(self) -> ConversationTemplate:
        """Create template for insights delivery."""
        return ConversationTemplate(
            template_id="flow-insights",
            name="Insights Delivery Flow",
            applies_to_intents=["insights.view", "analytics.spending"],
            entry_step_id="intro",
            steps=[
                FlowStep(
                    step_id="intro",
                    step_type=StepType.ACKNOWLEDGMENT,
                    name="Introduce Insights",
                    response=ResponseGuideline(
                        template_he="הנה כמה תובנות על החשבון שלך:",
                        template_en="Here are some insights about your account:",
                    ),
                    delay_ms=500,
                    next_step_on_success="present_insights",
                ),
                FlowStep(
                    step_id="present_insights",
                    step_type=StepType.INSIGHT,
                    name="Present Insights",
                    response=ResponseGuideline(
                        template_he="{insight_content}",
                        template_en="{insight_content}",
                        variables=["insight_content"],
                    ),
                    next_step_on_success="offer_recommendation",
                ),
                FlowStep(
                    step_id="offer_recommendation",
                    step_type=StepType.INFORMATION,
                    name="Offer Recommendation",
                    condition=StepCondition.CUSTOM,
                    condition_params={"has_recommendation": True},
                    response=ResponseGuideline(
                        template_he="💡 המלצה: {recommendation}",
                        template_en="💡 Recommendation: {recommendation}",
                        variables=["recommendation"],
                    ),
                    is_optional=True,
                    next_step_on_success="ask_action",
                ),
                FlowStep(
                    step_id="ask_action",
                    step_type=StepType.CONFIRMATION,
                    name="Ask to Take Action",
                    response=ResponseGuideline(
                        template_he="תרצה שאעזור לך לבצע את ההמלצה?",
                        template_en="Would you like me to help you implement this recommendation?",
                    ),
                    expects_user_input=True,
                    is_optional=True,
                    next_step_on_success="execute_recommendation",
                ),
                FlowStep(
                    step_id="execute_recommendation",
                    step_type=StepType.ACTION,
                    name="Execute Recommendation",
                    action_before="execute_insight_recommendation",
                    response=ResponseGuideline(
                        template_he="מבצע...",
                        template_en="Processing...",
                    ),
                ),
            ],
        )
