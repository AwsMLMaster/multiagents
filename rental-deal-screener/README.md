# Rental Deal Screener

A client-side web app for screening distressed rental property deals in the
U.S., built from a market-research/investment-strategy session covering
vacancy-adjusted yield screening, target markets (Indianapolis, Cleveland,
Pittsburgh, and a Tier 2 list), Fair-Housing-neutral neighborhood criteria,
distress-signal research workflow, and a full deal cash-flow calculator.

No backend, no database, no API keys required — everything runs in the
browser and your candidate properties are saved to `localStorage`. Fully
portable: `npm install && npm run dev` on any machine with Node.js.

## Screens

- **Market Screener** — the vacancy-adjusted yield table and the revised
  market shortlist (jobs / education / vacancy / property-management
  economics), plus published property-management pricing examples for the
  top 3 markets.
- **Criteria & Workflow** — the target definition, ZIP/neighborhood
  screening criteria, the distress-signal glossary, the research workflow
  (LandGlide/GIS → county assessor → recorder → tax records → foreclosure
  records → distress verification → estimate equity → contact owner), and
  the free-tooling alternative to paid parcel-data subscriptions.
- **Deal Tracker** — add, edit, and delete candidate properties with every
  field from the original "collect for each house" checklist. Each card
  shows live-computed discount %, gross yield, vacancy-adjusted yield, net
  monthly cash flow, and cash-on-cash return, plus a pass/fail badge against
  the strategy's target thresholds. Export the whole list to CSV.

## Deal math

Implements the formula from the strategy session exactly:

```
Rent − vacancy − property tax − insurance − management
     − maintenance − CapEx − HOA − leasing/turnover = actual cash flow
```

See `src/lib/calculations.ts` for the full computation (acquisition
discount, gross yield, vacancy-adjusted yield, annual/monthly net cash flow,
cash-on-cash return) and the target checks (≥9% gross yield, 20–30%
discount, <8% vacancy, ≤10% management fee).

## Getting started

```bash
npm install
npm run dev       # http://localhost:5173
npm run build      # production build to dist/
```

## Data note

The market figures in `src/data/markets.ts` were captured from the original
strategy session's 2026 datasets. Different sources use different
definitions, dates, geographies, and methodologies — revalidate every market
and property using current local/county records before investing. This tool
is a screening aid, not investment, legal, or tax advice.
