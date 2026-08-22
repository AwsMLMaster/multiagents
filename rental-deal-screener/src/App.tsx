import { useEffect, useState } from "react";
import { Deal } from "./types";
import { loadDeals, saveDeals } from "./lib/storage";
import MarketScreener from "./components/MarketScreener";
import CriteriaChecklist from "./components/CriteriaChecklist";
import DealTracker from "./components/DealTracker";
import Sources from "./components/Sources";

type Tab = "markets" | "criteria" | "deals" | "sources";

const TABS: { key: Tab; label: string }[] = [
  { key: "markets", label: "Market Screener" },
  { key: "criteria", label: "Criteria & Workflow" },
  { key: "deals", label: "Deal Tracker" },
  { key: "sources", label: "Sources" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("markets");
  const [deals, setDeals] = useState<Deal[]>(() => loadDeals());

  useEffect(() => {
    saveDeals(deals);
  }, [deals]);

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6">
          <h1 className="text-xl font-semibold text-slate-50">Rental Deal Screener</h1>
          <p className="mt-1 text-sm text-slate-400">
            Distressed rental property strategy: market screening, deal calculator, and
            candidate tracker for the U.S. buy-and-hold play.
          </p>
        </div>
        <nav className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-4 sm:px-6">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={
                "whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition " +
                (tab === t.key
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-slate-400 hover:text-slate-200")
              }
            >
              {t.label}
              {t.key === "deals" && deals.length > 0 && (
                <span className="ml-1.5 rounded-full bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                  {deals.length}
                </span>
              )}
            </button>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        {tab === "markets" && <MarketScreener />}
        {tab === "criteria" && <CriteriaChecklist />}
        {tab === "deals" && <DealTracker deals={deals} onChange={setDeals} />}
        {tab === "sources" && <Sources />}
      </main>

      <footer className="border-t border-slate-800 py-6 text-center text-xs text-slate-600">
        Data stored locally in your browser only. Screening aid, not investment advice.
      </footer>
    </div>
  );
}
