"use client";

import useSWR from "swr";
import { getCompanies, type Company } from "@/lib/api";

function fmt(n: number) {
  return new Intl.NumberFormat("nb-NO").format(n);
}

export default function FinansPage() {
  const { data: companies, isLoading } = useSWR<Company[]>(
    "companies-finans",
    () => getCompanies(50),
  );

  const withRisk = companies?.filter((c) => c.risk_score != null) ?? [];
  const avgRisk =
    withRisk.length > 0
      ? Math.round(withRisk.reduce((sum, c) => sum + (c.risk_score ?? 0), 0) / withRisk.length)
      : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Finansanalyse</h1>
        <p className="text-sm text-[#8A7F74] mt-1">
          Finansielle nøkkeltall og trender på tvers av kundeporteføljen
        </p>
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="broker-card h-20 animate-pulse bg-[#EDE8E3]" />
          ))}
        </div>
      )}

      {/* Summary metrics */}
      {!isLoading && companies && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div className="broker-card">
            <p className="text-xs text-[#8A7F74] font-medium mb-1">Antall selskaper</p>
            <p className="text-2xl font-bold text-[#2C3E50]">{companies.length}</p>
          </div>
          <div className="broker-card">
            <p className="text-xs text-[#8A7F74] font-medium mb-1">Gjennomsnittlig risikoscore</p>
            <p className="text-2xl font-bold text-[#2C3E50]">{avgRisk ?? "–"}</p>
          </div>
          <div className="broker-card">
            <p className="text-xs text-[#8A7F74] font-medium mb-1">Analysert (med score)</p>
            <p className="text-2xl font-bold text-[#2C3E50]">{withRisk.length}</p>
          </div>
        </div>
      )}

      {/* Placeholder */}
      <div className="broker-card border-l-4 border-[#C8A951]">
        <p className="text-sm font-semibold text-[#2C3E50] mb-1">Full implementasjon kommer</p>
        <p className="text-sm text-[#8A7F74]">
          Finansfanen vil vise aggregerte regnskapstall (omsetning, EBITDA, egenkapitalandel)
          på tvers av alle kunder, bransjesammenligning mot SSB-benchmarks, trendlinjer per år,
          og varslinger om selskaper med svake nøkkeltall.
        </p>
      </div>

      {/* Risk distribution */}
      {!isLoading && companies && companies.length > 0 && (
        <div className="broker-card">
          <h2 className="text-sm font-semibold text-[#2C3E50] mb-4">Risikofordeling</h2>
          <div className="space-y-3">
            {[
              { label: "Lav risiko (0–39)", filter: (c: Company) => (c.risk_score ?? 100) < 40, color: "bg-green-500" },
              { label: "Middels risiko (40–69)", filter: (c: Company) => { const s = c.risk_score ?? 0; return s >= 40 && s < 70; }, color: "bg-amber-500" },
              { label: "Høy risiko (70+)", filter: (c: Company) => (c.risk_score ?? 0) >= 70, color: "bg-red-500" },
            ].map(({ label, filter, color }) => {
              const count = companies.filter(filter).length;
              const pct = companies.length > 0 ? Math.round((count / companies.length) * 100) : 0;
              return (
                <div key={label}>
                  <div className="flex justify-between text-xs text-[#8A7F74] mb-1">
                    <span>{label}</span>
                    <span>{count} ({pct}%)</span>
                  </div>
                  <div className="h-2 bg-[#EDE8E3] rounded-full overflow-hidden">
                    <div
                      className={`h-full ${color} rounded-full transition-all duration-500`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {!isLoading && companies && companies.length === 0 && (
        <div className="broker-card text-center py-10">
          <p className="text-sm text-[#8A7F74]">
            Ingen selskaper i databasen ennå. Gå til Admin for å seed demo-data.
          </p>
        </div>
      )}
    </div>
  );
}
