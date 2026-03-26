"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { getCompanies, type Company } from "@/lib/api";
import Link from "next/link";

const RISK_BANDS = [
  { label: "Lav (0–39)",     min: 0,  max: 39,  color: "#27AE60" },
  { label: "Moderat (40–69)", min: 40, max: 69,  color: "#C8A951" },
  { label: "Høy (70–100)",   min: 70, max: 100, color: "#C0392B" },
  { label: "Ukjent",         min: -1, max: -1,  color: "#C4BDB4" },
];

function band(score?: number) {
  if (score == null) return 3;
  if (score < 40) return 0;
  if (score < 70) return 1;
  return 2;
}

export default function PortfolioPage() {
  const { data: companies, isLoading } = useSWR<Company[]>(
    "companies-portfolio", () => getCompanies(200),
  );
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState<number | null>(null);

  const filtered = useMemo(() => {
    if (!companies) return [];
    return companies.filter((c) => {
      const matchSearch = !search || (c.navn ?? c.orgnr).toLowerCase().includes(search.toLowerCase());
      const matchRisk   = riskFilter === null || band(c.risk_score) === riskFilter;
      return matchSearch && matchRisk;
    });
  }, [companies, search, riskFilter]);

  const pieData = useMemo(() => {
    if (!companies) return [];
    const counts = [0, 0, 0, 0];
    for (const c of companies) counts[band(c.risk_score)]++;
    return RISK_BANDS.map((b, i) => ({ name: b.label, value: counts[i], color: b.color })).filter((d) => d.value > 0);
  }, [companies]);

  const totalPremium = useMemo(() =>
    filtered.reduce((s) => s, 0), // placeholder — no premium on Company type
  [filtered]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Portefølje</h1>
        <p className="text-sm text-[#8A7F74] mt-1">Oversikt over alle kunder og risikofordeling</p>
      </div>

      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="broker-card h-20 animate-pulse bg-[#EDE8E3]" />)}
        </div>
      )}

      {companies && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="broker-card">
              <p className="text-xs text-[#8A7F74] font-medium mb-1">Totalt kunder</p>
              <p className="text-2xl font-bold text-[#2C3E50]">{companies.length}</p>
            </div>
            {RISK_BANDS.slice(0, 3).map((b, i) => {
              const count = companies.filter((c) => band(c.risk_score) === i).length;
              return (
                <div key={b.label} className="broker-card cursor-pointer hover:bg-[#F9F7F4]"
                  onClick={() => setRiskFilter(riskFilter === i ? null : i)}>
                  <p className="text-xs font-medium mb-1" style={{ color: b.color }}>{b.label}</p>
                  <p className="text-2xl font-bold text-[#2C3E50]">{count}</p>
                  {riskFilter === i && <p className="text-xs text-[#8A7F74] mt-0.5">Filtrert ↑</p>}
                </div>
              );
            })}
          </div>

          {/* Pie chart */}
          {pieData.length > 0 && (
            <div className="broker-card">
              <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">Risikofordeling</h2>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name.split(" ")[0]} ${(percent * 100).toFixed(0)}%`}>
                    {pieData.map((d, i) => <Cell key={i} fill={d.color} />)}
                  </Pie>
                  <Tooltip formatter={(v: number) => [`${v} selskaper`]} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Filter + table */}
          <div className="broker-card">
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              <input
                value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="Søk selskap…"
                className="flex-1 min-w-0 px-3 py-1.5 text-sm border border-[#D4C9B8] rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
              />
              {riskFilter !== null && (
                <button onClick={() => setRiskFilter(null)}
                  className="text-xs px-2.5 py-1 rounded-full bg-[#EDE8E3] text-[#8A7F74] hover:bg-[#DDD8D3]">
                  Nullstill filter ×
                </button>
              )}
              <span className="text-xs text-[#8A7F74]">{filtered.length} selskaper</span>
            </div>

            {filtered.length === 0 ? (
              <p className="text-sm text-[#8A7F74] text-center py-6">Ingen selskaper matcher søket.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                    <th className="text-left pb-2 font-medium">Selskap</th>
                    <th className="text-left pb-2 font-medium">Bransje</th>
                    <th className="text-left pb-2 font-medium hidden md:table-cell">Kommune</th>
                    <th className="text-right pb-2 font-medium">Risiko</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#EDE8E3]">
                  {filtered.map((c) => (
                    <tr key={c.orgnr} className="hover:bg-[#F9F7F4]">
                      <td className="py-2">
                        <Link href={`/search/${c.orgnr}`}
                          className="font-medium text-[#4A6FA5] hover:underline">
                          {c.navn ?? c.orgnr}
                        </Link>
                        <span className="block text-xs text-[#8A7F74] font-normal">{c.orgnr}</span>
                      </td>
                      <td className="py-2 text-xs text-[#8A7F74] max-w-[180px] truncate">
                        {c.naeringskode1_beskrivelse ?? "–"}
                      </td>
                      <td className="py-2 text-xs text-[#8A7F74] hidden md:table-cell">{c.kommune ?? "–"}</td>
                      <td className="py-2 text-right">
                        {c.risk_score != null ? (
                          <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                            style={{
                              background: RISK_BANDS[band(c.risk_score)].color + "20",
                              color: RISK_BANDS[band(c.risk_score)].color,
                            }}>
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
            )}
          </div>
        </>
      )}

      {!isLoading && !companies && (
        <div className="broker-card text-center py-10">
          <p className="text-sm text-[#8A7F74]">Ingen selskaper i databasen ennå. Gå til Admin for å seed demo-data.</p>
        </div>
      )}
    </div>
  );
}
