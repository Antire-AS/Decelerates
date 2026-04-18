"use client";

import { useState, useTransition, useEffect } from "react";
import Link from "next/link";
import { searchCompanies, type SearchResult } from "@/lib/api";
import { Search, ChevronRight, Loader2, Clock } from "lucide-react";

export default function SearchPage() {
  const [query, setQuery]         = useState("");
  const [size, setSize]           = useState(20);
  const [kommunenr, setKommunenr] = useState("");
  const [results, setResults]     = useState<SearchResult[]>([]);
  const [searched, setSearched]   = useState(false);
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<{ orgnr: string; navn: string }[]>([]);

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("ba_recent_companies") || "[]");
      if (Array.isArray(stored)) setRecent(stored.slice(0, 8));
    } catch { /* ignore */ }
  }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
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
      <h1 className="text-2xl font-bold text-foreground">Selskapsøk</h1>

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
                         bg-white text-foreground placeholder-[#C4BDB4]
                         focus:outline-none focus-visible:ring-2 focus-visible:ring-[#4A6FA5]"
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
                         bg-white text-foreground placeholder-[#C4BDB4]
                         focus:outline-none focus-visible:ring-2 focus-visible:ring-[#4A6FA5]"
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
                         bg-white text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-[#4A6FA5]"
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
                     bg-[#2C3E50] text-white text-sm font-medium
                     hover:bg-[#3d5166] disabled:opacity-50 transition-colors"
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
                className="flex items-center justify-between px-3 py-2 rounded-lg border border-border hover:bg-[#F9F7F4] transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{c.navn}</p>
                  <p className="text-xs text-muted-foreground">{c.orgnr}</p>
                </div>
                <ChevronRight className="w-4 h-4 text-[#C4BDB4] flex-shrink-0" />
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {searched && (
        <div className="broker-card">
          <p className="text-xs text-muted-foreground mb-3">
            Fant <strong>{results.length}</strong> treff
          </p>

          {results.length === 0 ? (
            <p className="text-sm text-muted-foreground">Ingen selskaper funnet.</p>
          ) : (
            <div className="divide-y divide-[#EDE8E3]">
              {results.map((r) => (
                <Link
                  key={r.orgnr}
                  href={`/search/${r.orgnr}`}
                  className="flex items-center gap-3 py-3 hover:bg-[#F9F7F4] -mx-5 px-5
                             transition-colors group"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-foreground group-hover:text-[#4A6FA5]">
                      {r.navn}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {r.orgnr}
                      {r.organisasjonsform && ` · ${r.organisasjonsform}`}
                      {r.kommune && ` · ${r.kommune}`}
                      {r.postnummer && ` ${r.postnummer}`}
                    </p>
                    {r.naeringskode1_beskrivelse && (
                      <p className="text-xs text-[#A09890] mt-0.5">
                        {r.naeringskode1} {r.naeringskode1_beskrivelse}
                      </p>
                    )}
                  </div>
                  <ChevronRight className="w-4 h-4 text-[#C4BDB4] group-hover:text-[#4A6FA5] flex-shrink-0" />
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
