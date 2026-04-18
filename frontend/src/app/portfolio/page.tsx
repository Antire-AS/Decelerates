"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import {
  getCompanies, getPortfolios, createPortfolio, seedFullDemo,
  type Company, type PortfolioItem,
} from "@/lib/api";
import { useRiskConfig, UNKNOWN_BAND } from "@/lib/useRiskConfig";
import Link from "next/link";
import { Loader2, Plus, ChevronRight, BarChart2 } from "lucide-react";
import { PortfolioAnalytics } from "@/components/portfolio/PortfolioAnalytics";

export default function PortfolioPage() {
  const { data: companies, isLoading } = useSWR<Company[]>(
    "companies-portfolio", () => getCompanies(200),
  );
  const { data: portfolios = [], mutate: mutatePortfolios } = useSWR<PortfolioItem[]>(
    "portfolios", getPortfolios,
  );
  const { bands, bandIndexFor } = useRiskConfig();
  const RISK_BANDS = useMemo(() => [...bands, UNKNOWN_BAND], [bands]);
  const band = bandIndexFor;

  const [search, setSearch]         = useState("");
  const [riskFilter, setRiskFilter] = useState<number | null>(null);
  const [analyticsTab, setAnalyticsTab] = useState<"industry" | "top-risk">("industry");

  const [newPortfolioName, setNewPortfolioName] = useState("");
  const [creating, setCreating]                 = useState(false);

  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState<string | null>(null);

  const filtered = useMemo(() => {
    if (!companies) return [];
    return companies.filter((c) => {
      const matchSearch = !search || (c.navn ?? c.orgnr).toLowerCase().includes(search.toLowerCase());
      const matchRisk   = riskFilter === null || band(c.risk_score) === riskFilter;
      return matchSearch && matchRisk;
    });
  }, [companies, search, riskFilter, band]);

  const pieData = useMemo(() => {
    if (!companies) return [];
    const counts = new Array(RISK_BANDS.length).fill(0);
    for (const c of companies) counts[band(c.risk_score)]++;
    return RISK_BANDS.map((b, i) => ({ name: b.label, value: counts[i], color: b.color })).filter((d: { value: number }) => d.value > 0);
  }, [companies, RISK_BANDS, band]);

  const industryData = useMemo(() => {
    if (!companies) return [];
    const map = new Map<string, number>();
    for (const c of companies) {
      const k = c.naeringskode1_beskrivelse?.slice(0, 30) ?? "Ukjent";
      map.set(k, (map.get(k) ?? 0) + 1);
    }
    return [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([name, count]) => ({ name, count }));
  }, [companies]);

  const top15Risk = useMemo(() => {
    if (!companies) return [];
    return [...companies]
      .filter((c) => c.risk_score != null)
      .sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))
      .slice(0, 15)
      .map((c) => ({ name: (c.navn ?? c.orgnr).slice(0, 22), score: c.risk_score, orgnr: c.orgnr }));
  }, [companies]);

  async function handleCreatePortfolio() {
    if (!newPortfolioName.trim()) return;
    setCreating(true);
    try {
      await createPortfolio(newPortfolioName.trim());
      setNewPortfolioName("");
      mutatePortfolios();
    } finally { setCreating(false); }
  }

  async function handleSeedDemo() {
    setSeeding(true); setSeedMsg(null);
    try {
      const r = await seedFullDemo();
      setSeedMsg(r.message);
      mutatePortfolios();
    } catch (e) { setSeedMsg(`Feil: ${String(e)}`); }
    finally { setSeeding(false); }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Portefølje</h1>
          <p className="text-sm text-muted-foreground mt-1">Oversikt over alle kunder og risikofordeling</p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/portfolio/analytics"
            className="flex items-center gap-1.5 px-3 py-2 text-xs rounded-lg border border-[#C5D0E8] text-[#4A6FA5] bg-[#F0F4FB] hover:bg-[#E0E8F5]">
            <BarChart2 className="w-3 h-3" />
            Analyse
          </Link>
          <button onClick={handleSeedDemo} disabled={seeding}
            className="flex items-center gap-2 px-3 py-2 text-xs rounded-lg border border-input text-muted-foreground hover:bg-muted disabled:opacity-50">
            {seeding ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
            Seed demo-data
          </button>
        </div>
      </div>

      {seedMsg && <div className="broker-card text-xs text-foreground">{seedMsg}</div>}

      {/* ── Named portfolios ── */}
      <div className="broker-card space-y-4">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-sm font-semibold text-foreground">Navngitte porteføljer</h2>
          <div className="flex gap-1.5">
            <input
              type="text"
              value={newPortfolioName}
              onChange={(e) => setNewPortfolioName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreatePortfolio()}
              placeholder="Nytt navn…"
              className="input-sm w-36"
            />
            <button
              onClick={handleCreatePortfolio}
              disabled={creating || !newPortfolioName.trim()}
              className="px-3 py-1.5 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50 flex items-center gap-1"
            >
              {creating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
              Opprett
            </button>
          </div>
        </div>

        {portfolios.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Ingen porteføljer ennå. Opprett en for å gruppere selskaper og bruke AI-chat.
          </p>
        ) : (
          <div className="space-y-1.5">
            {portfolios.map((p) => (
              <Link
                key={p.id}
                href={`/portfolio/${p.id}`}
                className="flex items-center justify-between px-3 py-2.5 rounded-lg border border-border hover:bg-[#F9F7F4] hover:border-[#C5D8F0] transition-colors group"
              >
                <div>
                  <p className="text-sm font-medium text-foreground group-hover:text-[#4A6FA5]">{p.name}</p>
                  {p.description && (
                    <p className="text-xs text-muted-foreground mt-0.5">{p.description}</p>
                  )}
                </div>
                <ChevronRight className="w-4 h-4 text-[#C4BDB4] group-hover:text-[#4A6FA5]" />
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* ── Summary metrics ── */}
      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="broker-card h-20 animate-pulse bg-muted" />)}
        </div>
      )}

      {companies && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="broker-card">
              <p className="text-xs text-muted-foreground font-medium mb-1">Totalt kunder</p>
              <p className="text-2xl font-bold text-foreground">{companies.length}</p>
            </div>
            {RISK_BANDS.slice(0, -1).map((b, i) => {
              const count = companies.filter((c) => band(c.risk_score) === i).length;
              return (
                <div key={b.label}
                  className="broker-card cursor-pointer hover:bg-[#F9F7F4]"
                  onClick={() => setRiskFilter(riskFilter === i ? null : i)}>
                  <p className="text-xs font-medium mb-1" style={{ color: b.color }}>{b.label}</p>
                  <p className="text-2xl font-bold text-foreground">{count}</p>
                  {riskFilter === i && <p className="text-xs text-muted-foreground mt-0.5">Filtrert ↑</p>}
                </div>
              );
            })}
          </div>

          {/* ── Analytics charts ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {pieData.length > 0 && (
              <div className="broker-card">
                <h2 className="text-sm font-semibold text-foreground mb-3">Risikofordeling</h2>
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}
                      label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
                      labelLine={false}>
                      {pieData.map((d, i) => <Cell key={i} fill={d.color} />)}
                    </Pie>
                    <Tooltip formatter={(v: number) => [`${v} selskaper`]} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}

            {industryData.length > 0 && (
              <div className="broker-card">
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="text-sm font-semibold text-foreground">Bransjefordeling</h2>
                  <BarChart2 className="w-4 h-4 text-muted-foreground" />
                </div>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={industryData} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 9 }} />
                    <Tooltip formatter={(v: number) => [`${v} selskaper`]} />
                    <Bar dataKey="count" name="Selskaper" fill="#4A6FA5" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {top15Risk.length > 0 && (
            <PortfolioAnalytics
              industryData={industryData}
              top15Risk={top15Risk}
              analyticsTab={analyticsTab}
              setAnalyticsTab={setAnalyticsTab}
            />
          )}

          {/* ── Company table ── */}
          <div className="broker-card">
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              <input value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="Søk selskap…"
                className="flex-1 min-w-0 px-3 py-1.5 text-sm border border-input rounded-lg focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5]" />
              {riskFilter !== null && (
                <button onClick={() => setRiskFilter(null)}
                  className="text-xs px-2.5 py-1 rounded-full bg-muted text-muted-foreground hover:bg-[#DDD8D3]">
                  Nullstill filter ×
                </button>
              )}
              <span className="text-xs text-muted-foreground">{filtered.length} selskaper</span>
            </div>

            {filtered.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-6">Ingen selskaper matcher søket.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-muted-foreground border-b border-border">
                    <th className="text-left pb-2 font-medium">Selskap</th>
                    <th className="text-left pb-2 font-medium hidden md:table-cell">Bransje</th>
                    <th className="text-left pb-2 font-medium hidden lg:table-cell">Kommune</th>
                    <th className="text-right pb-2 font-medium">Risiko</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#EDE8E3]">
                  {filtered.map((c) => (
                    <tr key={c.orgnr} className="hover:bg-[#F9F7F4]">
                      <td className="py-2">
                        <Link href={`/search/${c.orgnr}`} className="font-medium text-[#4A6FA5] hover:underline">
                          {c.navn ?? c.orgnr}
                        </Link>
                        <span className="block text-xs text-muted-foreground font-normal">{c.orgnr}</span>
                      </td>
                      <td className="py-2 text-xs text-muted-foreground max-w-[180px] truncate hidden md:table-cell">
                        {c.naeringskode1_beskrivelse ?? "–"}
                      </td>
                      <td className="py-2 text-xs text-muted-foreground hidden lg:table-cell">{c.kommune ?? "–"}</td>
                      <td className="py-2 text-right">
                        {c.risk_score != null ? (
                          <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                            style={{
                              background: RISK_BANDS[band(c.risk_score)].color + "20",
                              color: RISK_BANDS[band(c.risk_score)].color,
                            }}>{c.risk_score}</span>
                        ) : <span className="text-xs text-muted-foreground">–</span>}
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
          <p className="text-sm text-muted-foreground">Ingen selskaper i databasen ennå. Demo-data lastes automatisk ved oppstart.</p>
        </div>
      )}
    </div>
  );
}
