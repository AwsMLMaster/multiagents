import {
  ZIP_SCREENING_CRITERIA,
  RESEARCH_WORKFLOW,
  FREE_ALTERNATIVE_TOOLS,
  TARGET_DEFINITION,
} from "../data/markets";
import { DISTRESS_SIGNALS } from "../types";

export default function CriteriaChecklist() {
  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-emerald-900 bg-emerald-950/30 p-5">
        <h2 className="text-lg font-semibold text-emerald-300">Target definition</h2>
        <p className="mt-2 text-sm text-slate-300">
          The goal is <em>not</em> to find the cheapest distressed house in America. The
          goal is to find a distressed house in a strong employment/education market
          where the house can be bought{" "}
          <strong className="text-emerald-300">
            {TARGET_DEFINITION.discountMinPct}–{TARGET_DEFINITION.discountMaxPct}% below
            realistic market value
          </strong>{" "}
          and rented for a gross yield of{" "}
          <strong className="text-emerald-300">≥{TARGET_DEFINITION.grossYieldMinPct}%</strong>,
          with market rental vacancy{" "}
          <strong className="text-emerald-300">&lt;{TARGET_DEFINITION.vacancyMaxPct}%</strong> and
          professional management{" "}
          <strong className="text-emerald-300">≤{TARGET_DEFINITION.managementMaxPct}%</strong>.
        </p>
        <p className="mt-3 rounded bg-slate-950/60 p-3 font-mono text-xs text-slate-400">
          Rent − vacancy − property tax − insurance − management − maintenance − CapEx −
          HOA − leasing/turnover = actual cash flow
        </p>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-100">ZIP / neighborhood screening criteria</h2>
        <p className="mt-1 text-sm text-slate-400">
          Don't search an entire city uniformly. Use: ZIP → neighborhood → house → rent
          → tenant profile → property manager → distress.
        </p>
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {ZIP_SCREENING_CRITERIA.map((c, i) => (
            <li
              key={i}
              className="flex items-start gap-2 rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-sm text-slate-300"
            >
              <span className="mt-0.5 text-emerald-400">✓</span>
              <span>{c}</span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-100">Distress signals</h2>
        <p className="mt-1 text-sm text-slate-400">
          Actual mortgage payment history and bank-account information are generally not
          public. Recorded mortgages, lenders, liens, tax delinquency and foreclosure
          filings can be public.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {DISTRESS_SIGNALS.map((s) => (
            <span
              key={s}
              className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300"
            >
              {s}
            </span>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-100">Research workflow</h2>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {RESEARCH_WORKFLOW.map((step, i) => (
            <div key={step} className="flex items-center gap-2">
              <span className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-200">
                {step}
              </span>
              {i < RESEARCH_WORKFLOW.length - 1 && <span className="text-slate-600">→</span>}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-100">Free alternative to paid parcel tools</h2>
        <p className="mt-1 text-sm text-slate-400">
          A mostly-free workflow (avoid paying for a subscription unless its convenience
          is worth it):
        </p>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {FREE_ALTERNATIVE_TOOLS.map((t) => (
            <li
              key={t}
              className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-sm text-slate-300"
            >
              {t}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
