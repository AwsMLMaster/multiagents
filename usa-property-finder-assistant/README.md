# USA Property Finder Assistant

A multi-agent, LangGraph-based virtual assistant for searching and evaluating
residential real estate across the United States. It helps buyers and
renters search listings, get automated valuations and comparable sales,
calculate mortgage payments and affordability, research neighborhoods, read
local market trends, and schedule tours - all through natural conversation,
with built-in **Fair Housing Act compliance guardrails**.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system design.

## Features

- **Property search** across location, price, beds/baths, type, and features
- **Property details**, side-by-side comparisons, and favorites
- **Automated valuation (AVM)** estimates and comparable recent sales
- **Mortgage calculator**: monthly payment breakdown, affordability estimate, current rates
- **Neighborhood insights**: schools, safety, walkability, amenities, commute time
- **Market trends**: median price, days on market, buyer's/seller's market read, forecasts
- **Tour scheduling** and listing agent contact requests
- **General real estate Q&A** (terminology, buying/renting process) via a Bedrock Knowledge Base
- **Fair Housing Act guardrails**: refuses to filter or characterize properties/neighborhoods
  by race, color, religion, sex, disability, familial status, or national origin
- Multi-layer caching, resilience (retry/circuit breaker/fallback), and observability
  (OpenTelemetry + LangSmith)

## Project layout

```
usa-property-finder-assistant/
├── config/settings.py          # Environment-driven configuration
├── docs/ARCHITECTURE.md        # Full architecture document
├── src/
│   ├── orchestrator/           # LangGraph state + graph wiring all agents
│   ├── agents/                 # 8 specialized agents + shared base agent
│   ├── intents/                # Intent registry + LLM/rule-based classifiers
│   ├── guardrails/              # Input/output validation, Fair Housing checks
│   ├── integrations/           # Bedrock, Knowledge Base, property data, geocoding, mortgage rates
│   ├── cache/                  # Multi-layer cache manager
│   ├── memory/                 # Short/long-term buyer memory
│   ├── preferences/            # Saved searches & alerts
│   ├── resilience/             # Retry, circuit breaker, fallback patterns
│   ├── observability/          # Telemetry (OTel + LangSmith + metrics)
│   └── evaluation/             # Golden-dataset evaluation framework
└── tests/                      # Offline unit tests (no network/AWS required)
```

## Agents

| Agent | Responsibility |
|-------|-----------------|
| Search | Property search by location/price/size/features |
| Property Details | Full listing details, comparisons, favorites |
| Valuation | AVM value estimates and comparable sales |
| Mortgage | Payment calculator, affordability, current rates |
| Neighborhood | Schools, safety, walkability, amenities, commute |
| Market Trends | Price trends, days-on-market, forecasts |
| Scheduling | Tour booking, listing agent contact |
| RAG | General real estate knowledge & terminology |

## Getting started

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your API keys
```

Run the offline unit tests (no AWS/network calls required):

```bash
python tests/test_intents.py
```

### Required external services (production)

| Purpose | Example providers |
|---|---|
| LLM inference | AWS Bedrock (Claude) |
| Knowledge base (RAG) | AWS Bedrock Knowledge Base |
| Property listings & public records | ATTOM Data, Realtor.com (RapidAPI), MLS Grid/IDX |
| Geocoding | Google Maps Geocoding API, Mapbox |
| Mortgage rates | Freddie Mac PMMS feed, RapidAPI mortgage rate providers |
| Session/memory store | DynamoDB |
| Cache | Redis / ElastiCache |

All external integrations degrade gracefully (empty results / fallback rates)
when not configured, so the assistant can run and be evaluated without live
API keys.

## Compliance note

This assistant is designed to comply with the federal **Fair Housing Act**
(42 U.S.C. §3601 et seq.): it never filters, ranks, or comments on properties
or neighborhoods based on race, color, religion, sex, disability, familial
status, or national origin, regardless of how a request is phrased. See
`src/guardrails/input_validator.py` and `src/guardrails/output_validator.py`.
This is not a substitute for legal review - consult counsel before
production deployment.
