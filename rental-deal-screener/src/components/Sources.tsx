import { SOURCES } from "../data/markets";

export default function Sources() {
  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-lg font-semibold text-slate-100">Sources referenced during the session</h2>
        <ul className="mt-4 space-y-2">
          {SOURCES.map((s) => (
            <li key={s.url}>
              <a
                href={s.url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-emerald-400 underline decoration-emerald-800 underline-offset-4 hover:text-emerald-300"
              >
                {s.label}
              </a>
              <span className="ml-2 text-xs text-slate-600">{s.url}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-amber-900 bg-amber-950/30 p-5 text-sm text-amber-200">
        <h3 className="font-semibold">Data note</h3>
        <p className="mt-2">
          The market figures baked into this app were taken from the 2026 datasets
          discussed during the original strategy session. Different sources use
          different definitions, dates, geographies and methodologies. Revalidate every
          market and property using current local and property-level records before
          investing. This tool is a screening aid, not investment, legal, or tax advice.
        </p>
      </section>
    </div>
  );
}
