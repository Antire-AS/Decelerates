"use client";

import useSWR from "swr";
import { getPortfolioOverview, getCompanies, type Company } from "@/lib/api";

export default function PortfolioPage() {
  const { data: overview, isLoading: overviewLoading } = useSWR(
    "portfolio-overview",
    getPortfolioOverview,
  );
  const { data: companies, isLoading: companiesLoading } = useSWR<Company[]>(
    "companies-portfolio",
    () => getCompanies(50),
  );

  const isLoading = overviewLoading || companiesLoading;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Portefølje</h1>
        <p className="text-sm text-[#8A7F74] mt-1">
          Oversikt over alle kunder, risikofordeling og bransjeprofil
        </p>
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="broker-card h-24 animate-pulse bg-[#EDE8E3]" />
          ))}
        </div>
      )}

      {/* Portfolio summary */}
      {!isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="broker-card">
            <p className="text-xs text-[#8A7F74] font-medium mb-1">Totalt antall kunder</p>
            <p className="text-2xl font-bold text-[#2C3E50]">
              {companies ? companies.length : "–"}
            </p>
          </div>
          <div className="broker-card">
            <p className="text-xs text-[#8A7F74] font-medium mb-1">Høy risiko</p>
            <p className="text-2xl font-bold text-[#C0392B]">
              {companies
                ? companies.filter((c) => (c.risk_score ?? 0) >= 70).length
                : "–"}
            </p>
          </div>
          <div className="broker-card">
            <p className="text-xs text-[#8A7F74] font-medium mb-1">Lav risiko</p>
            <p className="text-2xl font-bold text-[#27AE60]">
              {companies
                ? companies.filter((c) => (c.risk_score ?? 100) < 40).length
                : "–"}
            </p>
          </div>
        </div>
      )}

      {/* Placeholder for full implementation */}
      <div className="broker-card border-l-4 border-[#C8A951]">
        <p className="text-sm font-semibold text-[#2C3E50] mb-1">Full implementasjon kommer</p>
        <p className="text-sm text-[#8A7F74]">
          Porteføljeoversikten vil vise risikofordeling som kakediagram, bransjefordeling,
          premievolumoversikt per kundesegment, og en filtrerbar tabell over alle kunder
          med risikoscore, bransje og fornyelsesdatoer.
        </p>
      </div>

      {/* Companies table */}
      {companies && companies.length > 0 && (
        <div className="broker-card">
          <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">
            Alle selskaper ({companies.length})
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                <th className="text-left pb-2 font-medium">Selskap</th>
                <th className="text-left pb-2 font-medium">Bransje</th>
                <th className="text-left pb-2 font-medium">Kommune</th>
                <th className="text-right pb-2 font-medium">Risikoscore</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDE8E3]">
              {companies.map((c) => (
                <tr key={c.orgnr} className="hover:bg-[#F9F7F4]">
                  <td className="py-2 font-medium text-[#2C3E50]">
                    {c.navn ?? c.orgnr}
                    <span className="block text-xs text-[#8A7F74] font-normal">{c.orgnr}</span>
                  </td>
                  <td className="py-2 text-xs text-[#8A7F74] max-w-[160px] truncate">
                    {c.naeringskode1_beskrivelse ?? "–"}
                  </td>
                  <td className="py-2 text-xs text-[#8A7F74]">{c.kommune ?? "–"}</td>
                  <td className="py-2 text-right">
                    {c.risk_score != null ? (
                      <span
                        className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                          c.risk_score >= 70
                            ? "bg-red-100 text-red-700"
                            : c.risk_score >= 40
                              ? "bg-amber-100 text-amber-700"
                              : "bg-green-100 text-green-700"
                        }`}
                      >
                        {c.risk_score}
                      </span>
                    ) : (
                      <span className="text-xs text-[#8A7F74]">–</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {companies && companies.length === 0 && (
        <div className="broker-card text-center py-10">
          <p className="text-sm text-[#8A7F74]">
            Ingen selskaper i databasen ennå. Gå til Admin for å seed demo-data.
          </p>
        </div>
      )}
    </div>
  );
}
