# Digital Bank Chatbot Platform - Architecture Document

## Executive Summary

This document describes the architecture for a next-generation digital bank chatbot platform designed to replace the legacy system. The new architecture addresses critical pain points including slow response times (28s → <3s target), lack of caching, missing session management, and translation overhead, while enabling secure financial transactions through TCS Bancs integration.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [High-Level Architecture](#high-level-architecture)
4. [Multi-Agent Design](#multi-agent-design)
5. [AWS Services Integration](#aws-services-integration)
6. [Intent Management](#intent-management)
7. [TCS Bancs Integration](#tcs-bancs-integration)
8. [Caching Strategy](#caching-strategy)
9. [Session Management](#session-management)
10. [Guardrails & Security](#guardrails--security)
11. [Observability](#observability)
12. [Evaluation Framework](#evaluation-framework)
13. [Performance Targets](#performance-targets)

---

## System Overview

### Current State Pain Points

| # | Pain Point | Impact | Solution |
|---|------------|--------|----------|
| 1 | No cache for general answers | Redundant LLM calls, high latency | Redis semantic cache + DynamoDB |
| 2 | No historical session store | No conversation context | DynamoDB session store |
| 3 | Hebrew ↔ English translation overhead | Added latency, translation errors | Native Hebrew LLM (Claude 3.5) |
| 4 | Intent-based question translation | Rigid, hard to maintain | LangGraph dynamic routing |
| 5 | 28 seconds average response | Poor UX | Target <3s with caching/optimization |
| 6 | No financial transaction capability | Limited functionality | TCS Bancs API integration |
| 7 | Weak guardrails | Security/compliance risk | AWS Bedrock Guardrails |
| 8 | No evaluation framework | Cannot measure quality | LangSmith + custom evals |
| 9 | Small golden dataset | Limited testing | Expanded synthetic + real dataset |
| 10 | Ad-hoc RAG databases | Operational overhead | AWS Bedrock Knowledge Base |

### Target Architecture Benefits

- **Sub-3 second response times** via intelligent caching and parallel processing
- **Native Hebrew support** eliminating translation layer
- **Secure financial transactions** through TCS Bancs integration
- **Enterprise-grade observability** with OTel and LangSmith
- **Modular agent architecture** for easy capability extension
- **AWS-native services** for reliability and compliance

---

## Architecture Principles

1. **Agent Modularity**: Each agent handles a specific domain (RAG, transactions, intent routing)
2. **Fault Tolerance**: Graceful degradation, circuit breakers, retry mechanisms
3. **Security First**: Multi-layer guardrails, PII protection, transaction validation
4. **Observable**: Every decision traceable via LangSmith and OTel
5. **Scalable**: Horizontal scaling via AWS Lambda/ECS
6. **Hebrew Native**: No translation layer, direct Hebrew processing

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DIGITAL BANK CHATBOT PLATFORM                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────┐     ┌──────────────────────────────────────────────────────────┐  │
│  │   Client    │     │                    API GATEWAY (AWS)                      │  │
│  │  (Mobile/   │────▶│  • Authentication (JWT/OAuth2)                           │  │
│  │   Web App)  │     │  • Rate Limiting                                          │  │
│  └─────────────┘     │  • Request Validation                                     │  │
│                      └──────────────────────┬───────────────────────────────────┘  │
│                                             │                                       │
│                                             ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                         ORCHESTRATOR LAYER (LangGraph)                        │  │
│  │  ┌────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    SUPERVISOR AGENT (Central Coordinator)               │  │  │
│  │  │  • Intent Classification    • Agent Selection    • Response Synthesis   │  │  │
│  │  │  • Conversation State       • Error Handling     • Fallback Logic       │  │  │
│  │  └────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                         │                                     │  │
│  │              ┌──────────────────────────┼──────────────────────────┐         │  │
│  │              │                          │                          │         │  │
│  │              ▼                          ▼                          ▼         │  │
│  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │  │
│  │  │   RAG AGENT         │  │  TRANSACTION AGENT  │  │  ACCOUNT AGENT      │  │  │
│  │  │  • General Banking  │  │  • Fund Transfer    │  │  • Balance Inquiry  │  │  │
│  │  │  • Product Info     │  │  • Bill Payment     │  │  • Statement        │  │  │
│  │  │  • FAQ              │  │  • Loan Payment     │  │  • Account Details  │  │  │
│  │  │  • Policies         │  │  • Standing Orders  │  │  • Notifications    │  │  │
│  │  └─────────┬───────────┘  └─────────┬───────────┘  └─────────┬───────────┘  │  │
│  │            │                        │                        │               │  │
│  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │  │
│  │  │   LOAN AGENT        │  │  SUPPORT AGENT      │  │  ANALYTICS AGENT    │  │  │
│  │  │  • Loan Status      │  │  • Complaint        │  │  • Spending Insights│  │  │
│  │  │  • EMI Calculator   │  │  • Service Request  │  │  • Budget Analysis  │  │  │
│  │  │  • Eligibility      │  │  • Branch/ATM Info  │  │  • Predictions      │  │  │
│  │  │  • Application      │  │  • Escalation       │  │  • Recommendations  │  │  │
│  │  └─────────┴───────────┘  └─────────┴───────────┘  └─────────┴───────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                             │                                       │
│  ┌──────────────────────────────────────────┴───────────────────────────────────┐  │
│  │                           INTEGRATION LAYER                                   │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │  │
│  │  │  TCS BANCS      │  │  AWS BEDROCK    │  │  BEDROCK        │               │  │
│  │  │  CONNECTOR      │  │  KNOWLEDGE BASE │  │  GUARDRAILS     │               │  │
│  │  │  • Core Banking │  │  • Document RAG │  │  • PII Filter   │               │  │
│  │  │  • Payments     │  │  • Product KB   │  │  • Content Safe │               │  │
│  │  │  • Loans        │  │  • FAQ          │  │  • Topic Block  │               │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘               │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                             │                                       │
│  ┌──────────────────────────────────────────┴───────────────────────────────────┐  │
│  │                           DATA & CACHE LAYER                                  │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │  │
│  │  │  ELASTICACHE    │  │  DYNAMODB       │  │  S3             │               │  │
│  │  │  (Redis)        │  │                 │  │                 │               │  │
│  │  │  • Semantic     │  │  • Sessions     │  │  • Documents    │               │  │
│  │  │    Cache        │  │  • User Context │  │  • Audit Logs   │               │  │
│  │  │  • Response     │  │  • Intent Cache │  │  • Eval Data    │               │  │
│  │  │    Cache        │  │  • Transactions │  │  • Models       │               │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘               │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                             │                                       │
│  ┌──────────────────────────────────────────┴───────────────────────────────────┐  │
│  │                         OBSERVABILITY LAYER                                   │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │  │
│  │  │  LANGSMITH      │  │  AWS CLOUDWATCH │  │  OPENTELEMETRY  │               │  │
│  │  │  • LLM Traces   │  │  • Metrics      │  │  • Distributed  │               │  │
│  │  │  • Evals        │  │  • Logs         │  │    Tracing      │               │  │
│  │  │  • Datasets     │  │  • Alarms       │  │  • Spans        │               │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘               │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Multi-Agent Design

### LangGraph State Machine

```
                                    ┌─────────────────┐
                                    │      START      │
                                    └────────┬────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                              ┌─────│   INPUT_GUARD   │─────┐
                              │     └────────┬────────┘     │
                              │              │              │
                           BLOCKED      APPROVED       NEEDS_AUTH
                              │              │              │
                              ▼              ▼              ▼
                    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
                    │  REJECTION  │  │ CACHE_CHECK │  │    AUTH     │
                    │  RESPONSE   │  └──────┬──────┘  │   VERIFY    │
                    └─────────────┘         │         └──────┬──────┘
                                            │                │
                                    ┌───────┴───────┐        │
                                    │               │        │
                                 HIT            MISS         │
                                    │               │        │
                                    ▼               ▼        ▼
                          ┌─────────────┐  ┌─────────────────────┐
                          │CACHE_RETURN │  │  INTENT_CLASSIFIER  │
                          └─────────────┘  └──────────┬──────────┘
                                                      │
                    ┌──────────┬──────────┬──────────┼──────────┬──────────┐
                    │          │          │          │          │          │
                    ▼          ▼          ▼          ▼          ▼          ▼
             ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
             │   RAG    │ │TRANSACTION│ │ ACCOUNT │ │   LOAN   │ │ SUPPORT  │
             │  AGENT   │ │  AGENT   │ │  AGENT  │ │  AGENT   │ │  AGENT   │
             └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
                  │            │            │            │            │
                  │            │     ┌──────┴──────┐     │            │
                  │            │     │             │     │            │
                  │            │  SIMPLE      COMPLEX    │            │
                  │            │     │             │     │            │
                  │            ▼     ▼             ▼     ▼            │
                  │     ┌────────────────┐  ┌────────────────┐        │
                  │     │  TCS_BANCS_API │  │ HUMAN_HANDOFF  │        │
                  │     └───────┬────────┘  └───────┬────────┘        │
                  │             │                   │                 │
                  └──────────┬──┴───────────────────┴─────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ OUTPUT_GUARD    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │RESPONSE_SYNTHESIS│
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  CACHE_UPDATE   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │       END       │
                    └─────────────────┘
```

### Agent Specifications

| Agent | Responsibility | Tools | Data Sources |
|-------|---------------|-------|--------------|
| **Supervisor** | Orchestration, routing, synthesis | All agents | Session state |
| **RAG Agent** | General banking knowledge | Bedrock KB, Search | Knowledge Base |
| **Transaction Agent** | Financial operations | TCS Bancs API | Core Banking |
| **Account Agent** | Account information | TCS Bancs API | Core Banking |
| **Loan Agent** | Loan management | TCS Bancs API, Calculator | Loan System |
| **Support Agent** | Customer service | Ticketing API | CRM |
| **Analytics Agent** | Financial insights | Analytics API | Data Warehouse |

---

## AWS Services Integration

### Bedrock Configuration

```yaml
bedrock:
  model_id: "anthropic.claude-3-5-sonnet-20241022-v2:0"
  inference_config:
    maxTokens: 4096
    temperature: 0.1
    topP: 0.9

  knowledge_base:
    id: "BANK_KB_001"
    data_sources:
      - s3://bank-documents/policies/
      - s3://bank-documents/products/
      - s3://bank-documents/faq/
    embedding_model: "amazon.titan-embed-text-v2:0"
    vector_store: "opensearch-serverless"
    chunking:
      strategy: "semantic"
      max_tokens: 512
      overlap: 50

  guardrails:
    id: "BANK_GUARDRAIL_001"
    content_filters:
      - type: "SEXUAL"
        strength: "HIGH"
      - type: "VIOLENCE"
        strength: "HIGH"
      - type: "HATE"
        strength: "HIGH"
    topic_policies:
      - name: "competitor_discussion"
        action: "BLOCK"
      - name: "investment_advice"
        action: "WARN"
    pii_policies:
      - type: "CREDIT_CARD"
        action: "ANONYMIZE"
      - type: "SSN"
        action: "BLOCK"
      - type: "BANK_ACCOUNT"
        action: "ANONYMIZE"
    word_policies:
      - words: ["guaranteed returns", "risk-free"]
        action: "BLOCK"
```

### Bedrock AgentCore

```yaml
agent_core:
  agent_id: "BANK_AGENT_001"
  foundation_model: "anthropic.claude-3-5-sonnet-20241022-v2:0"

  action_groups:
    - name: "account_operations"
      api_schema: "openapi/account-api.yaml"
      lambda_arn: "arn:aws:lambda:region:account:function:account-handler"

    - name: "transaction_operations"
      api_schema: "openapi/transaction-api.yaml"
      lambda_arn: "arn:aws:lambda:region:account:function:transaction-handler"

    - name: "loan_operations"
      api_schema: "openapi/loan-api.yaml"
      lambda_arn: "arn:aws:lambda:region:account:function:loan-handler"

  knowledge_bases:
    - kb_id: "BANK_KB_001"
      description: "General banking knowledge and policies"
```

---

## Intent Management

### Intent Registry

```python
INTENT_REGISTRY = {
    # Account Intents
    "account.balance": {
        "agent": "account_agent",
        "auth_required": True,
        "tools": ["get_balance"],
        "params": ["account_id"],
        "examples_he": ["מה היתרה שלי?", "כמה כסף יש לי בחשבון?"],
        "examples_en": ["What's my balance?", "How much money do I have?"]
    },
    "account.statement": {
        "agent": "account_agent",
        "auth_required": True,
        "tools": ["get_statement"],
        "params": ["account_id", "date_range"],
        "examples_he": ["הצג לי את התנועות האחרונות", "דוח חשבון"],
        "examples_en": ["Show recent transactions", "Account statement"]
    },

    # Transaction Intents
    "transaction.transfer": {
        "agent": "transaction_agent",
        "auth_required": True,
        "mfa_required": True,
        "tools": ["initiate_transfer", "confirm_transfer"],
        "params": ["from_account", "to_account", "amount", "currency"],
        "examples_he": ["העבר 1000 שקל לחשבון 12345", "רוצה לבצע העברה"],
        "examples_en": ["Transfer 1000 NIS to account 12345"]
    },
    "transaction.bill_payment": {
        "agent": "transaction_agent",
        "auth_required": True,
        "tools": ["pay_bill"],
        "params": ["biller_id", "amount"],
        "examples_he": ["שלם חשבון חשמל", "תשלום ארנונה"],
        "examples_en": ["Pay electricity bill", "Pay municipal tax"]
    },

    # Loan Intents
    "loan.status": {
        "agent": "loan_agent",
        "auth_required": True,
        "tools": ["get_loan_details"],
        "params": ["loan_id"],
        "examples_he": ["מה המצב של ההלוואה שלי?", "כמה נשאר לשלם?"],
        "examples_en": ["What's my loan status?", "How much left to pay?"]
    },
    "loan.calculator": {
        "agent": "loan_agent",
        "auth_required": False,
        "tools": ["calculate_emi"],
        "params": ["principal", "rate", "tenure"],
        "examples_he": ["חשב החזר חודשי להלוואה של 100000"],
        "examples_en": ["Calculate monthly payment for 100000 loan"]
    },

    # RAG Intents
    "rag.general": {
        "agent": "rag_agent",
        "auth_required": False,
        "tools": ["knowledge_base_query"],
        "examples_he": ["מה שעות הפעילות?", "איך פותחים חשבון?"],
        "examples_en": ["What are the operating hours?", "How to open account?"]
    },
    "rag.products": {
        "agent": "rag_agent",
        "auth_required": False,
        "tools": ["product_search"],
        "examples_he": ["ספר לי על חשבון חיסכון", "מה הריביות על פיקדונות?"],
        "examples_en": ["Tell me about savings account", "Deposit interest rates?"]
    },

    # Support Intents
    "support.complaint": {
        "agent": "support_agent",
        "auth_required": True,
        "tools": ["create_ticket", "get_ticket_status"],
        "examples_he": ["יש לי תלונה", "רוצה לדבר עם נציג"],
        "examples_en": ["I have a complaint", "Want to speak to agent"]
    },

    # Analytics Intents
    "analytics.spending": {
        "agent": "analytics_agent",
        "auth_required": True,
        "tools": ["analyze_spending", "get_insights"],
        "examples_he": ["על מה אני מוציא הכי הרבה?", "ניתוח הוצאות"],
        "examples_en": ["What do I spend most on?", "Spending analysis"]
    }
}
```

### Dynamic Intent Addition

New intents can be added via configuration without code changes:

```yaml
# config/intents/custom_intents.yaml
intents:
  - id: "crypto.portfolio"
    agent: "crypto_agent"
    auth_required: true
    tools: ["get_crypto_balance", "trade_crypto"]
    params: ["crypto_symbol", "amount"]
    examples_he: ["מה מצב התיק קריפטו שלי?"]
    examples_en: ["What's my crypto portfolio status?"]
    enabled: true
    feature_flag: "crypto_enabled"
```

---

## TCS Bancs Integration

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TCS BANCS INTEGRATION LAYER                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    API GATEWAY (Internal)                    │   │
│  │  • mTLS Authentication    • Request Signing                  │   │
│  │  • Rate Limiting          • Circuit Breaker                  │   │
│  └─────────────────────────────────┬───────────────────────────┘   │
│                                    │                                │
│  ┌─────────────────────────────────┴───────────────────────────┐   │
│  │                    SERVICE MESH (AWS App Mesh)               │   │
│  └─────────────────────────────────┬───────────────────────────┘   │
│                                    │                                │
│  ┌──────────────┬──────────────┬───┴────────┬──────────────────┐   │
│  │              │              │            │                   │   │
│  ▼              ▼              ▼            ▼                   ▼   │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐             │
│ │ACCOUNT │ │PAYMENT │ │  LOAN  │ │CUSTOMER│ │STANDING│             │
│ │SERVICE │ │SERVICE │ │SERVICE │ │SERVICE │ │ORDERS  │             │
│ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘             │
│     │          │          │          │          │                   │
│  ┌──┴──────────┴──────────┴──────────┴──────────┴──┐               │
│  │           TCS BANCS ADAPTER LAYER               │               │
│  │  • Protocol Translation (REST ↔ ISO 20022)      │               │
│  │  • Message Mapping                              │               │
│  │  • Error Handling                               │               │
│  │  • Idempotency Management                       │               │
│  └─────────────────────────┬───────────────────────┘               │
│                            │                                        │
│                            ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    TCS BANCS CORE                            │   │
│  │              (Bank's Core Banking System)                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### API Operations

| Operation | TCS Bancs API | Security Level | Timeout |
|-----------|--------------|----------------|---------|
| Get Balance | `/accounts/{id}/balance` | AUTH | 2s |
| Get Statement | `/accounts/{id}/transactions` | AUTH | 5s |
| Fund Transfer | `/payments/transfer` | AUTH + MFA | 10s |
| Bill Payment | `/payments/bills` | AUTH + MFA | 10s |
| Loan Inquiry | `/loans/{id}/details` | AUTH | 3s |
| Standing Order | `/payments/standing-orders` | AUTH + MFA | 10s |

---

## Caching Strategy

### Multi-Layer Cache Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      CACHING LAYERS                            │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Layer 1: IN-MEMORY (Application Level)                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • TTL: 60 seconds                                        │  │
│  │  • Purpose: Hot data, frequent queries                    │  │
│  │  • Size: 100MB per instance                               │  │
│  │  • Implementation: Python lru_cache + TTL wrapper         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                    │
│                            ▼                                    │
│  Layer 2: DISTRIBUTED (ElastiCache Redis)                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Semantic Cache:                                          │  │
│  │  • Vector similarity search for questions                 │  │
│  │  • TTL: 24 hours for general knowledge                    │  │
│  │  • Threshold: 0.95 cosine similarity                      │  │
│  │                                                           │  │
│  │  Response Cache:                                          │  │
│  │  • Exact match on normalized queries                      │  │
│  │  • TTL: 1 hour for account data, 24h for general          │  │
│  │                                                           │  │
│  │  Session Cache:                                           │  │
│  │  • Conversation context                                   │  │
│  │  • TTL: 30 minutes sliding window                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                    │
│                            ▼                                    │
│  Layer 3: PERSISTENT (DynamoDB)                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • Historical sessions                                    │  │
│  │  • User preferences                                       │  │
│  │  • Intent patterns                                        │  │
│  │  • Audit logs                                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Cache Keys Structure

```python
CACHE_KEY_PATTERNS = {
    # Semantic cache for RAG queries
    "semantic": "semantic:{embedding_hash}",

    # Response cache
    "response": "response:{intent}:{normalized_query_hash}",

    # Session cache
    "session": "session:{user_id}:{session_id}",

    # User context
    "user_context": "user:{user_id}:context",

    # Rate limiting
    "rate_limit": "ratelimit:{user_id}:{endpoint}",

    # Account data (short TTL)
    "account_balance": "account:{account_id}:balance",
    "account_transactions": "account:{account_id}:txns:{date_range_hash}"
}
```

---

## Session Management

### Session State Schema

```python
@dataclass
class SessionState:
    session_id: str
    user_id: str
    conversation_history: List[Message]
    current_intent: Optional[str]
    intent_params: Dict[str, Any]
    auth_level: AuthLevel  # NONE, BASIC, MFA
    pending_transaction: Optional[Transaction]
    language: str  # "he" or "en"
    created_at: datetime
    last_activity: datetime
    metadata: Dict[str, Any]

@dataclass
class Message:
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime
    intent: Optional[str]
    confidence: Optional[float]
    agent: Optional[str]
    tools_used: List[str]
    latency_ms: int
```

### Session Lifecycle

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  NEW    │────▶│ ACTIVE  │────▶│ IDLE    │────▶│ EXPIRED │
└─────────┘     └────┬────┘     └────┬────┘     └─────────┘
                     │               │
                     │   Activity    │
                     └───────────────┘
```

---

## Guardrails & Security

### Multi-Layer Security Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SECURITY LAYERS                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Layer 1: INPUT VALIDATION                                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  • Input sanitization (XSS, injection prevention)             │  │
│  │  • Length limits (max 2000 chars)                             │  │
│  │  • Language detection                                          │  │
│  │  • Prompt injection detection                                  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Layer 2: BEDROCK GUARDRAILS                                        │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  • Content filtering (harmful, inappropriate)                 │  │
│  │  • Topic blocking (competitors, investment advice)            │  │
│  │  • PII detection and anonymization                            │  │
│  │  • Word/phrase blocking                                        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Layer 3: TRANSACTION SECURITY                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  • MFA for financial operations                               │  │
│  │  • Transaction limits validation                               │  │
│  │  • Velocity checks                                             │  │
│  │  • Fraud detection integration                                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Layer 4: OUTPUT VALIDATION                                         │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  • Response sanitization                                       │  │
│  │  • PII masking in logs                                        │  │
│  │  • Confidence threshold checks                                 │  │
│  │  • Hallucination detection                                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Layer 5: AUDIT & COMPLIANCE                                        │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  • Complete audit trail                                        │  │
│  │  • Regulatory compliance (banking regulations)                │  │
│  │  • Data retention policies                                     │  │
│  │  • GDPR/Privacy compliance                                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Custom Guardrail Rules

```python
BANKING_GUARDRAILS = {
    "prohibited_topics": [
        "investment_advice_specific",  # Cannot recommend specific investments
        "competitor_comparison",       # Cannot discuss competitors
        "legal_advice",               # Cannot provide legal guidance
        "tax_advice_specific",        # Cannot provide specific tax advice
    ],

    "required_disclaimers": {
        "loan_calculator": "This is an estimate only. Actual terms may vary.",
        "investment_info": "Past performance is not indicative of future results.",
        "exchange_rates": "Rates shown are indicative and may change.",
    },

    "transaction_limits": {
        "daily_transfer_limit": 50000,  # NIS
        "single_transfer_limit": 20000,
        "require_mfa_above": 1000,
    },

    "pii_patterns": [
        r"\b\d{9}\b",  # Israeli ID
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # Credit card
        r"\b\d{2,3}[-\s]?\d{7}\b",  # Bank account
    ]
}
```

---

## Observability

### OpenTelemetry Integration

```python
# Trace Structure
TRACE_SCHEMA = {
    "service.name": "digital-bank-chatbot",
    "spans": {
        "request": {
            "attributes": {
                "user.id": "string",
                "session.id": "string",
                "request.language": "string",
                "request.length": "int",
            }
        },
        "cache_check": {
            "attributes": {
                "cache.hit": "bool",
                "cache.type": "string",
                "cache.latency_ms": "int",
            }
        },
        "intent_classification": {
            "attributes": {
                "intent.detected": "string",
                "intent.confidence": "float",
                "intent.fallback": "bool",
            }
        },
        "agent_execution": {
            "attributes": {
                "agent.name": "string",
                "agent.tools_used": "list",
                "agent.latency_ms": "int",
            }
        },
        "llm_call": {
            "attributes": {
                "llm.model": "string",
                "llm.tokens_input": "int",
                "llm.tokens_output": "int",
                "llm.latency_ms": "int",
            }
        },
        "tcs_bancs_call": {
            "attributes": {
                "api.endpoint": "string",
                "api.status_code": "int",
                "api.latency_ms": "int",
            }
        },
    }
}
```

### LangSmith Integration

```python
LANGSMITH_CONFIG = {
    "project_name": "digital-bank-chatbot",
    "tracing_enabled": True,
    "feedback_enabled": True,

    "evaluation_datasets": [
        "golden_dataset_general",
        "golden_dataset_transactions",
        "golden_dataset_hebrew",
    ],

    "metrics": [
        "response_correctness",
        "intent_accuracy",
        "response_relevance",
        "latency_p50",
        "latency_p95",
        "guardrail_triggers",
    ]
}
```

### Key Metrics Dashboard

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Response Latency P50 | <2s | >3s |
| Response Latency P95 | <5s | >8s |
| Cache Hit Rate | >60% | <40% |
| Intent Accuracy | >95% | <90% |
| Transaction Success Rate | >99% | <95% |
| Guardrail Triggers | <5% | >10% |
| Error Rate | <1% | >2% |

---

## Evaluation Framework

### Evaluation Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EVALUATION FRAMEWORK                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    GOLDEN DATASETS                           │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐               │   │
│  │  │  General  │  │Transaction│  │  Hebrew   │               │   │
│  │  │   (200)   │  │   (150)   │  │   (300)   │               │   │
│  │  └───────────┘  └───────────┘  └───────────┘               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    EVALUATORS                                │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │   │
│  │  │    Intent     │  │   Response    │  │    Safety     │   │   │
│  │  │   Accuracy    │  │   Quality     │  │   Compliance  │   │   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘   │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │   │
│  │  │   Latency     │  │  Transaction  │  │   Hebrew      │   │   │
│  │  │   Benchmark   │  │   Accuracy    │  │   Quality     │   │   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    REPORTING                                 │   │
│  │  • LangSmith Dashboard                                       │   │
│  │  • CloudWatch Metrics                                        │   │
│  │  • Weekly Quality Reports                                    │   │
│  │  • Regression Alerts                                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Evaluation Metrics

```python
EVALUATION_METRICS = {
    "intent_accuracy": {
        "description": "Accuracy of intent classification",
        "target": 0.95,
        "evaluator": "exact_match",
    },
    "response_relevance": {
        "description": "Relevance of response to query",
        "target": 0.90,
        "evaluator": "llm_judge",
    },
    "response_correctness": {
        "description": "Factual correctness of response",
        "target": 0.95,
        "evaluator": "llm_judge_with_context",
    },
    "transaction_accuracy": {
        "description": "Correct handling of financial transactions",
        "target": 0.99,
        "evaluator": "exact_match",
    },
    "hebrew_quality": {
        "description": "Quality of Hebrew responses",
        "target": 0.90,
        "evaluator": "native_speaker_eval",
    },
    "safety_compliance": {
        "description": "Adherence to guardrails",
        "target": 1.0,
        "evaluator": "guardrail_check",
    },
    "latency_p95": {
        "description": "95th percentile response time",
        "target": 5000,  # ms
        "evaluator": "percentile",
    },
}
```

### Test Scenarios

```yaml
# test_scenarios.yaml
scenarios:
  - name: "balance_inquiry_hebrew"
    input: "מה היתרה בחשבון שלי?"
    expected_intent: "account.balance"
    expected_agent: "account_agent"
    auth_required: true

  - name: "fund_transfer_with_amount"
    input: "העבר 500 שקל לחשבון של אבא"
    expected_intent: "transaction.transfer"
    expected_agent: "transaction_agent"
    expected_params:
      amount: 500
      currency: "ILS"
    auth_required: true
    mfa_required: true

  - name: "general_faq"
    input: "איך פותחים חשבון בנק?"
    expected_intent: "rag.general"
    expected_agent: "rag_agent"
    should_use_knowledge_base: true

  - name: "guardrail_investment_advice"
    input: "באיזה מניות כדאי להשקיע?"
    expected_behavior: "disclaimer_or_refuse"
    guardrail_triggered: true
```

---

## Performance Targets

### Latency Breakdown Target

```
┌────────────────────────────────────────────────────────────┐
│            TARGET LATENCY BREAKDOWN (Total: <3s)           │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  API Gateway + Auth       ████░░░░░░░░░░░░░░░░  200ms     │
│  Input Guardrails         ██░░░░░░░░░░░░░░░░░░░  100ms     │
│  Cache Check              █░░░░░░░░░░░░░░░░░░░░   50ms     │
│  Intent Classification    ████░░░░░░░░░░░░░░░░░  200ms     │
│  Agent Execution          █████████████░░░░░░░░ 1500ms     │
│  ├─ LLM Call              ████████████░░░░░░░░░ 1200ms     │
│  ├─ Knowledge Base        ██░░░░░░░░░░░░░░░░░░░  200ms     │
│  └─ TCS Bancs API         █░░░░░░░░░░░░░░░░░░░░  100ms     │
│  Output Guardrails        ██░░░░░░░░░░░░░░░░░░░  100ms     │
│  Response Synthesis       ████░░░░░░░░░░░░░░░░░  200ms     │
│  Cache Update             █░░░░░░░░░░░░░░░░░░░░   50ms     │
│                                                            │
│  TOTAL                    ████████████████████  2400ms     │
│  Buffer                   ████░░░░░░░░░░░░░░░░░  600ms     │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Scaling Targets

| Metric | Current | Target |
|--------|---------|--------|
| Concurrent Users | 100 | 10,000 |
| Requests/Second | 10 | 1,000 |
| Response Time P50 | 28s | 2s |
| Response Time P95 | 45s | 5s |
| Cache Hit Rate | 0% | 60% |
| Availability | 95% | 99.9% |

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AWS DEPLOYMENT                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Region: Primary (il-central-1 or eu-west-1)                       │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  VPC (10.0.0.0/16)                                          │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                   │   │
│  │  │ Public Subnet   │  │ Public Subnet   │                   │   │
│  │  │ (10.0.1.0/24)   │  │ (10.0.2.0/24)   │                   │   │
│  │  │ ┌─────────────┐ │  │ ┌─────────────┐ │                   │   │
│  │  │ │ ALB         │ │  │ │ NAT Gateway │ │                   │   │
│  │  │ └─────────────┘ │  │ └─────────────┘ │                   │   │
│  │  └─────────────────┘  └─────────────────┘                   │   │
│  │                                                              │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                   │   │
│  │  │ Private Subnet  │  │ Private Subnet  │                   │   │
│  │  │ (10.0.3.0/24)   │  │ (10.0.4.0/24)   │                   │   │
│  │  │ ┌─────────────┐ │  │ ┌─────────────┐ │                   │   │
│  │  │ │ ECS Fargate │ │  │ │ ECS Fargate │ │                   │   │
│  │  │ │ (Chatbot)   │ │  │ │ (Workers)   │ │                   │   │
│  │  │ └─────────────┘ │  │ └─────────────┘ │                   │   │
│  │  └─────────────────┘  └─────────────────┘                   │   │
│  │                                                              │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                   │   │
│  │  │ Data Subnet     │  │ Data Subnet     │                   │   │
│  │  │ (10.0.5.0/24)   │  │ (10.0.6.0/24)   │                   │   │
│  │  │ ┌─────────────┐ │  │ ┌─────────────┐ │                   │   │
│  │  │ │ElastiCache  │ │  │ │ DynamoDB    │ │                   │   │
│  │  │ │ (Redis)     │ │  │ │ (VPC EP)    │ │                   │   │
│  │  │ └─────────────┘ │  │ └─────────────┘ │                   │   │
│  │  └─────────────────┘  └─────────────────┘                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. **Phase 1 - Foundation (Weeks 1-4)**
   - Set up AWS infrastructure (VPC, ECS, ElastiCache, DynamoDB)
   - Implement LangGraph orchestrator skeleton
   - Create Bedrock Knowledge Base with initial documents
   - Set up observability stack

2. **Phase 2 - Core Agents (Weeks 5-8)**
   - Implement RAG Agent with Bedrock KB
   - Implement Account Agent with TCS Bancs integration
   - Implement basic caching layer
   - Set up guardrails

3. **Phase 3 - Transactions (Weeks 9-12)**
   - Implement Transaction Agent
   - Add MFA flow
   - Implement Loan Agent
   - Security audit

4. **Phase 4 - Optimization (Weeks 13-16)**
   - Performance tuning
   - Evaluation framework deployment
   - Golden dataset expansion
   - Load testing

5. **Phase 5 - Production (Weeks 17-20)**
   - Production deployment
   - Monitoring setup
   - Documentation
   - Training
