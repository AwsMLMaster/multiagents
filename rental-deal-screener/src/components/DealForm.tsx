import { useState } from "react";
import { Deal, DISTRESS_SIGNALS, DistressSignal, PopulationTrend } from "../types";
import { ALL_TARGET_MARKETS } from "../data/markets";
import { calculateDealMetrics, checkAgainstTargets, formatCurrency, formatPercent } from "../lib/calculations";

interface Props {
  initial: Deal;
  onSave: (deal: Deal) => void;
  onCancel: () => void;
}

function numOrNull(v: string): number | null {
  if (v.trim() === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

const POPULATION_TRENDS: PopulationTrend[] = ["Growing", "Stable", "Declining", "Unknown"];

function NumberField({
  label,
  value,
  onChange,
  suffix,
  placeholder,
}: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  suffix?: string;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-400">{label}</span>
      <div className="mt-1 flex items-center gap-1">
        <input
          type="number"
          value={value ?? ""}
          placeholder={placeholder}
          onChange={(e) => onChange(numOrNull(e.target.value))}
          className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
        />
        {suffix && <span className="text-xs text-slate-500">{suffix}</span>}
      </div>
    </label>
  );
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-400">{label}</span>
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
      />
    </label>
  );
}

export default function DealForm({ initial, onSave, onCancel }: Props) {
  const [deal, setDeal] = useState<Deal>(initial);

  function set<K extends keyof Deal>(key: K, value: Deal[K]) {
    setDeal((d) => ({ ...d, [key]: value }));
  }

  function toggleSignal(signal: DistressSignal) {
    setDeal((d) => ({
      ...d,
      distressSignals: d.distressSignals.includes(signal)
        ? d.distressSignals.filter((s) => s !== signal)
        : [...d.distressSignals, signal],
    }));
  }

  const metrics = calculateDealMetrics(deal);
  const checks = checkAgainstTargets(deal, metrics);

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="text-lg font-semibold text-slate-100">
        {initial.address || initial.market ? "Edit candidate property" : "Add candidate property"}
      </h2>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <TextField label="Address" value={deal.address} onChange={(v) => set("address", v)} placeholder="123 Main St, Indianapolis, IN" />
        <label className="block">
          <span className="text-xs font-medium text-slate-400">Market</span>
          <input
            type="text"
            list="markets"
            value={deal.market}
            onChange={(e) => set("market", e.target.value)}
            placeholder="Indianapolis"
            className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
          />
          <datalist id="markets">
            {ALL_TARGET_MARKETS.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </label>
        <TextField label="ZIP code" value={deal.zip} onChange={(v) => set("zip", v)} placeholder="46202" />
        <TextField label="Property type" value={deal.propertyType} onChange={(v) => set("propertyType", v)} placeholder="Single-family" />
      </div>

      <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-slate-400">Valuation & acquisition</h3>
      <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <NumberField label="Estimated market value" value={deal.estMarketValue} onChange={(v) => set("estMarketValue", v)} suffix="$" />
        <NumberField label="Asking / auction price" value={deal.askingPrice} onChange={(v) => set("askingPrice", v)} suffix="$" />
        <NumberField label="Est. total cash required" value={deal.estimatedTotalCashRequired} onChange={(v) => set("estimatedTotalCashRequired", v)} suffix="$" />
      </div>

      <div className="mt-3">
        <span className="text-xs font-medium text-slate-400">Distress signals</span>
        <div className="mt-2 flex flex-wrap gap-2">
          {DISTRESS_SIGNALS.map((s) => (
            <button
              type="button"
              key={s}
              onClick={() => toggleSignal(s)}
              className={
                "rounded-full border px-3 py-1 text-xs transition " +
                (deal.distressSignals.includes(s)
                  ? "border-emerald-500 bg-emerald-900/50 text-emerald-300"
                  : "border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-500")
              }
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-slate-400">Rental income</h3>
      <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <NumberField label="Expected monthly rent" value={deal.expectedMonthlyRent} onChange={(v) => set("expectedMonthlyRent", v)} suffix="$" />
        <NumberField label="Market vacancy" value={deal.marketVacancyPct} onChange={(v) => set("marketVacancyPct", v)} suffix="%" />
      </div>

      <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-slate-400">Operating expenses</h3>
      <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <NumberField label="Property tax (annual)" value={deal.propertyTaxAnnual} onChange={(v) => set("propertyTaxAnnual", v)} suffix="$" />
        <NumberField label="Insurance (annual)" value={deal.insuranceAnnual} onChange={(v) => set("insuranceAnnual", v)} suffix="$" />
        <NumberField label="Management fee" value={deal.managementFeePct} onChange={(v) => set("managementFeePct", v)} suffix="% of rent" />
        <NumberField label="Maintenance + CapEx reserve" value={deal.maintenanceCapexPct} onChange={(v) => set("maintenanceCapexPct", v)} suffix="% of rent" />
        <NumberField label="HOA" value={deal.hoaMonthly} onChange={(v) => set("hoaMonthly", v)} suffix="$/mo" />
        <NumberField label="Leasing / turnover cost (annual)" value={deal.turnoverCostAnnual} onChange={(v) => set("turnoverCostAnnual", v)} suffix="$" />
      </div>

      <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-slate-400">Neighborhood screening</h3>
      <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <NumberField label="Median household income" value={deal.neighborhoodMedianIncome} onChange={(v) => set("neighborhoodMedianIncome", v)} suffix="$" placeholder="target > 60,000" />
        <NumberField label="Bachelor's degree+ population" value={deal.bachelorsPlusPct} onChange={(v) => set("bachelorsPlusPct", v)} suffix="%" placeholder="target ≥ 30" />
        <NumberField label="Unemployment" value={deal.unemploymentPct} onChange={(v) => set("unemploymentPct", v)} suffix="%" />
        <label className="block">
          <span className="text-xs font-medium text-slate-400">Population trend</span>
          <select
            value={deal.populationTrend}
            onChange={(e) => set("populationTrend", e.target.value as PopulationTrend)}
            className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
          >
            {POPULATION_TRENDS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <TextField label="Crime note (relative to surrounding area)" value={deal.crimeNote} onChange={(v) => set("crimeNote", v)} />
        <TextField label="Commute note" value={deal.commuteNote} onChange={(v) => set("commuteNote", v)} />
        <TextField label="Property manager options" value={deal.propertyManagerOptions} onChange={(v) => set("propertyManagerOptions", v)} placeholder="2-3 candidates serving this ZIP" />
      </div>

      <label className="mt-6 block">
        <span className="text-xs font-medium text-slate-400">Notes</span>
        <textarea
          value={deal.notes}
          onChange={(e) => set("notes", e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
        />
      </label>

      <div className="mt-6 rounded-lg border border-slate-800 bg-slate-950/60 p-4">
        <h3 className="text-sm font-semibold text-slate-200">Live calculation</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Acquisition discount" value={formatPercent(metrics.acquisitionDiscountPct)} />
          <Metric label="Gross yield (on price)" value={formatPercent(metrics.grossYieldOnPriceP, 2)} />
          <Metric label="Vacancy-adjusted yield" value={formatPercent(metrics.vacancyAdjustedYieldPct, 2)} />
          <Metric label="Annual expenses" value={formatCurrency(metrics.annualExpenses)} />
          <Metric label="Net monthly cash flow" value={formatCurrency(metrics.monthlyCashFlow)} highlight />
          <Metric label="Net annual cash flow" value={formatCurrency(metrics.annualCashFlow)} />
          <Metric label="Cash-on-cash return" value={formatPercent(metrics.cashOnCashReturnPct)} />
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {checks.map((c) => (
            <div key={c.label} className="flex items-center gap-2 text-xs">
              <span
                className={
                  "flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] " +
                  (c.pass === null
                    ? "bg-slate-700 text-slate-400"
                    : c.pass
                    ? "bg-emerald-600 text-white"
                    : "bg-rose-600 text-white")
                }
              >
                {c.pass === null ? "?" : c.pass ? "✓" : "✕"}
              </span>
              <span className="text-slate-300">{c.label}</span>
              <span className="text-slate-500">— {c.detail}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 flex justify-end gap-3">
        <button
          onClick={onCancel}
          className="rounded-md border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
        >
          Cancel
        </button>
        <button
          onClick={() => onSave({ ...deal, updatedAt: new Date().toISOString() })}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
        >
          Save deal
        </button>
      </div>
    </div>
  );
}

function Metric({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={"mt-0.5 text-base font-semibold " + (highlight ? "text-emerald-400" : "text-slate-100")}>
        {value}
      </div>
    </div>
  );
}
