"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import {
  getCompanies, getPortfolios, createPortfolio, portfolioChat,
  seedFullDemo, getPortfolioRisk, getPortfolioAlerts,
  getPortfolioConcentration, removePortfolioCompany, downloadPortfolioPdf,
  type Company, type PortfolioItem, type PortfolioRiskRow,
} from "@/lib/api";
import Link from "next/link";
import { Loader2, Plus, MessageSquare, Sparkles, Download, Trash2, AlertTriangle, BarChart2 } from "lucide-react";

const RISK_BANDS = [
  { label: "Lav (0–39)",      min: 0,  max: 39,  color: "#27AE60" },
  { label: "Moderat (40–69)", min: 40, max: 69,  color: "#C8A951" },
  { label: "Høy (70–100)",    min: 70, max: 100, color: "#C0392B" },
  { label: "Ukjent",          min: -1, max: -1,  color: "#C4BDB4" },
];

function band(score?: number) {
  if (score == null) return 3;
  if (score < 40) return 0;
  if (score < 70) return 1;
  return 2;
}

function fmtMnok(v?: number) {
  if (!v) return "–";
  return `${(v / 1e6).toLocaleString("nb-NO", { maximumFractionDigits: 1 })} MNOK`;
}

export default function PortfolioPage() {
  const { data: companies, isLoading } = useSWR<Company[]>(
    "companies-portfolio", () => getCompanies(200),
  );
  const { data: portfolios = [], mutate: mutatePortfolios } = useSWR<PortfolioItem[]>(
    "portfolios", getPortfolios,
  );

  const [search, setSearch]         = useState("");
  const [riskFilter, setRiskFilter] = useState<number | null>(null);
  const [analyticsTab, setAnalyticsTab] = useState<"industry" | "top-risk">("industry");

  // Portfolio management
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<number | null>(null);
  const [newPortfolioName, setNewPortfolioName]       = useState("");
  const [creating, setCreating]                       = useState(false);
  const [removingOrgnr, setRemovingOrgnr]             = useState<string | null>(null);
  const [pdfDownloading, setPdfDownloading]           = useState(false);

  // Portfolio chat
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatAnswer, setChatAnswer]     = useState<string | null>(null);
  const [chatSources, setChatSources]   = useState<string[]>([]);
  const [chatLoading, setChatLoading]   = useState(false);
  const [chatErr, setChatErr]           = useState<string | null>(null);

  // Demo seed
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState<string | null>(null);

  // Portfolio-specific data (lazy)
  const { data: portfolioRisk, mutate: mutateRisk } = useSWR<PortfolioRiskRow[]>(
    selectedPortfolioId ? `portfolio-risk-${selectedPortfolioId}` : null,
    () => getPortfolioRisk(selectedPortfolioId!),
  );
  const { data: portfolioAlerts } = useSWR(
    selectedPortfolioId ? `portfolio-alerts-${selectedPortfolioId}` : null,
    () => getPortfolioAlerts(selectedPortfolioId!),
  );
  const { data: concentration } = useSWR(
    selectedPortfolioId ? `portfolio-concentration-${selectedPortfolioId}` : null,
    () => getPortfolioConcentration(selectedPortfolioId!),
  );

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
      const p = await createPortfolio(newPortfolioName.trim());
      setNewPortfolioName("");
      mutatePortfolios();
      setSelectedPortfolioId(p.id);
    } finally { setCreating(false); }
  }

  async function handleChat() {
    if (!selectedPortfolioId || !chatQuestion.trim()) return;
    setChatLoading(true); setChatErr(null); setChatAnswer(null);
    try {
      const r = await portfolioChat(selectedPortfolioId, chatQuestion);
      setChatAnswer(r.answer);
      setChatSources(r.sources ?? []);
    } catch (e) { setChatErr(String(e)); }
    finally { setChatLoading(false); }
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

  async function handleRemove(orgnr: string) {
    if (!selectedPortfolioId) return;
    setRemovingOrgnr(orgnr);
    try {
      await removePortfolioCompany(selectedPortfolioId, orgnr);
      mutateRisk();
    } finally { setRemovingOrgnr(null); }
  }

  async function handleDownloadPdf() {
    if (!selectedPortfolioId) return;
    const p = portfolios.find((x) => x.id === selectedPortfolioId);
    setPdfDownloading(true);
    try {
      await downloadPortfolioPdf(selectedPortfolioId, p?.name ?? "rapport");
    } finally { setPdfDownloading(false); }
  }

  const selectedPortfolio = portfolios.find((p) => p.id === selectedPortfolioId);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-[#2C3E50]">Portefølje</h1>
          <p className="text-sm text-[#8A7F74] mt-1">Oversikt over alle kunder og risikofordeling</p>
        </div>
        <button onClick={handleSeedDemo} disabled={seeding}
          className="flex items-center gap-2 px-3 py-2 text-xs rounded-lg border border-[#D4C9B8] text-[#8A7F74] hover:bg-[#EDE8E3] disabled:opacity-50">
          {seeding ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
          Seed demo-data
        </button>
      </div>

      {seedMsg && <div className="broker-card text-xs text-[#2C3E50]">{seedMsg}</div>}

      {/* ── Portfolio selector + chat ────────────────────────────────── */}
      <div className="broker-card space-y-4">
        <h2 className="text-sm font-semibold text-[#2C3E50] flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-[#4A6FA5]" /> Navngitt portefølje
        </h2>

        <div className="flex flex-wrap gap-2 items-end">
          {portfolios.length > 0 && (
            <div>
              <label className="label-xs">Velg portefølje</label>
              <select value={selectedPortfolioId ?? ""}
                onChange={(e) => setSelectedPortfolioId(e.target.value ? Number(e.target.value) : null)}
                className="input-sm">
                <option value="">– velg –</option>
                {portfolios.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
          )}
          <div>
            <label className="label-xs">Opprett ny portefølje</label>
            <div className="flex gap-1.5">
              <input type="text" value={newPortfolioName} onChange={(e) => setNewPortfolioName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreatePortfolio()}
                placeholder="Navn…" className="input-sm w-36" />
              <button onClick={handleCreatePortfolio} disabled={creating || !newPortfolioName.trim()}
                className="px-3 py-1.5 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50 flex items-center gap-1">
                {creating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                Opprett
              </button>
            </div>
          </div>

          {selectedPortfolioId && (
            <button onClick={handleDownloadPdf} disabled={pdfDownloading}
              className="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-[#D4C9B8] text-[#8A7F74] hover:bg-[#EDE8E3] disabled:opacity-50">
              {pdfDownloading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
              Last ned PDF-rapport
            </button>
          )}
        </div>

        {/* Alerts */}
        {portfolioAlerts && portfolioAlerts.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-[#2C3E50] flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500" /> Varsler
            </p>
            {portfolioAlerts.map((a, i) => (
              <div key={i} className={`flex items-start gap-2 text-xs rounded-lg px-3 py-2 ${
                a.severity === "high" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>
                <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                <span><strong>{a.navn ?? a.orgnr}</strong>: {a.message}</span>
              </div>
            ))}
          </div>
        )}

        {/* Concentration */}
        {concentration && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {(["industry", "geography", "size"] as const).map((key) => {
              const items = concentration[key] ?? [];
              const labels: Record<string, string> = { industry: "Bransje", geography: "Geografi", size: "Størrelse" };
              return (
                <div key={key}>
                  <p className="text-xs font-semibold text-[#2C3E50] mb-1">{labels[key]}</p>
                  <div className="space-y-1">
                    {items.slice(0, 5).map((item: { label: string; count: number }) => (
                      <div key={item.label} className="flex justify-between text-xs">
                        <span className="text-[#8A7F74] truncate max-w-[120px]">{item.label}</span>
                        <span className="font-medium text-[#2C3E50]">{item.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Portfolio risk table with remove */}
        {portfolioRisk && portfolioRisk.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-[#2C3E50] mb-2">
              Selskaper i «{selectedPortfolio?.name}» ({portfolioRisk.length})
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[#8A7F74] border-b border-[#EDE8E3]">
                    <th className="text-left pb-1.5 font-medium">Selskap</th>
                    <th className="text-right pb-1.5 font-medium hidden sm:table-cell">Omsetning</th>
                    <th className="text-right pb-1.5 font-medium hidden md:table-cell">Egenkapital</th>
                    <th className="text-right pb-1.5 font-medium hidden md:table-cell">EK-andel</th>
                    <th className="text-right pb-1.5 font-medium">Risiko</th>
                    <th className="w-8 pb-1.5"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#EDE8E3]">
                  {portfolioRisk.map((r) => (
                    <tr key={r.orgnr} className="hover:bg-[#F9F7F4]">
                      <td className="py-1.5">
                        <Link href={`/search/${r.orgnr}`} className="font-medium text-[#4A6FA5] hover:underline">
                          {r.navn ?? r.orgnr}
                        </Link>
                      </td>
                      <td className="py-1.5 text-right text-[#8A7F74] hidden sm:table-cell">
                        {fmtMnok(r.revenue)}
                      </td>
                      <td className="py-1.5 text-right text-[#8A7F74] hidden md:table-cell">
                        {fmtMnok(r.equity)}
                      </td>
                      <td className="py-1.5 text-right text-[#8A7F74] hidden md:table-cell">
                        {r.equity_ratio != null ? `${(r.equity_ratio * 100).toFixed(1)}%` : "–"}
                      </td>
                      <td className="py-1.5 text-right">
                        {r.risk_score != null ? (
                          <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                            style={{
                              background: RISK_BANDS[band(r.risk_score)].color + "20",
                              color: RISK_BANDS[band(r.risk_score)].color,
                            }}>{r.risk_score}</span>
                        ) : <span className="text-[#8A7F74]">–</span>}
                      </td>
                      <td className="py-1.5 text-right">
                        <button onClick={() => handleRemove(r.orgnr)}
                          disabled={removingOrgnr === r.orgnr}
                          className="text-[#C4BDB4] hover:text-red-500 disabled:opacity-50">
                          {removingOrgnr === r.orgnr
                            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            : <Trash2 className="w-3.5 h-3.5" />}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Portfolio chat */}
        {selectedPortfolioId && (
          <div className="space-y-3 pt-2 border-t border-[#EDE8E3]">
            <p className="text-xs font-semibold text-[#2C3E50] flex items-center gap-1.5">
              <MessageSquare className="w-3.5 h-3.5" /> Portefølje-chat
            </p>
            <div className="flex gap-2">
              <input type="text" value={chatQuestion} onChange={(e) => setChatQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleChat()}
                placeholder="F.eks. «Hvilke selskaper har lavest egenkapitalandel?»"
                className="flex-1 px-3 py-2 text-sm border border-[#EDE8E3] rounded-lg text-[#2C3E50] placeholder-[#C8BEB4] focus:outline-none focus:border-[#2C3E50]" />
              <button onClick={handleChat} disabled={chatLoading || !chatQuestion.trim()}
                className="px-4 py-2 rounded-lg bg-[#4A6FA5] text-white text-sm font-medium hover:bg-[#3d5e8e] disabled:opacity-50 flex items-center gap-1">
                {chatLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <MessageSquare className="w-4 h-4" />}
                Spør
              </button>
            </div>
            {chatErr && <p className="text-xs text-red-600">{chatErr}</p>}
            {chatAnswer && (
              <div className="bg-[#F9F7F4] rounded-lg p-3 space-y-2">
                <p className="text-xs text-[#2C3E50] whitespace-pre-wrap">{chatAnswer}</p>
                {chatSources.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {chatSources.map((s) => (
                      <Link key={s} href={`/search/${s}`}
                        className="text-xs px-2 py-0.5 rounded-full bg-[#EDE8E3] text-[#4A6FA5] hover:underline">{s}</Link>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {!selectedPortfolioId && portfolios.length === 0 && (
          <p className="text-xs text-[#8A7F74]">
            Opprett en portefølje og legg til selskaper via selskapsprofilen for å bruke chatten.
          </p>
        )}
      </div>

      {/* ── Summary cards ─────────────────────────────────────────────── */}
      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="broker-card h-20 animate-pulse bg-[#EDE8E3]" />)}
        </div>
      )}

      {companies && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="broker-card">
              <p className="text-xs text-[#8A7F74] font-medium mb-1">Totalt kunder</p>
              <p className="text-2xl font-bold text-[#2C3E50]">{companies.length}</p>
            </div>
            {RISK_BANDS.slice(0, 3).map((b, i) => {
              const count = companies.filter((c) => band(c.risk_score) === i).length;
              return (
                <div key={b.label}
                  className="broker-card cursor-pointer hover:bg-[#F9F7F4]"
                  onClick={() => setRiskFilter(riskFilter === i ? null : i)}>
                  <p className="text-xs font-medium mb-1" style={{ color: b.color }}>{b.label}</p>
                  <p className="text-2xl font-bold text-[#2C3E50]">{count}</p>
                  {riskFilter === i && <p className="text-xs text-[#8A7F74] mt-0.5">Filtrert ↑</p>}
                </div>
              );
            })}
          </div>

          {/* ── Analytics charts ──────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Risk distribution pie */}
            {pieData.length > 0 && (
              <div className="broker-card">
                <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">Risikofordeling</h2>
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}
                      label={({ name, percent }) => `${name.split(" ")[0]} ${(percent * 100).toFixed(0)}%`}>
                      {pieData.map((d, i) => <Cell key={i} fill={d.color} />)}
                    </Pie>
                    <Tooltip formatter={(v: number) => [`${v} selskaper`]} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Industry breakdown */}
            {industryData.length > 0 && (
              <div className="broker-card">
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="text-sm font-semibold text-[#2C3E50]">Bransjefordeling</h2>
                  <BarChart2 className="w-4 h-4 text-[#8A7F74]" />
                </div>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={industryData} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 9 }} />
                    <Tooltip formatter={(v: number) => [`${v} selskaper`]} />
                    <Bar dataKey="count" name="Selskaper" fill="#4A6FA5" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Top 15 risk chart */}
          {top15Risk.length > 0 && (
            <div className="broker-card">
              <div className="flex items-center gap-2 mb-3">
                <button onClick={() => setAnalyticsTab("industry")}
                  className={`text-xs px-2.5 py-1 rounded-lg ${analyticsTab === "industry" ? "bg-[#2C3E50] text-white" : "text-[#8A7F74] hover:bg-[#EDE8E3]"}`}>
                  Bransje
                </button>
                <button onClick={() => setAnalyticsTab("top-risk")}
                  className={`text-xs px-2.5 py-1 rounded-lg ${analyticsTab === "top-risk" ? "bg-[#2C3E50] text-white" : "text-[#8A7F74] hover:bg-[#EDE8E3]"}`}>
                  Top 15 risiko
                </button>
              </div>
              {analyticsTab === "top-risk" && (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={top15Risk} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 10 }} domain={[0, 100]} />
                    <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 9 }} />
                    <Tooltip formatter={(v: number) => [`${v} / 100`]} />
                    <Bar dataKey="score" name="Risikoscore" fill="#C0392B" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
              {analyticsTab === "industry" && (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={industryData} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 9 }} />
                    <Tooltip formatter={(v: number) => [`${v} selskaper`]} />
                    <Bar dataKey="count" name="Selskaper" fill="#4A6FA5" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          )}

          {/* Company table */}
          <div className="broker-card">
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              <input value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="Søk selskap…"
                className="flex-1 min-w-0 px-3 py-1.5 text-sm border border-[#D4C9B8] rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]" />
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
                        <span className="block text-xs text-[#8A7F74] font-normal">{c.orgnr}</span>
                      </td>
                      <td className="py-2 text-xs text-[#8A7F74] max-w-[180px] truncate hidden md:table-cell">
                        {c.naeringskode1_beskrivelse ?? "–"}
                      </td>
                      <td className="py-2 text-xs text-[#8A7F74] hidden lg:table-cell">{c.kommune ?? "–"}</td>
                      <td className="py-2 text-right">
                        {c.risk_score != null ? (
                          <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                            style={{
                              background: RISK_BANDS[band(c.risk_score)].color + "20",
                              color: RISK_BANDS[band(c.risk_score)].color,
                            }}>{c.risk_score}</span>
                        ) : <span className="text-xs text-[#8A7F74]">–</span>}
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
          <p className="text-sm text-[#8A7F74]">Ingen selskaper i databasen. Trykk «Seed demo-data» for å komme i gang.</p>
        </div>
      )}
    </div>
  );
}
