"""
Conversation Guidelines

Product team-defined guidelines for how conversations should be conducted.
These guidelines control tone, length, structure, and content of responses.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


class GuidelineCategory(Enum):
    """Categories of conversation guidelines."""
    TONE = "tone"
    LENGTH = "length"
    STRUCTURE = "structure"
    CONTENT = "content"
    TIMING = "timing"
    PERSONALIZATION = "personalization"
    ESCALATION = "escalation"
    COMPLIANCE = "compliance"


class ToneType(Enum):
    """Types of conversational tone."""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    EMPATHETIC = "empathetic"
    URGENT = "urgent"
    CELEBRATORY = "celebratory"
    SUPPORTIVE = "supportive"
    EDUCATIONAL = "educational"


class ResponseLength(Enum):
    """Response length guidelines."""
    CONCISE = "concise"      # 1-2 sentences
    STANDARD = "standard"    # 2-4 sentences
    DETAILED = "detailed"    # 4-6 sentences
    COMPREHENSIVE = "comprehensive"  # Full explanation


@dataclass
class ToneGuideline:
    """Guideline for conversational tone."""
    guideline_id: str
    name: str
    tone_type: ToneType

    # When to apply
    applies_to_intents: List[str] = field(default_factory=list)
    applies_to_contexts: List[str] = field(default_factory=list)  # e.g., "complaint", "error"

    # Tone characteristics
    formality_level: int = 3  # 1-5, 1=casual, 5=formal
    empathy_level: int = 3    # 1-5
    energy_level: int = 3     # 1-5, 1=calm, 5=enthusiastic

    # Language patterns
    use_customer_name: bool = True
    use_emoji: bool = False
    use_exclamations: bool = False

    # Example phrases (Hebrew)
    greeting_phrases_he: List[str] = field(default_factory=list)
    acknowledgment_phrases_he: List[str] = field(default_factory=list)
    closing_phrases_he: List[str] = field(default_factory=list)

    # Example phrases (English)
    greeting_phrases_en: List[str] = field(default_factory=list)
    acknowledgment_phrases_en: List[str] = field(default_factory=list)
    closing_phrases_en: List[str] = field(default_factory=list)

    # Avoid patterns
    avoid_phrases: List[str] = field(default_factory=list)


@dataclass
class ResponseLengthGuideline:
    """Guideline for response length."""
    guideline_id: str
    name: str
    length: ResponseLength

    # When to apply
    applies_to_intents: List[str] = field(default_factory=list)
    applies_to_complexity: str = "medium"  # low, medium, high

    # Length parameters
    min_words: int = 10
    max_words: int = 100
    min_sentences: int = 1
    max_sentences: int = 5

    # Bullet points
    use_bullet_points: bool = False
    max_bullet_points: int = 5

    # Progressive disclosure
    enable_progressive_disclosure: bool = False  # "More info" buttons
    initial_display_sentences: int = 2


@dataclass
class StructureGuideline:
    """Guideline for response structure."""
    guideline_id: str
    name: str

    # When to apply
    applies_to_intents: List[str] = field(default_factory=list)

    # Structure elements (in order)
    include_greeting: bool = False
    include_acknowledgment: bool = True
    include_main_content: bool = True
    include_next_steps: bool = True
    include_closing: bool = False
    include_call_to_action: bool = False

    # Formatting
    use_headers: bool = False
    use_numbered_steps: bool = False
    use_confirmation_summary: bool = False


@dataclass
class ContentGuideline:
    """Guideline for response content."""
    guideline_id: str
    name: str

    # When to apply
    applies_to_intents: List[str] = field(default_factory=list)

    # Required content
    required_disclaimers: List[str] = field(default_factory=list)
    required_warnings: List[str] = field(default_factory=list)

    # Content rules
    always_confirm_amounts: bool = True
    always_show_fees: bool = True
    always_explain_consequences: bool = True
    show_alternatives: bool = False

    # Personalization
    reference_past_interactions: bool = True
    reference_account_history: bool = True
    adapt_to_user_expertise: bool = True

    # Prohibited content
    prohibited_topics: List[str] = field(default_factory=list)
    prohibited_recommendations: List[str] = field(default_factory=list)


@dataclass
class TimingGuideline:
    """Guideline for timing and pacing."""
    guideline_id: str
    name: str

    # Response timing
    expected_response_time_ms: int = 2000  # Target response time
    max_response_time_ms: int = 5000       # Show typing indicator after this

    # Pacing
    pause_between_messages_ms: int = 500   # For multi-message responses
    typing_indicator_enabled: bool = True

    # Proactive timing
    proactive_insight_delay_ms: int = 1000  # Wait before showing unsolicited insights
    upsell_delay_ms: int = 2000            # Wait before suggesting offerings

    # Session timing
    idle_warning_seconds: int = 300         # Warn after 5 min idle
    session_timeout_seconds: int = 600      # End session after 10 min idle


@dataclass
class EscalationGuideline:
    """Guideline for escalation to human agents."""
    guideline_id: str
    name: str

    # Triggers for escalation offer
    offer_escalation_on_intents: List[str] = field(default_factory=list)
    offer_escalation_after_failures: int = 2  # Consecutive failures
    offer_escalation_on_sentiment: str = "negative"  # negative, very_negative

    # Automatic escalation
    auto_escalate_on_intents: List[str] = field(default_factory=list)
    auto_escalate_keywords: List[str] = field(default_factory=list)

    # Escalation messaging
    escalation_offer_message_he: str = "האם תרצה לדבר עם נציג?"
    escalation_offer_message_en: str = "Would you like to speak with an agent?"

    # Context handoff
    include_conversation_summary: bool = True
    include_customer_sentiment: bool = True
    include_attempted_actions: bool = True


@dataclass
class ConversationGuidelines:
    """
    Complete set of conversation guidelines.

    This is the main configuration object that product teams use to
    define how conversations should be conducted.
    """
    guidelines_id: str
    name: str
    description: str = ""
    version: str = "1.0"

    # Guidelines by category
    tone_guidelines: List[ToneGuideline] = field(default_factory=list)
    length_guidelines: List[ResponseLengthGuideline] = field(default_factory=list)
    structure_guidelines: List[StructureGuideline] = field(default_factory=list)
    content_guidelines: List[ContentGuideline] = field(default_factory=list)
    timing_guidelines: List[TimingGuideline] = field(default_factory=list)
    escalation_guidelines: List[EscalationGuideline] = field(default_factory=list)

    # Global settings
    default_language: str = "he"
    enable_bilingual_responses: bool = True

    # Quality thresholds
    min_quality_score: float = 0.7
    require_compliance_check: bool = True

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    is_active: bool = True


def create_default_guidelines() -> ConversationGuidelines:
    """Create default conversation guidelines for banking chatbot."""
    return ConversationGuidelines(
        guidelines_id="default-banking-v1",
        name="Default Banking Guidelines",
        description="Standard guidelines for digital bank chatbot conversations",
        version="1.0",
        tone_guidelines=[
            ToneGuideline(
                guideline_id="tone-default",
                name="Default Professional Tone",
                tone_type=ToneType.PROFESSIONAL,
                formality_level=4,
                empathy_level=3,
                energy_level=3,
                use_customer_name=True,
                greeting_phrases_he=["שלום", "היי", "בוקר טוב", "ערב טוב"],
                acknowledgment_phrases_he=["הבנתי", "ברור", "בסדר"],
                closing_phrases_he=["אשמח לעזור בכל שאלה נוספת", "אני כאן בשבילך"],
                greeting_phrases_en=["Hello", "Hi", "Good morning"],
                acknowledgment_phrases_en=["I understand", "Got it", "Sure"],
                closing_phrases_en=["Happy to help with anything else", "I'm here for you"],
                avoid_phrases=["לצערי", "אי אפשר", "אין מה לעשות"],
            ),
            ToneGuideline(
                guideline_id="tone-empathetic",
                name="Empathetic Tone for Complaints",
                tone_type=ToneType.EMPATHETIC,
                applies_to_intents=["support.complaint"],
                applies_to_contexts=["complaint", "frustration"],
                formality_level=3,
                empathy_level=5,
                energy_level=2,
                use_customer_name=True,
                acknowledgment_phrases_he=[
                    "אני מבין שזה מתסכל",
                    "אני מצטער לשמוע על חוויה זו",
                    "אני כאן כדי לעזור לפתור את זה",
                ],
                acknowledgment_phrases_en=[
                    "I understand this is frustrating",
                    "I'm sorry to hear about this experience",
                    "I'm here to help resolve this",
                ],
            ),
            ToneGuideline(
                guideline_id="tone-celebratory",
                name="Celebratory Tone for Success",
                tone_type=ToneType.CELEBRATORY,
                applies_to_contexts=["goal_achieved", "savings_milestone"],
                formality_level=2,
                empathy_level=3,
                energy_level=5,
                use_exclamations=True,
                acknowledgment_phrases_he=[
                    "מעולה!",
                    "כל הכבוד!",
                    "הגעת ליעד!",
                ],
                acknowledgment_phrases_en=[
                    "Excellent!",
                    "Well done!",
                    "You reached your goal!",
                ],
            ),
        ],
        length_guidelines=[
            ResponseLengthGuideline(
                guideline_id="length-default",
                name="Standard Response Length",
                length=ResponseLength.STANDARD,
                min_words=15,
                max_words=80,
                min_sentences=2,
                max_sentences=4,
            ),
            ResponseLengthGuideline(
                guideline_id="length-quick-answers",
                name="Concise for Simple Queries",
                length=ResponseLength.CONCISE,
                applies_to_intents=["account.balance", "general.greeting"],
                min_words=5,
                max_words=30,
                min_sentences=1,
                max_sentences=2,
            ),
            ResponseLengthGuideline(
                guideline_id="length-detailed-explanations",
                name="Detailed for Complex Topics",
                length=ResponseLength.DETAILED,
                applies_to_intents=["loan.calculator", "rag.products"],
                applies_to_complexity="high",
                min_words=50,
                max_words=200,
                min_sentences=4,
                max_sentences=8,
                use_bullet_points=True,
                max_bullet_points=5,
            ),
        ],
        structure_guidelines=[
            StructureGuideline(
                guideline_id="structure-transactional",
                name="Structure for Transactions",
                applies_to_intents=["transaction.transfer", "transaction.bill_payment"],
                include_acknowledgment=True,
                include_main_content=True,
                include_next_steps=True,
                use_confirmation_summary=True,
            ),
            StructureGuideline(
                guideline_id="structure-informational",
                name="Structure for Information",
                applies_to_intents=["rag.general", "rag.products"],
                include_main_content=True,
                use_headers=True,
                use_bullet_points=True,
            ),
        ],
        content_guidelines=[
            ContentGuideline(
                guideline_id="content-financial",
                name="Financial Content Rules",
                applies_to_intents=[
                    "transaction.transfer",
                    "loan.application",
                    "offerings.consent",
                ],
                required_disclaimers=[
                    "כפוף לאישור הבנק",
                    "הריבית עשויה להשתנות",
                ],
                always_confirm_amounts=True,
                always_show_fees=True,
                always_explain_consequences=True,
                prohibited_recommendations=[
                    "specific_stock_tips",
                    "guaranteed_returns",
                ],
            ),
        ],
        timing_guidelines=[
            TimingGuideline(
                guideline_id="timing-default",
                name="Default Timing",
                expected_response_time_ms=2000,
                max_response_time_ms=5000,
                pause_between_messages_ms=500,
                proactive_insight_delay_ms=1500,
                upsell_delay_ms=3000,
            ),
        ],
        escalation_guidelines=[
            EscalationGuideline(
                guideline_id="escalation-default",
                name="Default Escalation Rules",
                offer_escalation_on_intents=["support.complaint"],
                offer_escalation_after_failures=2,
                offer_escalation_on_sentiment="negative",
                auto_escalate_on_intents=["support.human_agent"],
                auto_escalate_keywords=["מנהל", "תלונה רשמית", "עורך דין"],
                include_conversation_summary=True,
                include_customer_sentiment=True,
            ),
        ],
    )
