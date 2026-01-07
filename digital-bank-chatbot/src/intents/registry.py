"""
Intent Registry for Digital Bank Chatbot.

This module defines all supported intents with their configurations,
including required parameters, target agents, and authentication requirements.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class IntentCategory(str, Enum):
    """High-level intent categories."""
    ACCOUNT = "account"
    TRANSACTION = "transaction"
    LOAN = "loan"
    RAG = "rag"
    SUPPORT = "support"
    ANALYTICS = "analytics"
    OFFERINGS = "offerings"
    GENERAL = "general"


@dataclass
class IntentDefinition:
    """Definition of a single intent."""
    id: str
    category: IntentCategory
    description: str
    target_agent: str
    requires_auth: bool = False
    requires_mfa: bool = False
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    examples_he: List[str] = field(default_factory=list)
    examples_en: List[str] = field(default_factory=list)
    enabled: bool = True
    feature_flag: Optional[str] = None
    max_confidence_threshold: float = 0.95
    min_confidence_threshold: float = 0.60


# ============================================================================
# Intent Registry
# ============================================================================

INTENT_REGISTRY: Dict[str, IntentDefinition] = {
    # =========================================================================
    # Account Intents
    # =========================================================================
    "account.balance": IntentDefinition(
        id="account.balance",
        category=IntentCategory.ACCOUNT,
        description="Get account balance",
        target_agent="account_agent",
        requires_auth=True,
        tools=["get_balance"],
        required_params=["account_id"],
        examples_he=[
            "מה היתרה שלי?",
            "כמה כסף יש לי בחשבון?",
            "מה היתרה בחשבון העו\"ש?",
            "הצג יתרה",
            "כמה כסף נשאר לי?",
            "מה המצב בחשבון?",
        ],
        examples_en=[
            "What's my balance?",
            "How much money do I have?",
            "Show my account balance",
            "Check balance",
        ],
    ),

    "account.statement": IntentDefinition(
        id="account.statement",
        category=IntentCategory.ACCOUNT,
        description="Get account statement/transactions",
        target_agent="account_agent",
        requires_auth=True,
        tools=["get_statement", "get_transactions"],
        required_params=["account_id"],
        optional_params=["from_date", "to_date", "limit"],
        examples_he=[
            "הצג לי את התנועות האחרונות",
            "דוח חשבון",
            "מה התנועות בחשבון?",
            "הצג היסטוריית תנועות",
            "תראה לי את הפעולות האחרונות",
            "מה הוצאתי החודש?",
        ],
        examples_en=[
            "Show recent transactions",
            "Account statement",
            "Transaction history",
            "What were my recent expenses?",
        ],
    ),

    "account.details": IntentDefinition(
        id="account.details",
        category=IntentCategory.ACCOUNT,
        description="Get account details",
        target_agent="account_agent",
        requires_auth=True,
        tools=["get_account_details"],
        required_params=["account_id"],
        examples_he=[
            "מה פרטי החשבון שלי?",
            "הצג פרטי חשבון",
            "מה מספר החשבון שלי?",
        ],
        examples_en=[
            "What are my account details?",
            "Show account information",
        ],
    ),

    "account.list": IntentDefinition(
        id="account.list",
        category=IntentCategory.ACCOUNT,
        description="List all accounts",
        target_agent="account_agent",
        requires_auth=True,
        tools=["list_accounts"],
        examples_he=[
            "אילו חשבונות יש לי?",
            "הצג את כל החשבונות",
            "רשימת חשבונות",
        ],
        examples_en=[
            "What accounts do I have?",
            "List my accounts",
            "Show all accounts",
        ],
    ),

    # =========================================================================
    # Transaction Intents
    # =========================================================================
    "transaction.transfer": IntentDefinition(
        id="transaction.transfer",
        category=IntentCategory.TRANSACTION,
        description="Transfer funds between accounts",
        target_agent="transaction_agent",
        requires_auth=True,
        requires_mfa=True,
        tools=["initiate_transfer", "confirm_transfer"],
        required_params=["from_account", "to_account", "amount"],
        optional_params=["currency", "description", "execution_date"],
        examples_he=[
            "העבר 1000 שקל לחשבון 12345",
            "רוצה לבצע העברה",
            "תעביר כסף לאבא",
            "העברה בנקאית",
            "לשלוח כסף לחשבון אחר",
            "העבר 500 ש\"ח",
        ],
        examples_en=[
            "Transfer 1000 NIS to account 12345",
            "I want to make a transfer",
            "Send money to another account",
        ],
    ),

    "transaction.bill_payment": IntentDefinition(
        id="transaction.bill_payment",
        category=IntentCategory.TRANSACTION,
        description="Pay bills",
        target_agent="transaction_agent",
        requires_auth=True,
        requires_mfa=True,
        tools=["pay_bill", "get_billers"],
        required_params=["biller_id", "amount"],
        optional_params=["from_account", "reference"],
        examples_he=[
            "שלם חשבון חשמל",
            "תשלום ארנונה",
            "לשלם את חשבון הגז",
            "תשלום חשבונות",
            "שלם את חשבון המים",
        ],
        examples_en=[
            "Pay electricity bill",
            "Pay municipal tax",
            "Bill payment",
        ],
    ),

    "transaction.status": IntentDefinition(
        id="transaction.status",
        category=IntentCategory.TRANSACTION,
        description="Check transaction status",
        target_agent="transaction_agent",
        requires_auth=True,
        tools=["get_transfer_status"],
        required_params=["transaction_id"],
        examples_he=[
            "מה מצב ההעברה?",
            "האם ההעברה בוצעה?",
            "בדוק סטטוס תשלום",
        ],
        examples_en=[
            "What's the transfer status?",
            "Check payment status",
        ],
    ),

    "transaction.standing_order": IntentDefinition(
        id="transaction.standing_order",
        category=IntentCategory.TRANSACTION,
        description="Manage standing orders",
        target_agent="transaction_agent",
        requires_auth=True,
        requires_mfa=True,
        tools=["create_standing_order", "list_standing_orders", "cancel_standing_order"],
        optional_params=["to_account", "amount", "frequency"],
        examples_he=[
            "צור הוראת קבע",
            "הצג הוראות קבע",
            "בטל הוראת קבע",
            "שנה הוראת קבע",
        ],
        examples_en=[
            "Create standing order",
            "Show standing orders",
            "Cancel standing order",
        ],
    ),

    # =========================================================================
    # Loan Intents
    # =========================================================================
    "loan.status": IntentDefinition(
        id="loan.status",
        category=IntentCategory.LOAN,
        description="Get loan status and details",
        target_agent="loan_agent",
        requires_auth=True,
        tools=["get_loan_details", "get_loans"],
        optional_params=["loan_id"],
        examples_he=[
            "מה המצב של ההלוואה שלי?",
            "כמה נשאר לשלם?",
            "פרטי הלוואה",
            "מתי התשלום הבא?",
            "כמה חוב נשאר?",
        ],
        examples_en=[
            "What's my loan status?",
            "How much left to pay?",
            "Loan details",
            "When is next payment?",
        ],
    ),

    "loan.calculator": IntentDefinition(
        id="loan.calculator",
        category=IntentCategory.LOAN,
        description="Calculate loan EMI",
        target_agent="loan_agent",
        requires_auth=False,
        tools=["calculate_emi"],
        required_params=["principal", "rate", "tenure"],
        examples_he=[
            "חשב החזר חודשי להלוואה של 100000",
            "כמה אשלם על הלוואה?",
            "מחשבון הלוואות",
            "חישוב משכנתא",
            "סימולטור הלוואה",
        ],
        examples_en=[
            "Calculate monthly payment for 100000 loan",
            "Loan calculator",
            "EMI calculator",
        ],
    ),

    "loan.application": IntentDefinition(
        id="loan.application",
        category=IntentCategory.LOAN,
        description="Apply for a loan",
        target_agent="loan_agent",
        requires_auth=True,
        tools=["check_eligibility", "start_application"],
        optional_params=["loan_type", "amount", "tenure"],
        examples_he=[
            "רוצה לקחת הלוואה",
            "בקשה להלוואה",
            "איך מגישים בקשה להלוואה?",
            "האם אני זכאי להלוואה?",
        ],
        examples_en=[
            "I want to take a loan",
            "Loan application",
            "Am I eligible for a loan?",
        ],
    ),

    "loan.payment": IntentDefinition(
        id="loan.payment",
        category=IntentCategory.LOAN,
        description="Make loan payment",
        target_agent="loan_agent",
        requires_auth=True,
        requires_mfa=True,
        tools=["make_loan_payment"],
        required_params=["loan_id", "amount"],
        examples_he=[
            "רוצה לשלם תשלום הלוואה",
            "תשלום מוקדם להלוואה",
            "לסגור הלוואה",
        ],
        examples_en=[
            "Make loan payment",
            "Early loan payment",
            "Close loan",
        ],
    ),

    # =========================================================================
    # RAG / General Knowledge Intents
    # =========================================================================
    "rag.general": IntentDefinition(
        id="rag.general",
        category=IntentCategory.RAG,
        description="General banking knowledge questions",
        target_agent="rag_agent",
        requires_auth=False,
        tools=["knowledge_base_query"],
        examples_he=[
            "מה שעות הפעילות?",
            "איך פותחים חשבון?",
            "מה התנאים לפתיחת חשבון?",
            "איפה הסניף הקרוב?",
            "מה מספר הטלפון של השירות?",
        ],
        examples_en=[
            "What are the operating hours?",
            "How to open an account?",
            "Where is the nearest branch?",
        ],
    ),

    "rag.products": IntentDefinition(
        id="rag.products",
        category=IntentCategory.RAG,
        description="Product information queries",
        target_agent="rag_agent",
        requires_auth=False,
        tools=["product_search", "knowledge_base_query"],
        examples_he=[
            "ספר לי על חשבון חיסכון",
            "מה הריביות על פיקדונות?",
            "אילו כרטיסי אשראי יש?",
            "מה ההבדל בין חשבון רגיל לפרימיום?",
            "תנאי משכנתא",
        ],
        examples_en=[
            "Tell me about savings account",
            "Deposit interest rates",
            "What credit cards are available?",
        ],
    ),

    "rag.procedures": IntentDefinition(
        id="rag.procedures",
        category=IntentCategory.RAG,
        description="Procedure and how-to queries",
        target_agent="rag_agent",
        requires_auth=False,
        tools=["knowledge_base_query"],
        examples_he=[
            "איך מחליפים סיסמה?",
            "איך מבטלים כרטיס?",
            "מה עושים אם שכחתי סיסמה?",
            "איך מעדכנים פרטים?",
        ],
        examples_en=[
            "How to change password?",
            "How to cancel a card?",
            "What to do if I forgot password?",
        ],
    ),

    # =========================================================================
    # Support Intents
    # =========================================================================
    "support.complaint": IntentDefinition(
        id="support.complaint",
        category=IntentCategory.SUPPORT,
        description="File a complaint",
        target_agent="support_agent",
        requires_auth=True,
        tools=["create_ticket", "get_ticket_status"],
        examples_he=[
            "יש לי תלונה",
            "רוצה להגיש תלונה",
            "שירות גרוע",
            "לא מרוצה מהשירות",
        ],
        examples_en=[
            "I have a complaint",
            "File a complaint",
            "Bad service",
        ],
    ),

    "support.human_agent": IntentDefinition(
        id="support.human_agent",
        category=IntentCategory.SUPPORT,
        description="Request human agent",
        target_agent="support_agent",
        requires_auth=False,
        tools=["escalate_to_human"],
        examples_he=[
            "רוצה לדבר עם נציג",
            "תעביר אותי לנציג אנושי",
            "אני צריך עזרה אנושית",
            "נציג שירות",
        ],
        examples_en=[
            "Want to speak to agent",
            "Transfer to human",
            "Customer service representative",
        ],
    ),

    "support.feedback": IntentDefinition(
        id="support.feedback",
        category=IntentCategory.SUPPORT,
        description="Provide feedback",
        target_agent="support_agent",
        requires_auth=False,
        tools=["submit_feedback"],
        examples_he=[
            "יש לי הצעה",
            "רוצה לתת פידבק",
            "משוב על השירות",
        ],
        examples_en=[
            "I have a suggestion",
            "Want to give feedback",
        ],
    ),

    # =========================================================================
    # Analytics Intents
    # =========================================================================
    "analytics.spending": IntentDefinition(
        id="analytics.spending",
        category=IntentCategory.ANALYTICS,
        description="Spending analysis",
        target_agent="analytics_agent",
        requires_auth=True,
        tools=["analyze_spending", "get_insights"],
        optional_params=["period", "category"],
        examples_he=[
            "על מה אני מוציא הכי הרבה?",
            "ניתוח הוצאות",
            "לאן הולך הכסף שלי?",
            "סיכום הוצאות חודשי",
        ],
        examples_en=[
            "What do I spend most on?",
            "Spending analysis",
            "Where does my money go?",
        ],
    ),

    "analytics.budget": IntentDefinition(
        id="analytics.budget",
        category=IntentCategory.ANALYTICS,
        description="Budget planning and tracking",
        target_agent="analytics_agent",
        requires_auth=True,
        tools=["get_budget", "set_budget", "budget_alerts"],
        optional_params=["category", "amount", "period"],
        examples_he=[
            "צור לי תקציב",
            "כמה חרגתי מהתקציב?",
            "תכנון תקציב",
            "התראות על חריגה",
        ],
        examples_en=[
            "Create a budget",
            "How much over budget?",
            "Budget planning",
        ],
    ),

    # =========================================================================
    # Offerings Intents
    # =========================================================================
    "offerings.view": IntentDefinition(
        id="offerings.view",
        category=IntentCategory.OFFERINGS,
        description="View available offerings for customer",
        target_agent="offerings_agent",
        requires_auth=True,
        tools=["get_matched_offerings", "get_offering_details"],
        examples_he=[
            "מה ההצעות שיש לי?",
            "יש הצעות מיוחדות בשבילי?",
            "מה אתם מציעים לי?",
            "הצג הטבות",
            "יש לכם מבצעים?",
            "אילו מוצרים מתאימים לי?",
        ],
        examples_en=[
            "What offers do you have for me?",
            "Any special offers?",
            "Show me promotions",
            "What products suit me?",
        ],
    ),

    "offerings.interest": IntentDefinition(
        id="offerings.interest",
        category=IntentCategory.OFFERINGS,
        description="Customer expresses interest in an offering",
        target_agent="offerings_agent",
        requires_auth=True,
        tools=["record_interest", "get_offering_details"],
        required_params=["offering_id"],
        examples_he=[
            "אני מעוניין בהצעה הזו",
            "ספר לי עוד על ההצעה",
            "אשמח לשמוע פרטים",
            "זה מעניין אותי",
            "תן לי עוד מידע",
        ],
        examples_en=[
            "I'm interested in this offer",
            "Tell me more about the offer",
            "I'd like more details",
            "This interests me",
        ],
    ),

    "offerings.consent": IntentDefinition(
        id="offerings.consent",
        category=IntentCategory.OFFERINGS,
        description="Customer consents to proceed with offering",
        target_agent="offerings_agent",
        requires_auth=True,
        requires_mfa=False,
        tools=["record_consent", "initiate_fulfillment"],
        required_params=["offering_id"],
        optional_params=["amount", "term_months"],
        examples_he=[
            "אני רוצה להתקדם עם ההצעה",
            "אני מאשר",
            "בואו נעשה את זה",
            "אני מסכים",
            "כן, אני רוצה",
            "תמשיכו עם הבקשה",
        ],
        examples_en=[
            "I want to proceed with the offer",
            "I approve",
            "Let's do it",
            "I agree",
            "Yes, I want this",
        ],
    ),

    "offerings.decline": IntentDefinition(
        id="offerings.decline",
        category=IntentCategory.OFFERINGS,
        description="Customer declines an offering",
        target_agent="offerings_agent",
        requires_auth=True,
        tools=["record_decline"],
        required_params=["offering_id"],
        optional_params=["reason"],
        examples_he=[
            "לא מתאים לי",
            "לא תודה",
            "לא מעוניין",
            "אולי בפעם אחרת",
            "תודה אבל לא",
        ],
        examples_en=[
            "Not for me",
            "No thanks",
            "Not interested",
            "Maybe another time",
            "Thanks but no",
        ],
    ),

    "offerings.status": IntentDefinition(
        id="offerings.status",
        category=IntentCategory.OFFERINGS,
        description="Check status of offering request",
        target_agent="offerings_agent",
        requires_auth=True,
        tools=["get_consent_status"],
        optional_params=["consent_id", "offering_id"],
        examples_he=[
            "מה המצב של הבקשה שלי?",
            "האם יצרו איתי קשר?",
            "מתי יחזרו אליי?",
            "סטטוס הבקשה",
        ],
        examples_en=[
            "What's the status of my request?",
            "Did anyone contact me?",
            "When will they call back?",
            "Request status",
        ],
    ),

    "offerings.savings": IntentDefinition(
        id="offerings.savings",
        category=IntentCategory.OFFERINGS,
        description="Open savings account from offering",
        target_agent="offerings_agent",
        requires_auth=True,
        requires_mfa=True,
        tools=["open_savings_account", "transfer_to_savings"],
        required_params=["amount"],
        optional_params=["term_months", "account_type"],
        examples_he=[
            "רוצה לפתוח חיסכון",
            "להעביר לחיסכון",
            "לפתוח פיקדון",
            "לחסוך את הכסף",
            "להתחיל לחסוך",
            "תעביר 10000 לחיסכון",
        ],
        examples_en=[
            "Want to open savings",
            "Transfer to savings",
            "Open a deposit",
            "Save the money",
            "Start saving",
        ],
    ),

    # =========================================================================
    # General Intents
    # =========================================================================
    "general.greeting": IntentDefinition(
        id="general.greeting",
        category=IntentCategory.GENERAL,
        description="Greeting",
        target_agent="rag_agent",
        requires_auth=False,
        examples_he=[
            "שלום",
            "היי",
            "בוקר טוב",
            "ערב טוב",
        ],
        examples_en=[
            "Hello",
            "Hi",
            "Good morning",
        ],
    ),

    "general.help": IntentDefinition(
        id="general.help",
        category=IntentCategory.GENERAL,
        description="Help request",
        target_agent="rag_agent",
        requires_auth=False,
        examples_he=[
            "עזרה",
            "מה אתה יכול לעשות?",
            "איך אתה יכול לעזור לי?",
            "מה האפשרויות?",
        ],
        examples_en=[
            "Help",
            "What can you do?",
            "How can you help me?",
        ],
    ),

    "general.goodbye": IntentDefinition(
        id="general.goodbye",
        category=IntentCategory.GENERAL,
        description="Goodbye",
        target_agent="rag_agent",
        requires_auth=False,
        examples_he=[
            "להתראות",
            "ביי",
            "תודה וביי",
            "סיימתי",
        ],
        examples_en=[
            "Goodbye",
            "Bye",
            "Thanks, bye",
        ],
    ),
}


def get_intent(intent_id: str) -> Optional[IntentDefinition]:
    """Get intent definition by ID."""
    return INTENT_REGISTRY.get(intent_id)


def get_intents_by_category(category: IntentCategory) -> List[IntentDefinition]:
    """Get all intents in a category."""
    return [
        intent for intent in INTENT_REGISTRY.values()
        if intent.category == category and intent.enabled
    ]


def get_intents_for_agent(agent: str) -> List[IntentDefinition]:
    """Get all intents handled by an agent."""
    return [
        intent for intent in INTENT_REGISTRY.values()
        if intent.target_agent == agent and intent.enabled
    ]


def get_all_examples(language: str = "he") -> Dict[str, List[str]]:
    """Get all examples for training/testing."""
    examples = {}
    for intent_id, intent in INTENT_REGISTRY.items():
        if intent.enabled:
            if language == "he":
                examples[intent_id] = intent.examples_he
            else:
                examples[intent_id] = intent.examples_en
    return examples


def add_custom_intent(intent: IntentDefinition) -> None:
    """Add a custom intent to the registry."""
    INTENT_REGISTRY[intent.id] = intent


def disable_intent(intent_id: str) -> bool:
    """Disable an intent."""
    if intent_id in INTENT_REGISTRY:
        INTENT_REGISTRY[intent_id].enabled = False
        return True
    return False


def enable_intent(intent_id: str) -> bool:
    """Enable an intent."""
    if intent_id in INTENT_REGISTRY:
        INTENT_REGISTRY[intent_id].enabled = True
        return True
    return False
