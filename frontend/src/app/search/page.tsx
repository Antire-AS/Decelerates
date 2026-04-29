"use client";

import { useState, useTransition, useEffect, useMemo } from "react";
import Link from "next/link";
import { searchCompanies, type SearchResult } from "@/lib/api";
import { Search, ChevronRight, Loader2, Clock } from "lucide-react";
import { useT } from "@/lib/i18n";
import { useRiskConfig, bandTailwindClass } from "@/lib/useRiskConfig";
import { cn } from "@/lib/cn";

type RiskFilter = "all" | string;

export default function SearchPage() {
  const T = useT();
  const { bands, bandFor } = useRiskConfig();
  const [query, setQuery]         = useState("");
  const [size, setSize]           = useState(20);
  const [kommunenr, setKommunenr] = useState("");
  const [results, setResults]     = useState<SearchResult[]>([]);
  const [searched, setSearched]   = useState(false);
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<{ orgnr: string; navn: string }[]>([]);
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");

  const countsByBand = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const r of results) {
      if (r.risk_score == null) continue;
      counts[bandFor(r.risk_score).label] = (counts[bandFor(r.risk_score).label] ?? 0) + 1;
    }
    return counts;
  }, [results, bandFor]);

  const filteredResults = useMemo(() => {
    if (riskFilter === "all") return results;
    return results.filter((r) => r.risk_score != null && bandFor(r.risk_score).label === riskFilter);
  }, [results, riskFilter, bandFor]);

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("ba_recent_companies") || "[]");
      if (Array.isArray(stored)) setRecent(stored.slice(0, 8));
    } catch { /* ignore */ }
  }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setRiskFilter("all");
    startTransition(async () => {
      try {
        const data = await searchCompanies(query.trim(), size, kommunenr.trim() || undefined);
        setResults(data);
        setSearched(true);
      } catch {
        setError("Søket feilet. Sjekk at API-en kjører.");
      }
    });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-foreground">{T("Selskapsøk")}</h1>

      {/* Search form — stacks vertically on mobile, single row on sm+ */}
      <form onSubmit={handleSearch} className="broker-card space-y-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <label className="block text-xs font-medium text-muted-foreground mb-1" htmlFor="search-query">
              Navn eller orgnr
            </label>
            <input
              id="search-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="F.eks. DNB BANK ASA eller 984851006"
              className="w-full px-3 py-2 text-sm border border-input rounded-lg
                         bg-card text-foreground placeholder:text-muted-foreground
                         focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <div className="w-full sm:w-36">
            <label className="block text-xs font-medium text-muted-foreground mb-1" htmlFor="search-kommune">
              Kommune (valgfri)
            </label>
            <input
              id="search-kommune"
              value={kommunenr}
              onChange={(e) => setKommunenr(e.target.value)}
              placeholder="F.eks. Oslo"
              className="w-full px-3 py-2 text-sm border border-input rounded-lg
                         bg-card text-foreground placeholder:text-muted-foreground
                         focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <div className="w-full sm:w-28">
            <label className="block text-xs font-medium text-muted-foreground mb-1" htmlFor="search-size">
              Maks treff
            </label>
            <select
              id="search-size"
              value={size}
              onChange={(e) => setSize(Number(e.target.value))}
              className="w-full px-3 py-2 text-sm border border-input rounded-lg
                         bg-card text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {[5, 10, 20, 50].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
        </div>

        <button
          type="submit"
          disabled={isPending || !query.trim()}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg
                     bg-primary text-primary-foreground text-sm font-medium
                     hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {isPending
            ? <Loader2 className="w-4 h-4 animate-spin" />
            : <Search className="w-4 h-4" />}
          Søk
        </button>

        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>

      {/* Recently viewed */}
      {!searched && recent.length > 0 && (
        <div className="broker-card">
          <div className="flex items-center gap-1.5 mb-3 text-xs text-muted-foreground">
            <Clock className="w-3.5 h-3.5" />
            <span className="font-medium">Nylig sett</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {recent.map((c) => (
              <Link
                key={c.orgnr}
                href={`/search/${c.orgnr}`}
                className="flex items-center justify-between px-3 py-2 rounded-lg border border-border hover:bg-muted transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{c.navn}</p>
                  <p className="text-xs text-muted-foreground">{c.orgnr}</p>
                </div>
                <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {searched && (
        <div className="broker-card">
          <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
            <p className="text-xs text-muted-foreground">
              Fant <strong>{results.length}</strong> treff
              {riskFilter !== "all" && (
                <span> · viser <strong>{filteredResults.length}</strong> i {riskFilter}</span>
              )}
            </p>
            {/* Risk-bucket filter chips — only render when at least one result has a score */}
            {Object.keys(countsByBand).length > 0 && (
              <div className="flex items-center gap-1.5" role="group" aria-label="Filtrer etter risiko">
                <button
                  onClick={() => setRiskFilter("all")}
                  className={cn(
                    "px-2.5 py-1 rounded-full text-xs font-medium border transition-colors",
                    riskFilter === "all"
                      ? "bg-foreground text-background border-foreground"
                      : "bg-card text-muted-foreground border-border hover:border-foreground"
                  )}
                  aria-pressed={riskFilter === "all"}
                >
                  Alle
                </button>
                {bands.map((band) => {
                  const count = countsByBand[band.label] ?? 0;
                  if (count === 0) return null;
                  const active = riskFilter === band.label;
                  return (
                    <button
                      key={band.label}
                      onClick={() => setRiskFilter(band.label)}
                      className={cn(
                        "px-2.5 py-1 rounded-full text-xs font-medium border transition-colors",
                        active
                          ? bandTailwindClass(band.label) + " border-transparent ring-2 ring-offset-1 ring-offset-background"
                          : "bg-card text-muted-foreground border-border hover:border-foreground",
                      )}
                      style={active ? { boxShadow: `0 0 0 1px ${band.color}` } : undefined}
                      aria-pressed={active}
                    >
                      <span
                        className="inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle"
                        style={{ backgroundColor: band.color }}
                        aria-hidden
                      />
                      {band.label} <span className="opacity-60">({count})</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {filteredResults.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {riskFilter === "all"
                ? "Ingen selskaper funnet."
                : `Ingen selskaper i ${riskFilter}-bucket. Prøv et annet filter.`}
            </p>
          ) : (
            <div className="divide-y divide-border">
              {filteredResults.map((r) => {
                const band = r.risk_score != null ? bandFor(r.risk_score) : null;
                return (
                  <Link
                    key={r.orgnr}
                    href={`/search/${r.orgnr}`}
                    className="flex items-center gap-3 py-3 hover:bg-muted -mx-5 px-5
                               transition-colors group"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-foreground group-hover:text-primary">
                          {r.navn}
                        </p>
                        {band && r.risk_score != null && (
                          <span
                            className={cn(
                              "px-2 py-0.5 rounded-full text-[10px] font-semibold flex-shrink-0",
                              bandTailwindClass(band.label),
                            )}
                            title={`Risikoscore ${r.risk_score} av 20`}
                          >
                            {band.label} · {r.risk_score}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {r.orgnr}
                        {r.organisasjonsform && ` · ${r.organisasjonsform}`}
                        {r.kommune && ` · ${r.kommune}`}
                        {r.postnummer && ` ${r.postnummer}`}
                      </p>
                      {r.naeringskode1_beskrivelse && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {r.naeringskode1} {r.naeringskode1_beskrivelse}
                        </p>
                      )}
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-primary flex-shrink-0" />
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
