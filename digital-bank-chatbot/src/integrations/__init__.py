"""
Integration modules for external services.

This package provides integration with:
- AWS Bedrock (LLM inference)
- AWS Bedrock Knowledge Base (RAG)
- TCS Bancs (Core Banking)
"""

from .bedrock_client import (
    BedrockClient,
    BedrockConfig,
    BedrockResponse,
    BedrockInvocationError,
    create_bedrock_client,
    HEBREW_SYSTEM_PROMPT,
)

from .knowledge_base import (
    KnowledgeBaseClient,
    KnowledgeBaseConfig,
    KnowledgeBaseResponse,
    RetrievalResult,
    KnowledgeBaseError,
    MultiKnowledgeBaseClient,
    create_knowledge_base_client,
)

from .tcs_bancs import (
    TCSBancsClient,
    TCSBancsConfig,
    TCSBancsError,
    AccountBalance,
    Transaction,
    TransferRequest,
    TransferResponse,
    LoanDetails,
    TransactionType,
    TransactionStatus,
    create_tcs_bancs_client,
)

__all__ = [
    # Bedrock
    "BedrockClient",
    "BedrockConfig",
    "BedrockResponse",
    "BedrockInvocationError",
    "create_bedrock_client",
    "HEBREW_SYSTEM_PROMPT",
    # Knowledge Base
    "KnowledgeBaseClient",
    "KnowledgeBaseConfig",
    "KnowledgeBaseResponse",
    "RetrievalResult",
    "KnowledgeBaseError",
    "MultiKnowledgeBaseClient",
    "create_knowledge_base_client",
    # TCS Bancs
    "TCSBancsClient",
    "TCSBancsConfig",
    "TCSBancsError",
    "AccountBalance",
    "Transaction",
    "TransferRequest",
    "TransferResponse",
    "LoanDetails",
    "TransactionType",
    "TransactionStatus",
    "create_tcs_bancs_client",
]
