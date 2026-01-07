"""
Digital Bank Chatbot Platform

A multi-agent AI chatbot platform for digital banking services,
built with LangGraph and AWS Bedrock.
"""

__version__ = "0.1.0"
__author__ = "Digital Bank Team"

from .orchestrator import (
    ChatbotState,
    create_chatbot_app,
    get_chatbot_app,
)

__all__ = [
    "__version__",
    "ChatbotState",
    "create_chatbot_app",
    "get_chatbot_app",
]
