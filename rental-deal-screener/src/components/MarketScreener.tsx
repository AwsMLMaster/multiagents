import { useMemo, useState } from "react";
import {
  VACANCY_YIELD_TABLE,
  MARKET_SHORTLIST,
  MANAGEMENT_PRICING,
} from "../data/markets";
import StarRating from "./StarRating";

type SortKey = keyof (typeof VACANCY_YIELD_TABLE)[number];

export default function MarketScreener() {
  const [sortKey, setSortKey] = useState<SortKey>("vacancyAdjustedYieldPct");
  const [sortDesc, setSortDesc] = useState(true);

  const sortedYieldTable = useMemo(() => {
    const rows = [...VACANCY_YIELD_TABLE];
    rows.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "number" && typeof bv === "number") {
        return sortDesc ? bv - av : av - bv;
      }
      return sortDesc
        ? String(bv).localeCompare(String(av))
        : String(av).localeCompare(String(bv));
    });
    return rows;
  }, [sortKey, sortDesc]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDesc((d) => !d);
    } else {
      setSortKey(key);
      setSortDesc(true);
    }
  }

  const columns: { key: SortKey; label: string }[] = [
    { key: "market", label: "Market" },
    { key: "grossYieldPct", label: "Gross yield" },
    { key: "vacancyPct", label: "Vacancy" },
    { key: "occupancyPct", label: "Occupancy" },
    { key: "vacancyAdjustedYieldPct", label: "Vacancy-adj. yield" },
  ];

  return (
    <div className="space-y-8">
      <section>
        <h2 className="text-lg font-semibold text-slate-100">Vacancy-adjusted yield screen</h2>
        <p className="mt-1 text-sm text-slate-400">
          <span className="font-mono text-slate-300">
            Vacancy-adjusted gross yield = Gross rent-to-price yield × (1 − vacancy)
          </span>{" "}
          — a screening metric only. Not net yield: taxes, insurance, maintenance,
          management, CapEx, HOA and turnover still need to be deducted (see Deal
          Calculator).
        </p>
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-800">
          <table className="min-w-full divide-y divide-slate-800 text-sm">
            <thead className="bg-slate-900">
              <tr>
                {columns.map((c) => (
                  <th
                    key={c.key}
                    onClick={() => toggleSort(c.key)}
                    className="cursor-pointer select-none whitespace-nowrap px-4 py-2 text-left font-medium text-slate-300 hover:text-white"
                  >
                    {c.label}
                    {sortKey === c.key ? (sortDesc ? " ↓" : " ↑") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 bg-slate-950">
              {sortedYieldTable.map((row) => (
                <tr key={row.market} className="hover:bg-slate-900/60">
                  <td className="whitespace-nowrap px-4 py-2 font-medium text-slate-100">{row.market}</td>
                  <td className="whitespace-nowrap px-4 py-2 text-slate-300">{row.grossYieldPct}%</td>
                  <td className="whitespace-nowrap px-4 py-2 text-slate-300">{row.vacancyPct}%</td>
                  <td className="whitespace-nowrap px-4 py-2 text-slate-300">{row.occupancyPct}%</td>
                  <td className="whitespace-nowrap px-4 py-2 font-semibold text-emerald-400">
                    {row.vacancyAdjustedYieldPct}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-100">
          Revised shortlist (jobs, tenant quality, management economics)
        </h2>
        <p className="mt-1 text-sm text-slate-400">
          Adds required factors beyond raw yield: enough jobs, educated tenant pool, a
          reliable property manager with fees that don't destroy profit, and
          stable/growing population.
        </p>
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-800">
          <table className="min-w-full divide-y divide-slate-800 text-sm">
            <thead className="bg-slate-900">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-slate-300">Rank</th>
                <th className="px-4 py-2 text-left font-medium text-slate-300">Market</th>
                <th className="px-4 py-2 text-left font-medium text-slate-300">Cash flow</th>
                <th className="px-4 py-2 text-left font-medium text-slate-300">Jobs</th>
                <th className="px-4 py-2 text-left font-medium text-slate-300">Education / tenant quality</th>
                <th className="px-4 py-2 text-left font-medium text-slate-300">Vacancy</th>
                <th className="px-4 py-2 text-left font-medium text-slate-300">PM economics</th>
                <th className="px-4 py-2 text-left font-medium text-slate-300">Tier</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 bg-slate-950">
              {MARKET_SHORTLIST.map((row) => (
                <tr key={row.market} className="align-top hover:bg-slate-900/60">
                  <td className="px-4 py-2 font-mono text-slate-400">#{row.rank}</td>
                  <td className="px-4 py-2">
                    <div className="font-medium text-slate-100">{row.market}</div>
                    <div className="mt-0.5 max-w-xs text-xs text-slate-500">{row.rationale}</div>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2"><StarRating value={row.cashFlow} /></td>
                  <td className="whitespace-nowrap px-4 py-2"><StarRating value={row.jobs} /></td>
                  <td className="whitespace-nowrap px-4 py-2"><StarRating value={row.educationTenantQuality} /></td>
                  <td className="whitespace-nowrap px-4 py-2"><StarRating value={row.vacancy} /></td>
                  <td className="whitespace-nowrap px-4 py-2"><StarRating value={row.propertyManagementEconomics} /></td>
                  <td className="whitespace-nowrap px-4 py-2">
                    <span
                      className={
                        "rounded px-2 py-0.5 text-xs font-medium " +
                        (row.tier === 1
                          ? "bg-emerald-900/60 text-emerald-300"
                          : row.tier === 2
                          ? "bg-sky-900/60 text-sky-300"
                          : "bg-amber-900/60 text-amber-300")
                      }
                    >
                      {row.tier === "separate" ? "Separate strategy" : `Tier ${row.tier}`}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-100">Property management pricing examples</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          {MANAGEMENT_PRICING.map((m) => (
            <div key={m.market} className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
              <h3 className="font-medium text-slate-100">{m.market}</h3>
              <ul className="mt-2 space-y-1 text-sm text-slate-400">
                {m.examples.map((ex, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-slate-600">•</span>
                    <span>{ex}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
