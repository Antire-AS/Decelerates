"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  getCompanies, getPortfolios, getPortfolioRisk, getPremiumAnalytics,
  type Company, type PortfolioItem, type PortfolioRiskRow, type PremiumAnalytics,
} from "@/lib/api";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { Loader2 } from "lucide-react";

const COLORS = ["#4A6FA5", "#2C3E50", "#C8A951", "#7B9E87", "#9B6B6B", "#6B8FAB", "#B8860B"];

function fmt(n: number | undefined | null) {
  if (n == null) return "–";
  return new Intl.NumberFormat("nb-NO").format(Math.round(n));
}

function fmtMnok(n: number | undefined | null) {
  if (n == null) return "–";
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(1)} mrd`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(0)} MNOK`;
  return `${(n / 1e3).toFixed(0)} TNOK`;
}

function MetricCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="broker-card">
      <p className="text-xs text-[#8A7F74] font-medium mb-1">{label}</p>
      <p className="text-2xl font-bold text-[#2C3E50]">{value}</p>
      {sub && <p className="text-xs text-[#8A7F74] mt-1">{sub}</p>}
    </div>
  );
}

// ── Tab 1: Premium Analytics ──────────────────────────────────────────────────

function PremiumTab() {
  const { data, isLoading, error } = useSWR<PremiumAnalytics>("premium-analytics", getPremiumAnalytics);

  if (isLoading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-[#4A6FA5]" /></div>;
  if (error || !data) return <div className="broker-card text-center py-10 text-sm text-[#8A7F74]">Ingen policyer registrert ennå. Legg til policyer i Selskapsøk → CRM-fanen.</div>;

  const insurerData = (data.by_insurer ?? []).map((b) => ({ name: b.insurer, value: b.total_premium, count: b.count, pct: b.share_pct }));
  const productData = (data.by_product ?? []).map((b) => ({ name: b.product_type, value: b.total_premium, count: b.count, pct: b.share_pct }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Total premievolum" value={fmtMnok(data.total_premium_book)} />
        <MetricCard label="Aktive avtaler" value={String(data.active_policy_count ?? 0)} />
        <MetricCard label="Forfaller 90 dager" value={fmtMnok(data.renewals_90d_premium)} />
        <MetricCard label="Snitt per avtale" value={fmt(data.avg_premium_per_policy)} sub="kr" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {insurerData.length > 0 && (
          <div className="broker-card">
            <h3 className="text-sm font-semibold text-[#2C3E50] mb-4">Premie per forsikringsselskap</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={insurerData} layout="vertical" margin={{ left: 8, right: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v / 1e6).toFixed(0)}M`} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={110} />
                <Tooltip formatter={(v: number) => [`kr ${fmt(v)}`, "Premie"]} />
                <Bar dataKey="value" fill="#4A6FA5" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-3 space-y-1.5">
              {insurerData.map((d, i) => (
                <div key={d.name} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                    <span className="text-[#2C3E50]">{d.name}</span>
                  </div>
                  <span className="text-[#8A7F74]">{d.count} avtaler · {d.pct.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {productData.length > 0 && (
          <div className="broker-card">
            <h3 className="text-sm font-semibold text-[#2C3E50] mb-4">Premie per produkttype</h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={productData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, pct }) => `${name.slice(0, 12)} ${pct.toFixed(0)}%`} labelLine={false}>
                  {productData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v: number) => `kr ${fmt(v)}`} />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-2 space-y-1.5">
              {productData.map((d, i) => (
                <div key={d.name} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                    <span className="text-[#2C3E50]">{d.name}</span>
                  </div>
                  <span className="text-[#8A7F74]">{d.count} avtaler · {d.pct.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {(data.by_status ?? []).length > 0 && (
        <div className="broker-card">
          <h3 className="text-sm font-semibold text-[#2C3E50] mb-3">Fordeling per status</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                  <th className="text-left pb-2 font-medium">Status</th>
                  <th className="text-right pb-2 font-medium">Avtaler</th>
                  <th className="text-right pb-2 font-medium">Premie (kr)</th>
                  <th className="text-right pb-2 font-medium">Andel</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EDE8E3]">
                {data.by_status.map((s) => (
                  <tr key={s.status} className="hover:bg-[#F9F7F4]">
                    <td className="py-2 text-[#2C3E50] capitalize">{s.status}</td>
                    <td className="py-2 text-right text-[#8A7F74]">{s.count}</td>
                    <td className="py-2 text-right font-medium text-[#2C3E50]">{fmt(s.total_premium)}</td>
                    <td className="py-2 text-right text-[#8A7F74]">{s.share_pct.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Tab 2: Portfolio Financial Overview ───────────────────────────────────────

function PortfolioTab() {
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
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${r.risk_score <= 3 ? "bg-green-100 text-green-700" : r.risk_score <= 7 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>
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

// ── Tab 3: Company Comparison ─────────────────────────────────────────────────

function CompareTab() {
  const { data: companies, isLoading } = useSWR<Company[]>("companies-compare", () => getCompanies(500));
  const [selected, setSelected] = useState<Set<string>>(new Set());

  if (isLoading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-[#4A6FA5]" /></div>;
  if (!companies?.length) return <div className="broker-card text-center py-10 text-sm text-[#8A7F74]">Ingen selskaper i databasen ennå.</div>;

  const toggle = (orgnr: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(orgnr)) next.delete(orgnr);
      else if (next.size < 8) next.add(orgnr);
      return next;
    });
  };

  const selectedRows = companies.filter((c) => selected.has(c.orgnr));

  return (
    <div className="space-y-4">
      <p className="text-sm text-[#8A7F74]">Velg opptil 8 selskaper å sammenligne (klikk for å velge/fjerne).</p>
      <div className="broker-card max-h-64 overflow-y-auto space-y-1">
        {companies.map((c) => (
          <button key={c.orgnr} onClick={() => toggle(c.orgnr)}
            className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
              selected.has(c.orgnr) ? "bg-[#2C3E50] text-white" : "hover:bg-[#EDE8E3] text-[#2C3E50]"
            }`}>
            <span>{c.navn ?? c.orgnr} <span className="text-xs opacity-60">({c.orgnr})</span></span>
            {c.risk_score != null && (
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${selected.has(c.orgnr) ? "bg-white/20 text-white" : c.risk_score <= 3 ? "bg-green-100 text-green-700" : c.risk_score <= 7 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>
                {c.risk_score}
              </span>
            )}
          </button>
        ))}
      </div>

      {selectedRows.length > 0 && (
        <div className="broker-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                <th className="text-left pb-2 font-medium">Selskap</th>
                <th className="text-left pb-2 font-medium">Bransje</th>
                <th className="text-right pb-2 font-medium">Risikoscore</th>
                <th className="text-right pb-2 font-medium">Kommune</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDE8E3]">
              {selectedRows.map((c) => (
                <tr key={c.orgnr} className="hover:bg-[#F9F7F4]">
                  <td className="py-2">
                    <span className="font-medium text-[#2C3E50]">{c.navn ?? c.orgnr}</span>
                    <span className="block text-xs text-[#8A7F74]">{c.orgnr}</span>
                  </td>
                  <td className="py-2 text-[#8A7F74] text-xs">{c.naeringskode1_beskrivelse ?? "–"}</td>
                  <td className="py-2 text-right">
                    {c.risk_score != null ? (
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${c.risk_score <= 3 ? "bg-green-100 text-green-700" : c.risk_score <= 7 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>
                        {c.risk_score}
                      </span>
                    ) : "–"}
                  </td>
                  <td className="py-2 text-right text-[#8A7F74] text-xs">{c.kommune ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

const TABS = [
  { id: "premium", label: "Premieanalyse" },
  { id: "portfolio", label: "Portefølje" },
  { id: "compare", label: "Sammenlign selskaper" },
] as const;

type TabId = typeof TABS[number]["id"];

export default function FinansPage() {
  const [activeTab, setActiveTab] = useState<TabId>("premium");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Finansanalyse</h1>
        <p className="text-sm text-[#8A7F74] mt-1">
          Premievolum, porteføljeanalyse og sammenligning av selskaper
        </p>
      </div>

      <div className="flex gap-2 flex-wrap">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              activeTab === t.id ? "bg-[#2C3E50] text-white" : "bg-[#EDE8E3] text-[#8A7F74] hover:bg-[#DDD8D3]"
            }`}>{t.label}</button>
        ))}
      </div>

      {activeTab === "premium"    && <PremiumTab />}
      {activeTab === "portfolio"  && <PortfolioTab />}
      {activeTab === "compare"    && <CompareTab />}
    </div>
  );
}
