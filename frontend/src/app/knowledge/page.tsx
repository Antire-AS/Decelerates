"use client";

import { useState, useRef, useEffect } from "react";
import useSWR from "swr";
import {
  knowledgeChat, knowledgeSearch, knowledgeIndex, knowledgeSeedRegulations,
  getKnowledgeStats, knowledgeIngest,
} from "@/lib/api";
import {
  BookOpen, FileText, Video, Search, Settings, Loader2, RefreshCw, Sparkles,
  BarChart3, Download, Trash2, Plus, FolderOpen,
} from "lucide-react";
import DocumentsPanel from "@/components/knowledge/DocumentsPanel";
import VideosPanel from "@/components/knowledge/VideosPanel";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  source_snippets?: Record<string, string>;
}

function readableSource(src: string): string {
  if (src.startsWith("regulation::")) return src.replace("regulation::", "Regulering: ");
  if (src.startsWith("doc_")) return `Dokument ${src.replace("doc_", "")}`;
  if (src.startsWith("video_")) return `Video ${src.replace("video_", "")}`;
  if (src.startsWith("video::")) {
    const parts = src.split("::");
    return parts.length >= 2 ? `🎬 ${parts[1]}` : src;
  }
  if (src.startsWith("doc::")) {
    const parts = src.split("::");
    return parts.length >= 2 ? `📄 ${parts[1]}` : src;
  }
  return src;
}

// ── Markdown table parsing for AnalyseTab CSV downloads ──
function extractMarkdownTables(text: string): string[][][] {
  const tableRegex = /(\|.+\|(?:\n\|[-:| ]+\|)(?:\n\|.+\|)*)/g;
  const matches = text.match(tableRegex) ?? [];
  return matches.map((tbl) => {
    const lines = tbl
      .trim()
      .split("\n")
      .filter((ln) => !/^\|[-:| ]+\|$/.test(ln.trim()));
    return lines.map((ln) =>
      ln
        .replace(/^\||\|$/g, "")
        .split("|")
        .map((c) => c.trim()),
    );
  });
}

function tableToCsv(rows: string[][]): string {
  const escape = (s: string) => `"${s.replace(/"/g, '""')}"`;
  return rows.map((r) => r.map(escape).join(",")).join("\n");
}

