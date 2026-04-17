"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import Link from "next/link";
import { Search, Plus, Loader2, CheckCircle } from "lucide-react";
import {
  getCompanies,
  getPortfolios,
  addCompanyToPortfolio,
  type Company,
  type PortfolioItem,
} from "@/lib/api";
import { useRiskConfig } from "@/lib/useRiskConfig";

export default function ProspectingPage() {
  const { bands, bandFor } = useRiskConfig();
  const RISK_BANDS = useMemo(
    () => bands.map(b => ({ ...b, label: `${b.label} (${b.min}–${b.max})` })),
    [bands],
  );
  const riskColor = (score?: number | null) => bandFor(score).color;

  const [search, setSearch]         = useState("");
  const [industryFilter, setIndustry] = useState("");
  const [municipalityFilter, setMunicipality] = useState("");
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [sortBy, setSortBy]         = useState<"risk" | "revenue" | "name">("risk");

  // Server-side numeric ranges (Streamlit parity: revenue 0–2000 MNOK, risk 0–20)
  const [minRevenueMnok, setMinRevenueMnok] = useState(0);
  const [maxRevenueMnok, setMaxRevenueMnok] = useState(2000);
  const [minRiskScore,  setMinRiskScore]    = useState(0);
  const [maxRiskScore,  setMaxRiskScore]    = useState(20);

  // Re-fetch when server-side filters change. Client-side filters (search, kommune, industry,
  // categorical risk band) still run in-memory below for instant feedback.
  const fetchKey = `prosp-${minRevenueMnok}-${maxRevenueMnok}-${minRiskScore}-${maxRiskScore}-${sortBy}`;
  const sortByApi = sortBy === "name" ? "navn" : sortBy === "revenue" ? "revenue" : "risk_score";
  const { data: companies, isLoading } = useSWR<Company[]>(
    fetchKey,
    () => getCompanies(500, sortByApi, {
      min_revenue: minRevenueMnok > 0 ? minRevenueMnok * 1_000_000 : undefined,
      max_revenue: maxRevenueMnok < 2000 ? maxRevenueMnok * 1_000_000 : undefined,
      min_risk: minRiskScore > 0 ? minRiskScore : undefined,
      max_risk: maxRiskScore < 20 ? maxRiskScore : undefined,
    }),
  );
  const { data: portfolios = [] } = useSWR<PortfolioItem[]>("portfolios-prosp", getPortfolios);

  // portfolio-add state
  const [selectedOrgnr, setSelectedOrgnr]   = useState<string | null>(null);
  const [addingTo, setAddingTo]             = useState<number | null>(null);
  const [addedSet, setAddedSet]             = useState<Set<string>>(new Set());
  const [addErr, setAddErr]                 = useState<string | null>(null);

  // Unique industry options from data
  const industries = useMemo(() => {
    if (!companies) return [];
    const set = new Set<string>();
    for (const c of companies) {
      if (c.naeringskode1_beskrivelse) set.add(c.naeringskode1_beskrivelse);
    }
    return [...set].sort();
  }, [companies]);

  // Map select-option keys to band indices via the live bands array
  const BAND_KEY_TO_INDEX: Record<string, number> = useMemo(() => ({
    low:      0,
    mid:      1,
    high:     2,
    veryhigh: 3,
  }), []);

  const filtered = useMemo(() => {
    if (!companies) return [];
    return companies
      .filter((c) => {
        const name = (c.navn ?? c.orgnr).toLowerCase();
        const matchSearch = !search || name.includes(search.toLowerCase()) || c.orgnr.includes(search);
        const matchIndustry = !industryFilter || c.naeringskode1_beskrivelse === industryFilter;
        const matchMun = !municipalityFilter || (c.kommune ?? "").toLowerCase().includes(municipalityFilter.toLowerCase());
        const matchRisk =
          riskFilter === "all" ? true
          : riskFilter === "unknown" ? c.risk_score == null
          : (() => {
              const targetIdx = BAND_KEY_TO_INDEX[riskFilter];
              if (targetIdx === undefined || c.risk_score == null) return false;
              const b = bands[targetIdx];
              return b != null && c.risk_score >= b.min && c.risk_score <= b.max;
            })();
        return matchSearch && matchIndustry && matchMun && matchRisk;
      })
      .sort((a, b) => {
        if (sortBy === "risk")    return (b.risk_score ?? -1) - (a.risk_score ?? -1);
        if (sortBy === "revenue") return (b.omsetning ?? 0) - (a.omsetning ?? 0);
        return (a.navn ?? a.orgnr).localeCompare(b.navn ?? b.orgnr, "nb");
      });
  }, [companies, search, industryFilter, municipalityFilter, riskFilter, sortBy, bands, BAND_KEY_TO_INDEX]);

  async function handleAdd(portfolioId: number) {
    if (!selectedOrgnr) return;
    setAddingTo(portfolioId);
    setAddErr(null);
    try {
      await addCompanyToPortfolio(portfolioId, selectedOrgnr);
      setAddedSet((prev) => new Set([...prev, `${portfolioId}-${selectedOrgnr}`]));
      setSelectedOrgnr(null);
    } catch (e) {
      setAddErr(String(e));
    } finally {
      setAddingTo(null);
    }
  }

  function fmtMnok(n: number | null | undefined) {
    if (n == null) return "–";
    if (n >= 1e9) return `${(n / 1e9).toFixed(1)} mrd`;
    if (n >= 1e6) return `${(n / 1e6).toFixed(0)} MNOK`;
    return `${(n / 1e3).toFixed(0)} TNOK`;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Prospektering</h1>
        <p className="text-sm text-[#8A7F74] mt-1">
          Utforsk alle selskaper i databasen og legg til i en portefølje
        </p>
      </div>

      {/* ── Filters ── */}
      <div className="broker-card space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#C4BDB4]" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Navn eller orgnr…"
              className="w-full pl-9 pr-3 py-1.5 text-sm border border-[#D4C9B8] rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] text-[#2C3E50]"
            />
          </div>

          <select
            value={industryFilter}
            onChange={(e) => setIndustry(e.target.value)}
            className="text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 text-[#2C3E50] focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
          >
            <option value="">Alle bransjer</option>
            {industries.map((ind) => (
              <option key={ind} value={ind}>{ind.slice(0, 50)}</option>
            ))}
          </select>

          <input
            value={municipalityFilter}
            onChange={(e) => setMunicipality(e.target.value)}
            placeholder="Kommune…"
            className="text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 text-[#2C3E50] focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
          />

          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 text-[#2C3E50] focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
          >
            <option value="all">Alle risikonivåer</option>
            {(["low", "mid", "high", "veryhigh"] as const).map((key, i) => {
              const b = bands[i];
              return b ? (
                <option key={key} value={key}>{b.label} ({b.min}–{b.max})</option>
              ) : null;
            })}
            <option value="unknown">Ukjent</option>
          </select>
        </div>

        {/* Numeric range sliders — server-side filters */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-[#EDE8E3]">
          <div>
            <div className="flex justify-between items-baseline mb-1">
              <p className="text-xs font-medium text-[#8A7F74]">Omsetning (MNOK)</p>
              <span className="text-xs text-[#2C3E50] font-mono">{minRevenueMnok}–{maxRevenueMnok}</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="range" min={0} max={2000} step={10}
                value={minRevenueMnok}
                onChange={(e) => setMinRevenueMnok(Math.min(Number(e.target.value), maxRevenueMnok))}
                className="flex-1 accent-[#4A6FA5]"
              />
              <input
                type="range" min={0} max={2000} step={10}
                value={maxRevenueMnok}
                onChange={(e) => setMaxRevenueMnok(Math.max(Number(e.target.value), minRevenueMnok))}
                className="flex-1 accent-[#4A6FA5]"
              />
            </div>
          </div>
          <div>
            <div className="flex justify-between items-baseline mb-1">
              <p className="text-xs font-medium text-[#8A7F74]">Risikoscore (0–20)</p>
              <span className="text-xs text-[#2C3E50] font-mono">{minRiskScore}–{maxRiskScore}</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="range" min={0} max={20} step={1}
                value={minRiskScore}
                onChange={(e) => setMinRiskScore(Math.min(Number(e.target.value), maxRiskScore))}
                className="flex-1 accent-[#4A6FA5]"
              />
              <input
                type="range" min={0} max={20} step={1}
                value={maxRiskScore}
                onChange={(e) => setMaxRiskScore(Math.max(Number(e.target.value), minRiskScore))}
                className="flex-1 accent-[#4A6FA5]"
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs text-[#8A7F74]">Sorter etter:</span>
          {(["risk", "revenue", "name"] as const).map((s) => (
            <button key={s} onClick={() => setSortBy(s)}
              className={`px-3 py-1 text-xs rounded-lg font-medium transition-colors ${
                sortBy === s ? "bg-[#2C3E50] text-white" : "bg-[#EDE8E3] text-[#8A7F74] hover:bg-[#DDD8D3]"
              }`}>
              {s === "risk" ? "Risiko" : s === "revenue" ? "Omsetning" : "Navn"}
            </button>
          ))}
          <span className="text-xs text-[#8A7F74] ml-auto">
            {isLoading ? "Laster…" : `${filtered.length} selskaper`}
          </span>
        </div>
      </div>

      {/* Risk band quick-filter pills */}
      <div className="flex gap-2 flex-wrap">
        {RISK_BANDS.map((b) => {
          const count = (companies ?? []).filter((c) =>
            c.risk_score != null && c.risk_score >= b.min && c.risk_score <= b.max
          ).length;
          const key =
            b.min === 0  ? "low" :
            b.min === 4  ? "mid" :
            b.min === 8  ? "high" : "veryhigh";
          const active = riskFilter === key;
          return (
            <button key={b.label}
              onClick={() => setRiskFilter(active ? "all" : key)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
              style={{
                borderColor: b.color,
                color: active ? "white" : b.color,
                background: active ? b.color : "transparent",
              }}>
              <span className="w-2 h-2 rounded-full" style={{ background: active ? "white" : b.color }} />
              {b.label} — {count}
            </button>
          );
        })}
      </div>

      {/* ── Portfolio picker modal ── */}
      {selectedOrgnr && portfolios.length > 0 && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setSelectedOrgnr(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full p-6 space-y-4"
            onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-[#2C3E50]">Legg til i portefølje</h3>
            <p className="text-xs text-[#8A7F74]">Velg hvilken portefølje du vil legge til {selectedOrgnr}:</p>
            {addErr && <p className="text-xs text-red-600">{addErr}</p>}
            <div className="space-y-2">
              {portfolios.map((p) => {
                const key = `${p.id}-${selectedOrgnr}`;
                const done = addedSet.has(key);
                return (
                  <button key={p.id}
                    onClick={() => !done && handleAdd(p.id)}
                    disabled={addingTo === p.id || done}
                    className="w-full flex items-center justify-between px-4 py-2.5 rounded-lg border border-[#EDE8E3] hover:border-[#4A6FA5] hover:bg-[#F0F4FB] transition-colors disabled:opacity-60 text-sm text-[#2C3E50]"
                  >
                    <span>{p.name}</span>
                    {addingTo === p.id ? <Loader2 className="w-4 h-4 animate-spin text-[#4A6FA5]" />
                      : done ? <CheckCircle className="w-4 h-4 text-green-500" />
                      : <Plus className="w-4 h-4 text-[#4A6FA5]" />}
                  </button>
                );
              })}
            </div>
            <button onClick={() => setSelectedOrgnr(null)}
              className="w-full text-xs text-[#8A7F74] hover:text-[#2C3E50] pt-1">
              Avbryt
            </button>
          </div>
        </div>
      )}

      {/* ── Company table ── */}
      {isLoading ? (
        <div className="broker-card space-y-3">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="h-8 rounded animate-pulse bg-[#EDE8E3]" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="broker-card text-center py-10">
          <p className="text-sm text-[#8A7F74]">Ingen selskaper matcher filtrene.</p>
        </div>
      ) : (
        <div className="broker-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                <th className="text-left pb-2 font-medium">Selskap</th>
                <th className="text-left pb-2 font-medium hidden md:table-cell">Bransje</th>
                <th className="text-left pb-2 font-medium hidden lg:table-cell">Kommune</th>
                <th className="text-right pb-2 font-medium hidden sm:table-cell">Omsetning</th>
                <th className="text-right pb-2 font-medium">Risiko</th>
                <th className="text-right pb-2 font-medium">Handling</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDE8E3]">
              {filtered.map((c) => (
                <tr key={c.orgnr} className="hover:bg-[#F9F7F4]">
                  <td className="py-2 pr-3">
                    <Link href={`/search/${c.orgnr}`}
                      className="font-medium text-[#4A6FA5] hover:underline">
                      {c.navn ?? c.orgnr}
                    </Link>
                    <span className="block text-xs text-[#8A7F74]">{c.orgnr}</span>
                  </td>
                  <td className="py-2 text-xs text-[#8A7F74] max-w-[180px] truncate hidden md:table-cell">
                    {c.naeringskode1_beskrivelse ?? "–"}
                  </td>
                  <td className="py-2 text-xs text-[#8A7F74] hidden lg:table-cell">
                    {c.kommune ?? "–"}
                  </td>
                  <td className="py-2 text-right text-xs text-[#8A7F74] hidden sm:table-cell">
                    {fmtMnok(c.omsetning)}
                  </td>
                  <td className="py-2 text-right">
                    {c.risk_score != null ? (
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                        style={{
                          background: riskColor(c.risk_score) + "20",
                          color: riskColor(c.risk_score),
                        }}>
                        {c.risk_score}
                      </span>
                    ) : <span className="text-xs text-[#8A7F74]">–</span>}
                  </td>
                  <td className="py-2 text-right">
                    {portfolios.length > 0 ? (
                      <button
                        onClick={() => setSelectedOrgnr(c.orgnr)}
                        className="flex items-center gap-1 ml-auto px-2.5 py-1 text-xs rounded-lg border border-[#D4C9B8] text-[#4A6FA5] hover:bg-[#EDE8E3] transition-colors"
                      >
                        <Plus className="w-3 h-3" />
                        Portefølje
                      </button>
                    ) : (
                      <span className="text-xs text-[#C4BDB4]">Ingen porteføljer</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
