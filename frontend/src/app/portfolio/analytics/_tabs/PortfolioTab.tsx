"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { Loader2 } from "lucide-react";
import {
  getPortfolios, getPortfolioRisk,
  type PortfolioItem, type PortfolioRiskRow,
} from "@/lib/api";
import { fmtMnok, MetricCard } from "./_shared";
import { useRiskConfig, bandTailwindClass } from "@/lib/useRiskConfig";

export default function PortfolioTab() {
  const { bandFor } = useRiskConfig();
  const { data: portfolios, isLoading: loadingPortfolios } = useSWR<PortfolioItem[]>("portfolios-fin", getPortfolios);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const activeId = selectedId ?? (portfolios?.[0]?.id ?? null);
  const { data: rows, isLoading: loadingRows } = useSWR<PortfolioRiskRow[]>(
    activeId ? `portfolio-risk-${activeId}` : null,
    () => getPortfolioRisk(activeId!),
  );

  if (loadingPortfolios) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-[#4A6FA5]" /></div>;
  if (!portfolios?.length) return <div className="broker-card text-center py-10 text-sm text-[#8A7F74]">Ingen porteføljer funnet. Opprett en i Portefølje-fanen.</div>;

  const revenues = (rows ?? []).filter((r) => r.revenue != null).map((r) => ({ name: r.navn ?? r.orgnr, value: +(r.revenue! / 1e6).toFixed(1) })).sort((a, b) => b.value - a.value).slice(0, 12);
  const riskRows = (rows ?? []).filter((r) => r.risk_score != null).map((r) => ({ name: r.navn ?? r.orgnr, value: r.risk_score! })).sort((a, b) => b.value - a.value);

  const validEq = (rows ?? []).filter((r) => r.equity_ratio != null);
  const avgEq = validEq.length ? (validEq.reduce((s, r) => s + r.equity_ratio!, 0) / validEq.length * 100).toFixed(1) : null;
  const totalRev = (rows ?? []).reduce((s, r) => s + (r.revenue ?? 0), 0);
  const validRisk = (rows ?? []).filter((r) => r.risk_score != null);
  const avgRisk = validRisk.length ? (validRisk.reduce((s, r) => s + r.risk_score!, 0) / validRisk.length).toFixed(1) : null;

  return (
    <div className="space-y-6">
      {portfolios.length > 1 && (
        <div className="flex gap-2 flex-wrap">
          {portfolios.map((p) => (
            <button key={p.id} onClick={() => setSelectedId(p.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeId === p.id ? "bg-[#2C3E50] text-white" : "bg-[#EDE8E3] text-[#8A7F74] hover:bg-[#DDD8D3]"
              }`}>{p.name}</button>
          ))}
        </div>
      )}

      {loadingRows ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-[#4A6FA5]" /></div>
      ) : !rows?.length ? (
        <div className="broker-card text-center py-10 text-sm text-[#8A7F74]">Ingen selskaper i porteføljen eller data ikke hentet ennå.</div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard label="Selskaper" value={String(rows.length)} />
            <MetricCard label="Total omsetning" value={fmtMnok(totalRev)} />
            <MetricCard label="Gj.snitt risikoscore" value={avgRisk ?? "–"} sub="av 20" />
            <MetricCard label="Gj.snitt EK-andel" value={avgEq ? `${avgEq}%` : "–"} />
          </div>

          {revenues.length > 0 && (
            <div className="broker-card">
              <h3 className="text-sm font-semibold text-[#2C3E50] mb-4">Omsetning (MNOK) — topp {revenues.length}</h3>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={revenues} margin={{ left: 0, right: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={50} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: number) => [`${v} MNOK`, "Omsetning"]} />
                  <Bar dataKey="value" fill="#4A6FA5" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {riskRows.length > 0 && (
            <div className="broker-card">
              <h3 className="text-sm font-semibold text-[#2C3E50] mb-4">Risikoscore per selskap</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={riskRows} margin={{ left: 0, right: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={50} />
                  <YAxis tick={{ fontSize: 10 }} domain={[0, 20]} />
                  <Tooltip formatter={(v: number) => [v, "Risikoscore"]} />
                  <Bar dataKey="value" fill="#C8A951" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="broker-card overflow-x-auto">
            <h3 className="text-sm font-semibold text-[#2C3E50] mb-3">Alle selskaper</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                  <th className="text-left pb-2 font-medium">Selskap</th>
                  <th className="text-right pb-2 font-medium">Omsetning</th>
                  <th className="text-right pb-2 font-medium">Egenkapital</th>
                  <th className="text-right pb-2 font-medium">EK-andel</th>
                  <th className="text-right pb-2 font-medium">Risiko</th>
                  <th className="text-right pb-2 font-medium">År</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EDE8E3]">
                {[...rows].sort((a, b) => (b.revenue ?? 0) - (a.revenue ?? 0)).map((r) => (
                  <tr key={r.orgnr} className="hover:bg-[#F9F7F4]">
                    <td className="py-2">
                      <span className="font-medium text-[#2C3E50]">{r.navn ?? r.orgnr}</span>
                      <span className="block text-xs text-[#8A7F74]">{r.orgnr}</span>
                    </td>
                    <td className="py-2 text-right text-[#8A7F74]">{fmtMnok(r.revenue)}</td>
                    <td className="py-2 text-right text-[#8A7F74]">{fmtMnok(r.equity)}</td>
                    <td className="py-2 text-right text-[#8A7F74]">{r.equity_ratio != null ? `${(r.equity_ratio * 100).toFixed(1)}%` : "–"}</td>
                    <td className="py-2 text-right">
                      {r.risk_score != null ? (
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${bandTailwindClass(bandFor(r.risk_score).label)}`}>
                          {r.risk_score}
                        </span>
                      ) : "–"}
                    </td>
                    <td className="py-2 text-right text-[#8A7F74]">{r.regnskapsår ?? "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