function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// Render markdown text with tables shown as proper HTML <table> elements
function renderMarkdownWithTables(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const tableRegex = /(\|.+\|(?:\n\|[-:| ]+\|)(?:\n\|.+\|)*)/g;
  let lastIdx = 0;
  let match;
  let key = 0;
  while ((match = tableRegex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(
        <p key={key++} className="whitespace-pre-wrap text-sm text-[#2C3E50] leading-relaxed">
          {text.slice(lastIdx, match.index).trim()}
        </p>,
      );
    }
    const lines = match[0]
      .trim()
      .split("\n")
      .filter((ln) => !/^\|[-:| ]+\|$/.test(ln.trim()));
    const rows = lines.map((ln) =>
      ln
        .replace(/^\||\|$/g, "")
        .split("|")
        .map((c) => c.trim()),
    );
    if (rows.length >= 2) {
      parts.push(
        <div key={key++} className="overflow-x-auto my-3">
          <table className="w-full text-xs border border-[#EDE8E3]">
            <thead className="bg-[#F4F1ED]">
              <tr>
                {rows[0].map((h, i) => (
                  <th key={i} className="text-left px-2 py-1.5 font-semibold text-[#2C3E50] border-b border-[#EDE8E3]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(1).map((r, i) => (
                <tr key={i} className="border-b border-[#EDE8E3] last:border-0">
                  {r.map((c, j) => (
                    <td key={j} className="px-2 py-1.5 text-[#2C3E50]">{c}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
    }
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < text.length) {
    parts.push(
      <p key={key++} className="whitespace-pre-wrap text-sm text-[#2C3E50] leading-relaxed">
        {text.slice(lastIdx).trim()}
      </p>,
    );
  }
  return parts.length > 0 ? parts : (
    <p className="whitespace-pre-wrap text-sm text-[#2C3E50] leading-relaxed">{text}</p>
  );
}

const COMPARISON_PROMPTS: Array<{ label: string; prompt: string }> = [
  {
    label: "📊 Sammenlign ansvarsforsikring og produktansvar",
    prompt: "Lag en kompakt sammenligningstabell (markdown) av ansvarsforsikring og produktansvarsforsikring " +
            "med kolonner: Type | Hva dekkes | Typiske unntak | Hvem trenger det.",
  },
  {
    label: "📊 Oversikt over vanlige bedriftsforsikringer",
    prompt: "Lag en oversiktstabell (markdown) over de 6 vanligste forsikringstypene for norske SMB-bedrifter " +
            "med kolonner: Forsikringstype | Hva dekkes | Typisk forsikringssum | Anbefalt for.",
  },
  {
    label: "📊 Cyberforsikring — dekning og unntak",
    prompt: "Lag en tabell (markdown) over hva cyberforsikring typisk dekker og ikke dekker, " +
            "med kolonner: Område | Dekket? | Eksempel.",
  },
  {
    label: "📊 Sammenlign forsikringstilbydere i dokumentene",
    prompt: "Basert på forsikringsdokumentene i kunnskapsbasen, lag en sammenligningstabell av " +
            "forsikringstilbyderne med kolonner: Selskap | Produkt | Dekning | Premie | Særtrekk.",
  },
  {
    label: "📊 Forsikringslovgivning — nøkkelparagrafer",
    prompt: "Lag en oversiktstabell (markdown) over de viktigste paragrafene i Forsikringsavtaleloven (FAL) " +
            "som er relevante for bedriftsforsikring, med kolonner: § | Tema | Hva det innebærer.",
  },
];

// ── Chat tab ──────────────────────────────────────────────────────────────────

function ChatTab() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || isLoading) return;
    setQuestion("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setIsLoading(true);
    try {
      const res = await knowledgeChat(q);
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: res.answer,
        sources: res.sources,
        source_snippets: res.source_snippets,
      }]);
    } catch (err) {
      setError(`Kunne ikke hente svar: ${err instanceof Error ? err.message : "Ukjent feil"}`);
    } finally {
      setIsLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit(e as unknown as React.FormEvent);
    }
  }

  return (
    <div className="broker-card flex flex-col" style={{ minHeight: "60vh" }}>
      <div className="flex-1 space-y-4 overflow-y-auto mb-4" style={{ maxHeight: "55vh" }}>
        {messages.length === 0 && !isLoading && (
          <div className="text-center py-12 text-[#8A7F74]">
            <p className="text-sm font-medium text-[#2C3E50] mb-2">Hei! Jeg er din forsikringsassistent.</p>
            <p className="text-sm">Spør meg om forsikringstyper, risiko, kunderegulering, GDPR eller hvilken dekning et selskap trenger.</p>
            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-2">
              {[
                "Hva er ansvarsforsikring?",
                "Hvilken forsikring trenger et byggefirma?",
                "Hva er en SLA-avtale?",
                "Forklar egenkapitalandel enkelt",
              ].map((s) => (
                <button key={s} onClick={() => setQuestion(s)}
                  className="px-3 py-2 text-xs text-left rounded-lg border border-[#EDE8E3] text-[#2C3E50] hover:bg-[#F9F7F4]">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className="max-w-[82%]">
              <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-[#2C3E50] text-white rounded-br-sm"
                  : "bg-[#F4F1ED] text-[#2C3E50] rounded-bl-sm"
              }`}>
                {msg.role === "assistant"
                  ? renderMarkdownWithTables(msg.content)
                  : <p className="whitespace-pre-wrap">{msg.content}</p>}
              </div>
              {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                <details className="mt-1.5">
                  <summary className="text-xs text-[#8A7F74] cursor-pointer hover:text-[#2C3E50] inline-block">
                    Kilder ({msg.sources.length})
                  </summary>
                  <div className="mt-1.5 space-y-1">
                    {msg.sources.map((src) => {
                      const snippet = msg.source_snippets?.[src];
                      return (
                        <div key={src} className="text-xs border border-[#EDE8E3] rounded-lg p-2 bg-[#F9F7F4]">
                          <p className="font-medium text-[#2C3E50]">{readableSource(src)}</p>
                          {snippet && (
                            <p className="text-[10px] text-[#8A7F74] italic mt-0.5 line-clamp-3">{snippet}</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </details>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-[#F4F1ED] px-4 py-3 rounded-2xl rounded-bl-sm">
              <div className="flex gap-1 items-center h-4">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="w-1.5 h-1.5 bg-[#8A7F74] rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          </div>
        )}

        {error && <div className="broker-card bg-red-50 border-red-200 text-red-700 text-sm">{error}</div>}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 pt-4 border-t border-[#EDE8E3] items-end">
        <textarea value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={handleKeyDown}
          placeholder="Still et spørsmål... (Enter for å sende, Shift+Enter for ny linje)"
          rows={2} disabled={isLoading}
          className="flex-1 px-3 py-2 text-sm border border-[#EDE8E3] rounded-lg text-[#2C3E50] placeholder-[#C8BEB4] focus:outline-none focus:border-[#2C3E50] resize-none disabled:opacity-50" />
        {messages.length > 0 && (
          <button type="button" onClick={() => { setMessages([]); setError(null); }}
            title="Tøm samtale"
            className="px-3 py-2 rounded-lg border border-[#EDE8E3] text-[#8A7F74] hover:bg-[#F4F1ED] text-sm flex items-center gap-1">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
        <button type="submit" disabled={isLoading || !question.trim()}
          className="px-4 py-2 rounded-lg bg-[#2C3E50] text-white text-sm font-medium hover:bg-[#3d5166] disabled:opacity-50">
          Send
        </button>
      </form>
    </div>
  );
}

// ── Search tab ────────────────────────────────────────────────────────────────

interface SearchResult {
  source: string;
  chunk_text: string;
  orgnr: string;
  created_at?: string;
}

function SearchTab() {
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
          <label className="block text-xs font-medium text-[#8A7F74] mb-1">Søk i kunnskapsbasen</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#C4BDB4]" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Søk etter tekst, begreper, selskaper…"
              className="w-full pl-9 pr-3 py-2 text-sm border border-[#D4C9B8] rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] text-[#2C3E50]"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-[#8A7F74] mb-1">Antall</label>
          <select
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

// ── Analyse tab ───────────────────────────────────────────────────────────────

interface AnalyseResult {
  label: string;
  answer: string;
  sources?: string[];
}

function AnalyseTab() {
  const [result, setResult]   = useState<AnalyseResult | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError]     = useState<string | null>(null);

  async function handleRun(label: string, prompt: string) {
    setLoading(label);
    setError(null);
    try {
      const res = await knowledgeChat(prompt);
      setResult({ label, answer: res.answer, sources: res.sources });
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  }

  const tables = result ? extractMarkdownTables(result.answer) : [];

  return (
    <div className="space-y-4">
      <div className="broker-card space-y-2">
        <h3 className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
          <BarChart3 className="w-4 h-4" /> AI-genererte sammenligninger og tabeller
        </h3>
        <p className="text-xs text-[#8A7F74]">
          Klikk en knapp for å be AI-en lage en strukturert tabell basert på kunnskapsbasen.
          Tabeller kan lastes ned som CSV.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {COMPARISON_PROMPTS.map(({ label, prompt }) => (
          <button
            key={label}
            onClick={() => handleRun(label, prompt)}
            disabled={loading !== null}
            className="px-4 py-3 text-left text-sm rounded-lg border border-[#EDE8E3] hover:border-[#4A6FA5] hover:bg-[#F0F4FB] disabled:opacity-50 transition-colors text-[#2C3E50] font-medium flex items-center justify-between gap-2"
          >
            <span>{label}</span>
            {loading === label && <Loader2 className="w-3.5 h-3.5 animate-spin text-[#4A6FA5] flex-shrink-0" />}
          </button>
        ))}
      </div>

      {error && (
        <div className="broker-card bg-red-50 border-red-200 text-red-700 text-sm">{error}</div>
      )}

      {result && (
        <div className="broker-card space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold text-[#2C3E50]">{result.label}</h4>
            <button
              onClick={() => setResult(null)}
              className="text-xs text-[#8A7F74] hover:text-[#2C3E50] flex items-center gap-1"
            >
              <Trash2 className="w-3 h-3" /> Tøm
            </button>
          </div>

          {renderMarkdownWithTables(result.answer)}

          {tables.length > 0 && (
            <div className="flex gap-2 flex-wrap pt-2 border-t border-[#EDE8E3]">
              {tables.map((rows, i) => (
                <button
                  key={i}
                  onClick={() => downloadCsv(`sammenligning_${i + 1}.csv`, tableToCsv(rows))}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-[#C5D0E8] text-[#4A6FA5] bg-[#F0F4FB] hover:bg-[#E0E8F5]"
                >
                  <Download className="w-3 h-3" />
                  Last ned tabell {i + 1} (CSV)
                </button>
              ))}
            </div>
          )}

          {result.sources && result.sources.length > 0 && (
            <details className="pt-2 border-t border-[#EDE8E3]">
              <summary className="text-xs text-[#8A7F74] cursor-pointer hover:text-[#2C3E50]">
                Kilder ({result.sources.length})
              </summary>
              <div className="mt-2 space-y-1">
                {result.sources.map((src, i) => (
                  <p key={i} className="text-xs text-[#8A7F74]">• {readableSource(src)}</p>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

// ── Manage tab ────────────────────────────────────────────────────────────────

function ManageTab() {
  const { data: stats, mutate: mutateStats } = useSWR("knowledge-stats", getKnowledgeStats);

  const [indexLoading, setIndexLoading]   = useState(false);
  const [indexResult, setIndexResult]     = useState<string | null>(null);
  const [indexErr, setIndexErr]           = useState<string | null>(null);

  const [seedLoading, setSeedLoading]     = useState(false);
  const [seedResult, setSeedResult]       = useState<Array<{ name: string; status: string; chunks?: number }> | null>(null);
  const [seedErr, setSeedErr]             = useState<string | null>(null);

  // Custom ingest form
  const [ingestOrgnr,  setIngestOrgnr]  = useState("");
  const [ingestSource, setIngestSource] = useState("custom_note");
  const [ingestText,   setIngestText]   = useState("");
  const [ingestLoading, setIngestLoading] = useState(false);
  const [ingestErr,    setIngestErr]    = useState<string | null>(null);
  const [ingestOk,     setIngestOk]     = useState<string | null>(null);

  async function handleIngest() {
    setIngestErr(null);
    setIngestOk(null);
    const orgnr = ingestOrgnr.trim();
    if (!/^\d{9}$/.test(orgnr)) {
      setIngestErr("Skriv inn et gyldig 9-sifret orgnr.");
      return;
    }
    if (!ingestText.trim()) {
      setIngestErr("Teksten kan ikke være tom.");
      return;
    }
    setIngestLoading(true);
    try {
      const r = await knowledgeIngest(orgnr, ingestText.trim(), ingestSource.trim() || "custom_note");
      setIngestOk(`Lagret ${r.chunks_stored} biter for orgnr ${r.orgnr}.`);
      setIngestText("");
      mutateStats();
    } catch (e) {
      setIngestErr(String(e));
    } finally {
      setIngestLoading(false);
    }
  }

  async function handleIndex(force: boolean) {
    setIndexLoading(true); setIndexResult(null); setIndexErr(null);
    try {
      const r = await knowledgeIndex(force);
      setIndexResult(
        `Indeksering fullført — ${r.total_new_chunks} nye chunks ` +
        `(${r.docs_chunks} dokumenter, ${r.video_chunks} videoer)` +
        (r.cleared_chunks != null ? `, slettet ${r.cleared_chunks}` : ""),
      );
      mutateStats();
    } catch (e) { setIndexErr(String(e)); }
    finally { setIndexLoading(false); }
  }

  async function handleSeedRegulations() {
    setSeedLoading(true); setSeedResult(null); setSeedErr(null);
    try {
      const r = await knowledgeSeedRegulations();
      setSeedResult(r.seeded);
      mutateStats();
    } catch (e) { setSeedErr(String(e)); }
    finally { setSeedLoading(false); }
  }

  return (
    <div className="space-y-4">
      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Totalt chunks", value: stats?.total_chunks, icon: <BookOpen className="w-4 h-4" /> },
          { label: "Dokumentchunks", value: stats?.doc_chunks,   icon: <FileText className="w-4 h-4" /> },
          { label: "Videochunks",    value: stats?.video_chunks,  icon: <Video className="w-4 h-4" /> },
        ].map(({ label, value, icon }) => (
          <div key={label} className="broker-card text-center">
            <div className="flex justify-center text-[#4A6FA5] mb-1">{icon}</div>
            <p className="text-xl font-bold text-[#2C3E50]">{value ?? "–"}</p>
            <p className="text-xs text-[#8A7F74]">{label}</p>
          </div>
        ))}
      </div>

      {/* Index documents */}
      <div className="broker-card space-y-3">
        <h3 className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
          <RefreshCw className="w-4 h-4" /> Indekser dokumenter og videoer
        </h3>
        <p className="text-xs text-[#8A7F74]">
          Henter alle dokumenter og videoer fra databasen og bygger vektorsøkeindeksen på nytt.
          Bruk &ldquo;Tving&rdquo; for å slette eksisterende indeks og starte fra scratch.
        </p>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => handleIndex(false)}
            disabled={indexLoading}
            className="px-3 py-1.5 text-xs rounded-lg bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50 flex items-center gap-1.5"
          >
            {indexLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            Indekser (inkrementelt)
          </button>
          <button
            onClick={() => handleIndex(true)}
            disabled={indexLoading}
            className="px-3 py-1.5 text-xs rounded-lg bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 disabled:opacity-50 flex items-center gap-1.5"
          >
            {indexLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            Tving full re-indeksering
          </button>
        </div>
        {indexErr    && <p className="text-xs text-red-600">{indexErr}</p>}
        {indexResult && <p className="text-xs text-green-700">{indexResult}</p>}
      </div>

      {/* Seed regulations */}
      <div className="broker-card space-y-3">
        <h3 className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
          <Sparkles className="w-4 h-4" /> Seed norske forsikringsreguleringer
        </h3>
        <p className="text-xs text-[#8A7F74]">
          Legger til forhåndsdefinererte norske forsikrings- og finansreguleringer i kunnskapsbasen
          (GDPR, IDD, Solvens II, m.fl.). Allerede eksisterende oppføringer hoppes over.
        </p>
        <button
          onClick={handleSeedRegulations}
          disabled={seedLoading}
          className="px-3 py-1.5 text-xs rounded-lg bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50 flex items-center gap-1.5"
        >
          {seedLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
          Seed reguleringer
        </button>
        {seedErr && <p className="text-xs text-red-600">{seedErr}</p>}
        {seedResult && (
          <div className="divide-y divide-[#EDE8E3]">
            {seedResult.map((item, i) => (
              <div key={i} className="py-2 flex items-center justify-between text-xs">
                <span className="text-[#2C3E50] font-medium">{item.name}</span>
                <div className="flex items-center gap-2 text-[#8A7F74]">
                  {item.chunks != null && <span>{item.chunks} chunks</span>}
                  <span className={`px-1.5 py-0.5 rounded-full ${
                    item.status === "seeded" ? "bg-green-100 text-green-700"
                    : item.status === "exists" ? "bg-[#EDE8E3] text-[#8A7F74]"
                    : "bg-red-100 text-red-600"
                  }`}>
                    {item.status === "seeded" ? "Lagt til" : item.status === "exists" ? "Finnes" : item.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Custom knowledge ingest form */}
      <div className="broker-card space-y-3">
        <h3 className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> Legg til egendefinert tekst
        </h3>
        <p className="text-xs text-[#8A7F74]">
          Teksten blir delt opp i biter og embeddet for bruk i AI-chat. Knyttes til et orgnr.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div>
            <label className="block text-xs font-medium text-[#8A7F74] mb-1">Orgnr (9 siffer)</label>
            <input
              value={ingestOrgnr}
              onChange={(e) => setIngestOrgnr(e.target.value.replace(/\D/g, "").slice(0, 9))}
              maxLength={9}
              placeholder="123456789"
              className="w-full px-3 py-1.5 text-sm border border-[#D4C9B8] rounded-lg text-[#2C3E50] focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[#8A7F74] mb-1">Kildelabel</label>
            <input
              value={ingestSource}
              onChange={(e) => setIngestSource(e.target.value)}
              placeholder="custom_note"
              className="w-full px-3 py-1.5 text-sm border border-[#D4C9B8] rounded-lg text-[#2C3E50] focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-[#8A7F74] mb-1">Tekst å legge inn</label>
          <textarea
            value={ingestText}
            onChange={(e) => setIngestText(e.target.value)}
            rows={5}
            placeholder="Lim inn notater, sammendrag eller fritekst…"
            className="w-full px-3 py-2 text-sm border border-[#D4C9B8] rounded-lg text-[#2C3E50] focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] resize-y"
          />
        </div>
        <button
          onClick={handleIngest}
          disabled={ingestLoading}
          className="px-3 py-1.5 text-xs rounded-lg bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50 flex items-center gap-1.5"
        >
          {ingestLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
          Lagre i kunnskapsbase
        </button>
        {ingestErr && <p className="text-xs text-red-600">{ingestErr}</p>}
        {ingestOk  && <p className="text-xs text-green-700">{ingestOk}</p>}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = "chat" | "search" | "analyse" | "documents" | "videos" | "manage";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "chat",      label: "Chat",         icon: <Sparkles className="w-3.5 h-3.5" /> },
  { id: "search",    label: "Søk",          icon: <Search className="w-3.5 h-3.5" /> },
  { id: "analyse",   label: "Analyse",      icon: <BarChart3 className="w-3.5 h-3.5" /> },
  { id: "documents", label: "Dokumenter",   icon: <FolderOpen className="w-3.5 h-3.5" /> },
  { id: "videos",    label: "Videoer",      icon: <Video className="w-3.5 h-3.5" /> },
  { id: "manage",    label: "Administrer",  icon: <Settings className="w-3.5 h-3.5" /> },
];

export default function KnowledgePage() {
  // Read ?tab= so that /documents and /videos redirects can deep-link directly
  // to the right sub-tab. Falls back to "chat" for the bare /knowledge URL.
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    if (typeof window === "undefined") return "chat";
    const t = new URLSearchParams(window.location.search).get("tab");
    return (["chat","search","analyse","documents","videos","manage"] as const).includes(t as Tab) ? (t as Tab) : "chat";
  });

  const TAB_CLS = (t: Tab) =>
    `flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-colors cursor-pointer ${
      activeTab === t
        ? "bg-[#2C3E50] text-white"
        : "text-[#8A7F74] hover:bg-[#EDE8E3]"
    }`;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Kunnskapsbase</h1>
        <p className="text-sm text-[#8A7F74] mt-1">
          AI-assistent, semantisk søk og indeksadministrasjon
        </p>
      </div>

      <div className="flex gap-2 flex-wrap">
        {TABS.map(({ id, label, icon }) => (
          <button key={id} onClick={() => setActiveTab(id)} className={TAB_CLS(id)}>
            {icon}
            {label}
          </button>
        ))}
      </div>

      {activeTab === "chat"      && <ChatTab />}
      {activeTab === "search"    && <SearchTab />}
      {activeTab === "analyse"   && <AnalyseTab />}
      {activeTab === "documents" && <DocumentsPanel />}
      {activeTab === "videos"    && <VideosPanel />}
      {activeTab === "manage"    && <ManageTab />}
    </div>
  );
}
