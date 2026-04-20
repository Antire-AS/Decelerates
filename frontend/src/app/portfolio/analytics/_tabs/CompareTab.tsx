"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { Loader2 } from "lucide-react";
import { getCompanies, type Company } from "@/lib/api";
import { fmtMnok } from "./_shared";
import { useRiskConfig, bandTailwindClass } from "@/lib/useRiskConfig";

export default function CompareTab() {
  const { bandFor } = useRiskConfig();
  const { data: companies, isLoading } = useSWR<Company[]>("companies-compare", () => getCompanies(500));
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");

  if (isLoading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  if (!companies?.length) return <div className="broker-card text-center py-10 text-sm text-muted-foreground">Ingen selskaper i databasen ennå.</div>;

  const toggle = (orgnr: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(orgnr)) next.delete(orgnr);
      else if (next.size < 8) next.add(orgnr);
      return next;
    });
  };

  const filtered = companies.filter((c) =>
    !search || (c.navn ?? c.orgnr).toLowerCase().includes(search.toLowerCase())
  );
  const selectedRows = companies.filter((c) => selected.has(c.orgnr));

  const revenueChartData = selectedRows
    .filter((c) => c.omsetning != null)
    .map((c) => ({ name: c.navn ?? c.orgnr, value: +((c.omsetning! / 1e6).toFixed(1)) }))
    .sort((a, b) => b.value - a.value);

  const riskChartData = selectedRows
    .filter((c) => c.risk_score != null)
    .map((c) => ({ name: c.navn ?? c.orgnr, value: c.risk_score! }))
    .sort((a, b) => b.value - a.value);

  function exportCsv() {
    const header = "Selskap,Orgnr,Omsetning (NOK),Egenkapital (NOK),EK-andel %,Risikoscore,Bransje,Kommune,År";
    const rows = selectedRows.map((c) =>
      [
        `"${c.navn ?? c.orgnr}"`,
        c.orgnr,
        c.omsetning ?? "",
        c.sum_egenkapital ?? "",
        c.egenkapitalandel != null ? (c.egenkapitalandel * 100).toFixed(1) : "",
        c.risk_score ?? "",
        `"${c.naeringskode1_beskrivelse ?? ""}"`,
        `"${c.kommune ?? ""}"`,
        c.regnskapsår ?? "",
      ].join(",")
    );
    const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "sammenligning.csv";
    a.click();
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">Velg opptil 8 selskaper å sammenligne.</p>

      {/* Search + picker */}
      <div className="broker-card space-y-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Søk selskap…"
          className="w-full text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground placeholder:text-muted-foreground"
        />
        <div className="max-h-52 overflow-y-auto space-y-0.5">
          {filtered.map((c) => (
            <button key={c.orgnr} onClick={() => toggle(c.orgnr)}
              className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-sm transition-colors ${
                selected.has(c.orgnr) ? "bg-primary text-primary-foreground" : "hover:bg-muted text-foreground"
              }`}>
              <span>{c.navn ?? c.orgnr} <span className="text-xs opacity-60">({c.orgnr})</span></span>
              {c.risk_score != null && (
                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                  selected.has(c.orgnr) ? "bg-card/20 text-white"
                  : bandTailwindClass(bandFor(c.risk_score).label)
                }`}>{c.risk_score}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {selectedRows.length > 0 && (
        <>
          {/* Comparison table */}
          <div className="broker-card overflow-x-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-foreground">
                {selectedRows.length} selskaper valgt
              </h3>
              <button
                onClick={exportCsv}
                className="px-3 py-1 text-xs rounded-lg bg-muted text-foreground hover:bg-muted flex items-center gap-1.5"
              >
                ⬇ Eksporter CSV
              </button>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground border-b border-border">
                  <th className="text-left pb-2 font-medium">Selskap</th>
                  <th className="text-right pb-2 font-medium">Omsetning</th>
                  <th className="text-right pb-2 font-medium">Egenkapital</th>
                  <th className="text-right pb-2 font-medium">EK-andel</th>
                  <th className="text-right pb-2 font-medium">Risiko</th>
                  <th className="text-left pb-2 font-medium hidden md:table-cell">Bransje</th>
                  <th className="text-right pb-2 font-medium hidden sm:table-cell">År</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {selectedRows.map((c) => (
                  <tr key={c.orgnr} className="hover:bg-muted">
                    <td className="py-2">
                      <span className="font-medium text-foreground">{c.navn ?? c.orgnr}</span>
                      <span className="block text-xs text-muted-foreground">{c.orgnr}</span>
                    </td>
                    <td className="py-2 text-right text-muted-foreground">{fmtMnok(c.omsetning)}</td>
                    <td className="py-2 text-right text-muted-foreground">{fmtMnok(c.sum_egenkapital)}</td>
                    <td className="py-2 text-right text-muted-foreground">
                      {c.egenkapitalandel != null ? `${(c.egenkapitalandel * 100).toFixed(1)}%` : "–"}
                    </td>
                    <td className="py-2 text-right">
                      {c.risk_score != null ? (
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                          bandTailwindClass(bandFor(c.risk_score).label)
                        }`}>{c.risk_score}</span>
                      ) : "–"}
                    </td>
                    <td className="py-2 text-muted-foreground text-xs hidden md:table-cell">
                      {c.naeringskode1_beskrivelse ?? "–"}
                    </td>
                    <td className="py-2 text-right text-muted-foreground hidden sm:table-cell">
                      {c.regnskapsår ?? "–"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {revenueChartData.length > 0 && (
              <div className="broker-card">
                <h3 className="text-sm font-semibold text-foreground mb-3">Omsetning (MNOK)</h3>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={revenueChartData} margin={{ left: 0, right: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-25} textAnchor="end" height={50} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v: number) => [`${v} MNOK`, "Omsetning"]} />
                    <Bar dataKey="value" fill="#4A6FA5" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            {riskChartData.length > 0 && (
              <div className="broker-card">
                <h3 className="text-sm font-semibold text-foreground mb-3">Risikoscore</h3>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={riskChartData} margin={{ left: 0, right: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-25} textAnchor="end" height={50} />
                    <YAxis tick={{ fontSize: 10 }} domain={[0, 20]} />
                    <Tooltip formatter={(v: number) => [v, "Risikoscore"]} />
                    <Bar dataKey="value" fill="#C8A951" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
