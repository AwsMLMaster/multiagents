import { useMemo, useState } from "react";
import { Deal, emptyDeal } from "../types";
import { calculateDealMetrics, checkAgainstTargets, formatCurrency, formatPercent } from "../lib/calculations";
import { dealsToCsv, downloadCsv } from "../lib/csv";
import DealForm from "./DealForm";

interface Props {
  deals: Deal[];
  onChange: (deals: Deal[]) => void;
}

export default function DealTracker({ deals, onChange }: Props) {
  const [editingDeal, setEditingDeal] = useState<Deal | null>(null);
  const [isAdding, setIsAdding] = useState(false);

  const sorted = useMemo(
    () => [...deals].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)),
    [deals]
  );

  function handleSave(deal: Deal) {
    const exists = deals.some((d) => d.id === deal.id);
    onChange(exists ? deals.map((d) => (d.id === deal.id ? deal : d)) : [...deals, deal]);
    setEditingDeal(null);
    setIsAdding(false);
  }

  function handleDelete(id: string) {
    if (confirm("Delete this candidate property? This can't be undone.")) {
      onChange(deals.filter((d) => d.id !== id));
    }
  }

  function handleExport() {
    if (deals.length === 0) return;
    downloadCsv(`rental-deal-screener-${new Date().toISOString().slice(0, 10)}.csv`, dealsToCsv(deals));
  }

  if (isAdding) {
    return <DealForm initial={emptyDeal()} onSave={handleSave} onCancel={() => setIsAdding(false)} />;
  }
  if (editingDeal) {
    return <DealForm initial={editingDeal} onSave={handleSave} onCancel={() => setEditingDeal(null)} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-slate-100">
          Candidate properties <span className="text-slate-500">({deals.length})</span>
        </h2>
        <div className="flex gap-2">
          <button
            onClick={handleExport}
            disabled={deals.length === 0}
            className="rounded-md border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Export CSV
          </button>
          <button
            onClick={() => setIsAdding(true)}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            + Add candidate property
          </button>
        </div>
      </div>

      {deals.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-800 p-10 text-center text-sm text-slate-500">
          No candidate properties yet. Add one to start tracking distress signal, price,
          rent, and computed yield/cash flow.
        </div>
      ) : (
        <div className="space-y-3">
          {sorted.map((deal) => {
            const metrics = calculateDealMetrics(deal);
            const checks = checkAgainstTargets(deal, metrics);
            const passCount = checks.filter((c) => c.pass === true).length;
            const failCount = checks.filter((c) => c.pass === false).length;

            return (
              <div
                key={deal.id}
                className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 transition hover:border-slate-700"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-slate-100">
                        {deal.address || "Untitled property"}
                      </h3>
                      {deal.market && (
                        <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                          {deal.market}
                          {deal.zip ? ` · ${deal.zip}` : ""}
                        </span>
                      )}
                    </div>
                    {deal.distressSignals.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {deal.distressSignals.map((s) => (
                          <span key={s} className="rounded-full bg-rose-950/60 px-2 py-0.5 text-[10px] text-rose-300">
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={
                        "rounded-full px-2.5 py-1 text-xs font-medium " +
                        (failCount === 0 && passCount === checks.length
                          ? "bg-emerald-900/60 text-emerald-300"
                          : failCount > 0
                          ? "bg-rose-900/60 text-rose-300"
                          : "bg-slate-800 text-slate-400")
                      }
                    >
                      {passCount}/{checks.length} targets met
                    </span>
                    <button
                      onClick={() => setEditingDeal(deal)}
                      className="rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(deal.id)}
                      className="rounded-md border border-rose-900 px-3 py-1.5 text-xs text-rose-400 hover:bg-rose-950/50"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                  <MiniMetric label="Asking price" value={formatCurrency(deal.askingPrice)} />
                  <MiniMetric label="Discount" value={formatPercent(metrics.acquisitionDiscountPct)} />
                  <MiniMetric label="Gross yield" value={formatPercent(metrics.grossYieldOnPriceP, 2)} />
                  <MiniMetric label="Vacancy-adj. yield" value={formatPercent(metrics.vacancyAdjustedYieldPct, 2)} />
                  <MiniMetric label="Net cash flow/mo" value={formatCurrency(metrics.monthlyCashFlow)} highlight />
                  <MiniMetric label="Cash-on-cash" value={formatPercent(metrics.cashOnCashReturnPct)} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function MiniMetric({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={"text-sm font-semibold " + (highlight ? "text-emerald-400" : "text-slate-200")}>
        {value}
      </div>
    </div>
  );
}
