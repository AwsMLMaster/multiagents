# USA Property Finder Assistant - Architecture Document

## Executive Summary

This document describes the architecture for a multi-agent conversational assistant that helps people search for and evaluate residential real estate anywhere in the United States. The system routes natural-language requests to specialized agents (search, property details, valuation, mortgage, neighborhood, market trends, scheduling, and general Q&A) backed by real estate data providers, with **Fair Housing Act compliance guardrails** enforced at both the input and output layers.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [High-Level Architecture](#high-level-architecture)
4. [Multi-Agent Design](#multi-agent-design)
5. [External Data Integrations](#external-data-integrations)
6. [Intent Management](#intent-management)
7. [Guardrails & Fair Housing Compliance](#guardrails--fair-housing-compliance)
8. [Caching Strategy](#caching-strategy)
9. [Memory & Session Management](#memory--session-management)
10. [Observability](#observability)
11. [Evaluation Framework](#evaluation-framework)
12. [Resilience Patterns](#resilience-patterns)
13. [Performance Targets](#performance-targets)
14. [Deployment Architecture](#deployment-architecture)
15. [Next Steps](#next-steps)

---

## System Overview

### Problem

Home buyers and renters juggle multiple disconnected tools during a search: listing sites, mortgage calculators, school-rating sites, crime-data sites, and manual outreach to agents. This assistant unifies that workflow into one conversational interface, while enforcing that recommendations never violate fair housing law.

### Goals

- **Single conversational entry point** for search, valuation, financing, neighborhood research, market data, and scheduling
- **Fair Housing Act compliance by construction** - discriminatory steering requests are refused at the input guardrail, and outputs are separately checked for steering language
- **Provider-agnostic data layer** - property listings, geocoding, and mortgage rates are abstracted behind interfaces so a specific vendor (ATTOM, Realtor.com/RapidAPI, MLS Grid, Google Maps, Mapbox, Freddie Mac PMMS, etc.) can be swapped via configuration
- **Graceful degradation** - if a data provider is unavailable, the assistant falls back to cached results or a clear "unavailable" message rather than failing outright

---

## Architecture Principles

1. **Agent Modularity** - each agent owns one domain (search, valuation, mortgage, etc.) and can be developed, tested, and scaled independently
2. **Compliance First** - Fair Housing Act guardrails run on every input and every output, not just search queries
3. **Fault Tolerance** - retries, circuit breakers, and fallback chains around every external data call
4. **Observable** - every agent execution and tool call is traced (OpenTelemetry) and measured (latency, cache hit rate)
5. **Provider-Agnostic** - property data, geocoding, and mortgage rates are behind thin client interfaces
6. **No Fabrication** - agents only report what tool calls return; estimates are always labeled as estimates

---

## High-Level Architecture

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                        USA PROPERTY FINDER ASSISTANT                              │
├───────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌─────────────┐     ┌────────────────────────────────────────────────────────┐  │
│  │   Client    │     │                    API GATEWAY                         │  │
│  │ (Web/Mobile)│────▶│  • Rate limiting   • Request validation                 │  │
│  └─────────────┘     └──────────────────────────┬─────────────────────────────┘  │
│                                                  │                                │
│                                                  ▼                                │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                     ORCHESTRATOR LAYER (LangGraph)                         │  │
│  │  ┌──────────────────────────────────────────────────────────────────────┐ │  │
│  │  │      INPUT GUARD → CACHE CHECK → INTENT CLASSIFIER → AGENT ROUTER    │ │  │
│  │  └──────────────────────────────────────────────────────────────────────┘ │  │
│  │        │            │              │             │            │           │  │
│  │        ▼            ▼              ▼             ▼            ▼           │  │
│  │  ┌──────────┐ ┌────────────┐ ┌───────────┐ ┌──────────┐ ┌───────────┐    │  │
│  │  │  SEARCH  │ │  PROPERTY  │ │ VALUATION │ │ MORTGAGE │ │NEIGHBORHOOD│    │  │
│  │  │  AGENT   │ │  DETAILS   │ │  AGENT    │ │  AGENT   │ │   AGENT    │    │  │
│  │  └──────────┘ └────────────┘ └───────────┘ └──────────┘ └───────────┘    │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐                        │  │
│  │  │MARKET TRENDS │  │  SCHEDULING  │  │   RAG    │                        │  │
│  │  │    AGENT     │  │    AGENT     │  │  AGENT   │                        │  │
│  │  └──────────────┘  └──────────────┘  └──────────┘                        │  │
│  │        │                                                                  │  │
│  │        ▼                                                                  │  │
│  │  ┌──────────────────────────────────────────────────────────────────────┐ │  │
│  │  │  OUTPUT GUARD (Fair Housing check, disclaimers, PII mask) → SYNTHESIS│ │  │
│  │  └──────────────────────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                  │                                │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                          INTEGRATION LAYER                                 │  │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐  │  │
│  │  │  AWS BEDROCK  │ │  PROPERTY DATA│ │  GEOCODING    │ │ MORTGAGE      │  │  │
│  │  │  (Claude LLM) │ │  API PROVIDER │ │  PROVIDER     │ │ RATES         │  │  │
│  │  │  + Knowledge  │ │  (ATTOM /     │ │  (Google Maps │ │ PROVIDER      │  │  │
│  │  │  Base (RAG)   │ │  Realtor.com/ │ │  / Mapbox)    │ │ (Freddie Mac  │  │  │
│  │  │               │ │  MLS Grid)    │ │               │ │ PMMS / etc.)  │  │  │
│  │  └───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                  │                                │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                        DATA & CACHE LAYER                                  │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │  │
│  │  │  REDIS          │  │  DYNAMODB       │  │  S3             │            │  │
│  │  │  • Search cache │  │  • Sessions     │  │  • KB documents │            │  │
│  │  │  • Rate limiting│  │  • Saved search │  │  • Audit logs   │            │  │
│  │  │  (15min TTL)    │  │  • Memory       │  │                 │            │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘            │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                  │                                │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                       OBSERVABILITY LAYER                                  │  │
│  │  OpenTelemetry (traces)  •  LangSmith (LLM traces/evals)  •  CloudWatch    │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## Multi-Agent Design

### LangGraph State Machine

```
                                ┌─────────────┐
                                │    START    │
                                └──────┬──────┘
                                       ▼
                                ┌─────────────┐
                          ┌─────│ INPUT_GUARD │
                          │     └──────┬──────┘
                       BLOCKED         │ APPROVED
                          │            ▼
                          │     ┌─────────────┐
                          │     │ CACHE_CHECK │
                          │     └──────┬──────┘
                          │       ┌────┴────┐
                          │      HIT       MISS
                          │       │          │
                          │       ▼          ▼
                          │ ┌───────────┐ ┌────────────────────┐
                          │ │CACHE_RETURN│ │  INTENT_CLASSIFIER │
                          │ └───────────┘ └──────────┬──────────┘
                          │                           │
                          │      ┌──────────┬─────────┼─────────┬──────────┬──────────┐
                          │      ▼          ▼         ▼         ▼          ▼          ▼
                          │ ┌────────┐┌──────────┐┌────────┐┌────────┐┌──────────┐┌────────┐
                          │ │ SEARCH ││ PROPERTY ││VALUATION││MORTGAGE││NEIGHBOR- ││ MARKET │
                          │ │ AGENT  ││ DETAILS  ││ AGENT  ││ AGENT  ││HOOD AGENT││ TRENDS │
                          │ └───┬────┘└────┬─────┘└───┬────┘└───┬────┘└────┬─────┘└───┬────┘
                          │     │          │          │         │          │          │
                          │     │     ┌────────────┐  │    ┌─────────┐     │          │
                          │     │     │ SCHEDULING │  │    │   RAG   │     │          │
                          │     │     │   AGENT    │  │    │  AGENT  │     │          │
                          │     │     └─────┬──────┘  │    └────┬────┘     │          │
                          │     └───────────┴──────────┴─────────┴─────────┴──────────┘
                          │                             │
                          │                             ▼
                          │                    ┌─────────────────┐
                          │                    │  OUTPUT_GUARD   │
                          │                    │ (Fair Housing,  │
                          │                    │ disclaimers, PII)│
                          │                    └────────┬────────┘
                          │                             ▼
                          │                    ┌─────────────────┐
                          │                    │RESPONSE_SYNTHESIS│
                          │                    └────────┬────────┘
                          │                             ▼
                          │                    ┌─────────────────┐
                          │                    │  CACHE_UPDATE   │
                          │                    └────────┬────────┘
                          ▼                             ▼
                 ┌─────────────────┐             ┌─────────────┐
                 │REJECTION_RESPONSE│────────────▶│     END     │
                 └─────────────────┘             └─────────────┘
```

### Agent Specifications

| Agent | Responsibility | Tools | Data Source |
|-------|-----------------|-------|--------------|
| **Search** | Property search by location/price/size/features | `search_listings`, `geocode_location` | Property data provider |
| **Property Details** | Full listing detail, comparisons, favorites | `get_property_details`, `compare_properties` | Property data provider |
| **Valuation** | AVM estimates, comparable sales | `get_avm_estimate`, `get_comparable_sales` | Property data provider |
| **Mortgage** | Payment calculator, affordability, rates | `calculate_payment`, `calculate_affordability`, `get_current_rates` | Deterministic math + rates provider |
| **Neighborhood** | Schools, safety, walkability, commute | `get_school_ratings`, `get_crime_stats`, `estimate_commute` | Geocoding + livability data provider |
| **Market Trends** | Price trends, days-on-market, forecasts | `get_price_trends`, `get_market_forecast` | Market data provider |
| **Scheduling** | Tour booking, agent contact | `schedule_tour`, `contact_listing_agent` | Property data provider / CRM |
| **RAG** | General knowledge & terminology | `knowledge_base_query` | Bedrock Knowledge Base + static FAQ fallback |

---

## External Data Integrations

### Bedrock Configuration

```yaml
bedrock:
  model_id: "anthropic.claude-3-5-sonnet-20241022-v2:0"
  inference_config:
    maxTokens: 4096
    temperature: 0.1

  knowledge_base:
    description: "Real estate glossary, buying/renting process guides, FAQ"
    data_sources:
      - s3://property-finder-docs/glossary/
      - s3://property-finder-docs/process-guides/
      - s3://property-finder-docs/faq/
    embedding_model: "amazon.titan-embed-text-v2:0"

  guardrails:
    content_filters:
      - type: "HATE"
        strength: "HIGH"
    topic_policies:
      - name: "discriminatory_housing_requests"
        action: "BLOCK"
    pii_policies:
      - type: "SSN"
        action: "BLOCK"
      - type: "CREDIT_CARD"
        action: "ANONYMIZE"
```

### Property Data Provider

The `PropertyDataClient` (`src/integrations/property_data_api.py`) is provider-agnostic: it issues authenticated HTTP requests to a configured `base_url` and parses the response into internal `Property`, `ValuationEstimate`, and `ComparableSale` models. Supported provider patterns:

| Provider | Use case |
|---|---|
| ATTOM Data | Property records, AVM, tax history |
| Realtor.com (via RapidAPI) | Active listings search |
| MLS Grid / IDX feed | MLS-sourced listings (requires broker reciprocity agreement) |

### Geocoding Provider

`GeocodingClient` (`src/integrations/geocoding.py`) supports Google Maps Geocoding API or Mapbox, resolving free-text locations to coordinates and computing distance/commute estimates (haversine distance with a driving-time heuristic when no routing API is configured).

### Mortgage Rates Provider

`MortgageRatesClient` (`src/integrations/mortgage_rates.py`) fetches live average rates when configured, and otherwise serves a conservative static fallback table so the mortgage calculator always functions. Payment and affordability math (amortization, PMI threshold, debt-to-income) is computed locally - no external dependency required.

---

## Intent Management

### Intent Registry Structure

```python
INTENT_REGISTRY = {
    "search.properties": {
        "agent": "search_agent",
        "tools": ["search_listings", "geocode_location"],
        "required_params": ["location"],
        "examples": ["Find 3 bedroom homes in Austin, TX under $500,000"],
    },
    "valuation.estimate": {
        "agent": "valuation_agent",
        "tools": ["get_avm_estimate"],
        "required_params": ["property_id_or_address"],
        "examples": ["What's this house worth?"],
    },
    "mortgage.affordability": {
        "agent": "mortgage_agent",
        "tools": ["calculate_affordability"],
        "required_params": ["annual_income"],
        "examples": ["How much house can I afford with an $85,000 salary?"],
    },
    # ... 20 intents total across search, property, valuation, mortgage,
    # neighborhood, market, scheduling, and rag categories
}
```

New intents can be added at runtime via `add_custom_intent()` without code changes to the classifier or graph.

### Classification Strategy

`HybridClassifier` combines an LLM-based classifier (structured JSON output from Claude) with a keyword-based `RuleBasedClassifier` fallback used when the LLM call fails or returns low confidence (<0.5). The classifier prompt explicitly instructs the model to **never infer protected-class preferences into extracted search parameters**, even if implied by user phrasing.

---

## Guardrails & Fair Housing Compliance

Real estate assistants carry a distinct legal risk that generic chatbots do not: the **federal Fair Housing Act (42 U.S.C. §3601 et seq.)** prohibits any statement that indicates a preference, limitation, or discrimination based on race, color, religion, sex, disability, familial status, or national origin ("steering"). This is enforced at two layers:

```
┌──────────────────────────────────────────────────────────────────────┐
│                        GUARDRAIL LAYERS                              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Layer 1: INPUT VALIDATION (src/guardrails/input_validator.py)      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  • Prompt injection detection                                  │ │
│  │  • PII detection (SSN, credit card, phone, email)               │ │
│  │  • Fair Housing Act steering pattern detection - BLOCKS the     │ │
│  │    request outright with an explanatory refusal, and never      │ │
│  │    passes protected-class filters through to the search agent   │ │
│  │  • Length limits, sanitization                                 │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Layer 2: OUTPUT VALIDATION (src/guardrails/output_validator.py)    │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  • Blocks any generated text that characterizes a neighborhood  │ │
│  │    by racial/ethnic composition or recommends based on family   │ │
│  │    status/religion (defense in depth if the LLM drifts)         │ │
│  │  • PII masking                                                 │ │
│  │  • Required disclaimers (AVM estimates, mortgage estimates,     │ │
│  │    market forecasts, legal/tax topics)                          │ │
│  │  • FairHousingComplianceChecker as an additional dedicated pass │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**This is not a substitute for legal review.** Pattern-based detection reduces risk but cannot guarantee full compliance; production deployments should add human review workflows and consult real estate compliance counsel.

### Required Disclaimers

| Context | Disclaimer |
|---|---|
| `valuation.estimate` / `valuation.comps` | AVM estimate, not a licensed appraisal |
| `mortgage.calculate` | Estimate only; actual terms depend on lender/credit profile |
| `mortgage.affordability` | Not a pre-approval or lending commitment |
| `market.trends` / `market.forecast` | Forecasts are trend-based, not guarantees |

---

## Caching Strategy

Property and market data changes far more often than banking FAQ content, so TTLs are shorter than a typical support-chatbot cache:

| Cache | TTL | Rationale |
|---|---|---|
| In-memory (hot) | 60s (capped at 300s) | Repeated queries within a single request burst |
| Redis - search results | 15 min | Listings can go pending/sold quickly |
| Redis - AVM/valuation | 24h | AVM data typically refreshes daily |
| Redis - general Q&A responses | 15 min (non-personalized only) | RAG/FAQ answers are stable short-term |
| DynamoDB - sessions | 30 min sliding window | Conversation continuity |

Personalized responses (tied to `user_context`) and transactional intents (`scheduling.*`, `property.favorite`, `search.save`) are never cached.

---

## Memory & Session Management

`MemoryManager` (`src/memory/memory_manager.py`) provides:

- **Short-term memory**: the active search filters/results and the currently "focused" property for a session, so follow-ups like *"show me more like the second one"* or *"what about a bigger lot"* resolve correctly without re-stating context.
- **Long-term memory**: learned buyer preferences (budget, must-haves, deal-breakers) and episodic history (properties viewed, tours booked) persisted in DynamoDB across sessions.

---

## Observability

### Trace Structure

```python
TRACE_SCHEMA = {
    "service.name": "usa-property-finder-assistant",
    "spans": {
        "request": {"attributes": {"session.id": "string", "request.length": "int"}},
        "cache_check": {"attributes": {"cache.hit": "bool", "cache.latency_ms": "int"}},
        "intent_classification": {"attributes": {"intent.detected": "string", "intent.confidence": "float"}},
        "agent_execution": {"attributes": {"agent.name": "string", "agent.tools_used": "list"}},
        "tool_call": {"attributes": {"tool.name": "string", "tool.latency_ms": "int"}},
    }
}
```

### Key Metrics Dashboard

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Response Latency P50 | <2.5s | >4s |
| Response Latency P95 | <6s | >10s |
| Cache Hit Rate (search) | >30% | <10% |
| Intent Accuracy | >90% | <80% |
| Fair Housing Guardrail Pass Rate | 100% | <100% |
| Error Rate | <2% | >5% |

---

## Evaluation Framework

`Evaluator` (`src/evaluation/framework.py`) runs a golden dataset covering all 8 agent domains plus a **dedicated Fair Housing Act compliance suite** - test cases with discriminatory steering phrasing that must trigger the input guardrail (e.g., *"Only show me houses in white neighborhoods"*, *"Avoid neighborhoods with a lot of immigrants"*). Metrics tracked: intent accuracy, response relevance, Fair Housing compliance pass rate, and latency.

```
Evaluation Summary
==================
Total Tests: 14
Passed: 13 (92.9%)
Failed: 1

Key Metrics:
- Intent Accuracy: 92.9%
- Response Relevance: 100.0%
- Fair Housing Compliance: 100.0%
- Latency Pass Rate: 100.0%
```

---

## Resilience Patterns

Every external dependency (Bedrock, property data provider, geocoding, mortgage rates, Redis, DynamoDB) is wrapped with:

- **Retry with exponential backoff + jitter** (`src/resilience/retry.py`) - per-service policies (e.g., property data allows 3 attempts, geocoding 2)
- **Circuit breaker** (`src/resilience/circuit_breaker.py`) - fails fast after repeated failures, auto-recovers via a half-open probe state
- **Fallback chains** (`src/resilience/fallback.py`) - e.g., property search falls back to cached results, then an empty-results message, rather than a hard error; mortgage rates falls back to a static table

---

## Performance Targets

### Latency Breakdown Target

```
┌────────────────────────────────────────────────────────────┐
│            TARGET LATENCY BREAKDOWN (Total: <4s)           │
├────────────────────────────────────────────────────────────┤
│  Input Guardrails         ██░░░░░░░░░░░░░░░░░░░  100ms     │
│  Cache Check               █░░░░░░░░░░░░░░░░░░░░   50ms     │
│  Intent Classification    ████░░░░░░░░░░░░░░░░░  300ms     │
│  Agent Execution          ██████████████░░░░░░░ 2500ms     │
│  ├─ LLM Call               ████████░░░░░░░░░░░░ 1000ms     │
│  └─ Property/Market API    ██████████░░░░░░░░░░ 1500ms     │
│  Output Guardrails         ██░░░░░░░░░░░░░░░░░░░  100ms     │
│  Response Synthesis        █░░░░░░░░░░░░░░░░░░░░   50ms     │
│                                                            │
│  TOTAL                     ████████████████████ 3100ms     │
│  Buffer                    ██████░░░░░░░░░░░░░░░  900ms     │
└────────────────────────────────────────────────────────────┘
```

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AWS DEPLOYMENT (example)                     │
├─────────────────────────────────────────────────────────────────────┤
│  Region: us-east-1 (or nearest to primary user base)                │
│                                                                     │
│  VPC                                                                │
│  ├─ Public Subnet: ALB, NAT Gateway                                 │
│  ├─ Private Subnet: ECS Fargate (orchestrator + agents)             │
│  └─ Data Subnet: ElastiCache (Redis), DynamoDB (VPC endpoint)       │
│                                                                     │
│  External: Bedrock, Bedrock Knowledge Base, property data provider, │
│  geocoding provider, mortgage rates provider (all outside VPC,      │
│  reached via NAT / VPC endpoints as applicable)                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. **Phase 1 - Foundation**: stand up AWS infra (ECS, ElastiCache, DynamoDB), wire a real property data provider, load the Bedrock Knowledge Base with glossary/FAQ content
2. **Phase 2 - Core Agents**: validate search, property details, and valuation agents against live data; expand the golden evaluation dataset
3. **Phase 3 - Financing & Neighborhood**: integrate a live mortgage rates feed and a real school/crime/walkability data provider
4. **Phase 4 - Compliance Hardening**: legal review of Fair Housing guardrails; expand pattern coverage; add human-review workflow for edge cases
5. **Phase 5 - Production**: load testing, monitoring dashboards, saved-search alert delivery (email/push), launch
