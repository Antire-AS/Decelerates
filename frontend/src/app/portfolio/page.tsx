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
import { Loader2, Plus, Sparkles, Download, BarChart2 } from "lucide-react";
import { PortfolioRiskTable } from "@/components/portfolio/PortfolioRiskTable";
import { PortfolioAlerts } from "@/components/portfolio/PortfolioAlerts";
import { PortfolioConcentration } from "@/components/portfolio/PortfolioConcentration";
import { PortfolioAnalytics } from "@/components/portfolio/PortfolioAnalytics";
import { PortfolioChat } from "@/components/portfolio/PortfolioChat";

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

      {/* ── Portfolio selector + sub-components ─────────────────────── */}
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

        {portfolioAlerts && portfolioAlerts.length > 0 && (
          <PortfolioAlerts alerts={portfolioAlerts} />
        )}

        {concentration && (
          <PortfolioConcentration concentration={concentration} />
        )}

        {portfolioRisk && portfolioRisk.length > 0 && (
          <PortfolioRiskTable
            portfolioRisk={portfolioRisk}
            portfolioName={selectedPortfolio?.name}
            removingOrgnr={removingOrgnr}
            onRemove={handleRemove}
          />
        )}

        {selectedPortfolioId && (
          <PortfolioChat
            chatQuestion={chatQuestion}
            setChatQuestion={setChatQuestion}
            chatAnswer={chatAnswer}
            chatSources={chatSources}
            chatLoading={chatLoading}
            chatErr={chatErr}
            onSubmit={handleChat}
          />
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
            {pieData.length > 0 && (
              <div className="broker-card">
                <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">Risikofordeling</h2>
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
                  <h2 className="text-sm font-semibold text-[#2C3E50]">Bransjefordeling</h2>
                  <BarChart2 className="w-4 h-4 text-[#8A7F74]" />
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
