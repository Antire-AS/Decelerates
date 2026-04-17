"use client";

import { useState } from "react";
import { Search, Loader2 } from "lucide-react";
import { knowledgeSearch } from "@/lib/api";
import { readableSource } from "./_shared";

interface SearchResult {
  source: string;
  chunk_text: string;
  orgnr: string;
  created_at?: string;
}

export default function SearchTab() {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(10);
  const [filter, setFilter] = useState<"all" | "doc" | "video">("all");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filteredResults = results == null ? null : results.filter((r) => {
    const src = r.source ?? "";
    if (filter === "doc")   return src.startsWith("doc");
    if (filter === "video") return src.startsWith("video");
    return true;
  });
  const docCount   = results?.filter((r) => (r.source ?? "").startsWith("doc")).length ?? 0;
  const videoCount = results?.filter((r) => (r.source ?? "").startsWith("video")).length ?? 0;

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await knowledgeSearch(q, limit);
      setResults(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSearch} className="broker-card flex gap-3 items-end">
        <div className="flex-1">
          <label className="block text-xs font-medium text-[#8A7F74] mb-1" htmlFor="knowledge-search-query">Søk i kunnskapsbasen</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#C4BDB4]" />
            <input
              id="knowledge-search-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Søk etter tekst, begreper, selskaper…"
              className="w-full pl-9 pr-3 py-2 text-sm border border-[#D4C9B8] rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] text-[#2C3E50]"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-[#8A7F74] mb-1" htmlFor="knowledge-search-limit">Antall</label>
          <select
            id="knowledge-search-limit"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="text-sm border border-[#D4C9B8] rounded-lg px-2 py-2 text-[#2C3E50] focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
          >
            {[5, 10, 20, 50].map((n) => <option key={n} value={n}>{n} resultater</option>)}
          </select>
        </div>
        <button type="submit" disabled={isLoading || !query.trim()}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50 flex items-center gap-1.5">
          {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
          Søk
        </button>
      </form>

      {error && <div className="broker-card bg-red-50 border-red-200 text-red-700 text-sm">{error}</div>}

      {results !== null && results.length > 0 && (
        <div className="flex gap-2 flex-wrap items-center">
          <span className="text-xs text-[#8A7F74]">Filtrer:</span>
          {([
            { id: "all" as const,   label: `Alle (${results.length})` },
            { id: "doc" as const,   label: `📄 Dokumenter (${docCount})` },
            { id: "video" as const, label: `🎬 Videoer (${videoCount})` },
          ]).map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setFilter(id)}
              className={`px-3 py-1 text-xs rounded-lg font-medium transition-colors ${
                filter === id ? "bg-[#2C3E50] text-white" : "bg-[#EDE8E3] text-[#8A7F74] hover:bg-[#DDD8D3]"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {filteredResults !== null && (
        filteredResults.length === 0 ? (
          <div className="broker-card text-center py-10 text-sm text-[#8A7F74]">
            Ingen resultater for &ldquo;{query}&rdquo;.
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-[#8A7F74]">
              {filteredResults.length} treff — 📄 {filteredResults.filter((r) => (r.source ?? "").startsWith("doc")).length} fra dokumenter ·
              🎬 {filteredResults.filter((r) => (r.source ?? "").startsWith("video")).length} fra videoer
            </p>
            {filteredResults.map((r, i) => (
              <div key={i} className="broker-card space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-[#EDE8E3] text-[#8A7F74] truncate max-w-[60%]">
                    {readableSource(r.source)}
                  </span>
                  <div className="flex items-center gap-2 text-xs text-[#C4BDB4] flex-shrink-0">
                    {r.orgnr && <span>Orgnr: {r.orgnr}</span>}
                    {r.created_at && <span>{r.created_at.slice(0, 10)}</span>}
                  </div>
                </div>
                <p className="text-sm text-[#2C3E50] leading-relaxed line-clamp-5">{r.chunk_text}</p>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}
