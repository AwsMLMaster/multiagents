"""
Base Agent class for Digital Bank Chatbot.

Provides common functionality for all specialized agents.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Response from agent execution."""
    content: str
    tools_used: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None
    needs_followup: bool = False
    followup_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    description: str
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    max_tokens: int = 2048
    temperature: float = 0.1
    tools: List[str] = field(default_factory=list)
    system_prompt: Optional[str] = None


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the agent.

        Args:
            config: Optional agent configuration.
        """
        self.config = config or self._default_config()
        self._bedrock_client = None
        self._tools = {}

    @abstractmethod
    def _default_config(self) -> AgentConfig:
        """Return default configuration for this agent."""
        pass

    @abstractmethod
    async def execute(
        self,
        query: str,
        intent: Dict[str, Any],
        **kwargs
    ) -> AgentResponse:
        """
        Execute the agent's main task.

        Args:
            query: User query.
            intent: Intent classification result.
            **kwargs: Additional context.

        Returns:
            AgentResponse with results.
        """
        pass

    @property
    def bedrock_client(self):
        """Lazy initialization of Bedrock client."""
        if self._bedrock_client is None:
            from ..integrations.bedrock_client import create_bedrock_client
            self._bedrock_client = create_bedrock_client(
                model_id=self.config.model_id
            )
        return self._bedrock_client

    def _format_history(
        self,
        history: Optional[List[BaseMessage]]
    ) -> List[Dict[str, str]]:
        """Format conversation history for LLM."""
        if not history:
            return []

        formatted = []
        for msg in history[-10:]:  # Last 10 messages
            role = "user" if msg.type == "human" else "assistant"
            formatted.append({"role": role, "content": msg.content})

        return formatted

    def _build_error_response(
        self,
        error: str,
        hebrew_message: str = "מצטער, אירעה שגיאה בעיבוד הבקשה."
    ) -> AgentResponse:
        """Build error response."""
        logger.error(f"Agent {self.config.name} error: {error}")
        return AgentResponse(
            content=hebrew_message,
            success=False,
            error=error
        )


# Hebrew system prompts for agents
AGENT_SYSTEM_PROMPTS = {
    "rag": """אתה עוזר בנקאי וירטואלי מומחה במתן מידע כללי על שירותי הבנק.

תפקידך:
- לענות על שאלות כלליות לגבי מוצרים ושירותים
- להסביר מדיניות ונהלים
- לספק מידע על שעות פעילות, סניפים ושירותים

הנחיות:
- ענה בעברית ברורה ומובנת
- אם אינך בטוח, אמור זאת
- הפנה לשירות לקוחות בנושאים מורכבים
- אל תמציא מידע""",

    "account": """אתה עוזר בנקאי וירטואלי המתמחה בניהול חשבונות.

תפקידך:
- להציג יתרות חשבון
- להציג תנועות ופעולות
- לספק מידע על פרטי חשבון

הנחיות:
- הצג מידע מדויק מהמערכת
- הסתר מידע רגיש כמו מספרי כרטיס מלאים
- הצע עזרה נוספת אם נדרש
- אל תבצע פעולות ללא אישור מפורש""",

    "transaction": """אתה עוזר בנקאי וירטואלי המתמחה בביצוע פעולות פיננסיות.

תפקידך:
- לסייע בהעברות כספים
- לסייע בתשלום חשבונות
- ליצור ולנהל הוראות קבע

הנחיות חשובות:
- וודא את כל הפרטים לפני ביצוע פעולה
- בקש אישור מפורש לכל עסקה
- הזהר מטעויות בסכומים ומספרי חשבון
- הצג סיכום ברור לפני אישור סופי
- אם משהו לא ברור, שאל שוב""",

    "loan": """אתה עוזר בנקאי וירטואלי המתמחה בהלוואות ואשראי.

תפקידך:
- להציג מצב הלוואות
- לחשב החזרים חודשיים
- לספק מידע על אפשרויות מימון

הנחיות:
- הסבר תנאים בצורה ברורה
- הדגש שחישובים הם הערכות בלבד
- הפנה ליועץ לבקשות מורכבות
- היה שקוף לגבי ריביות ועמלות""",

    "support": """אתה עוזר בנקאי וירטואלי לתמיכה ושירות לקוחות.

תפקידך:
- לטפל בפניות ותלונות
- להעביר לנציג אנושי בעת הצורך
- לספק מידע על סטטוס פניות

הנחיות:
- היה אמפתי ומתחשב
- קבל משוב ברצינות
- הציע פתרונות מעשיים
- אל תבטיח דברים שאינך יכול לקיים""",

    "analytics": """אתה עוזר בנקאי וירטואלי לניתוח פיננסי.

תפקידך:
- לנתח דפוסי הוצאות
- לספק תובנות פיננסיות
- לסייע בתכנון תקציב

הנחיות:
- הצג נתונים בצורה ברורה וויזואלית
- הסבר מגמות ודפוסים
- הצע המלצות כלליות בלבד
- הדגש שזה אינו ייעוץ פיננסי מקצועי"""
}
