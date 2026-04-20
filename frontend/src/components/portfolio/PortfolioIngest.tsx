"use client";

import { useState, useRef } from "react";
import { Loader2, Play, CheckCircle, AlertCircle, SkipForward, X, FileUp } from "lucide-react";
import { useT } from "@/lib/i18n";

interface IngestEvent {
  type: string;
  orgnr?: string;
  navn?: string;
  message?: string;
  total?: number;
  fetched?: number;
  skipped?: number;
  errors?: number;
}

const EVENT_ICON: Record<string, React.ReactNode> = {
  done:          <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />,
  skipped:       <SkipForward className="w-3.5 h-3.5 text-brand-warning flex-shrink-0" />,
  error:         <AlertCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />,
  pdf_found:     <CheckCircle className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />,
  pdf_none:      <SkipForward className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />,
  pdf_error:     <AlertCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />,
};

function eventLabel(ev: IngestEvent, T: (k: string) => string): string {
  const name = ev.navn ?? ev.orgnr ?? "";
  switch (ev.type) {
    case "start":         return `${T("Starter innhenting for")} ${ev.total ?? "?"} ${T("selskaper…")}`;
    case "searching":     return `${T("Henter")} ${name}…`;
    case "done":          return `${name} — ${T("ferdig")}`;
    case "skipped":       return `${name} — ${T("allerede i database")}`;
    case "error":         return `${name} — ${T("feil")}: ${ev.message ?? T("ukjent")}`;
    case "pdf_searching": return `${name} — ${T("søker etter årsrapporter…")}`;
    case "pdf_found":     return `${name} — ${T("PDF funnet")}`;
    case "pdf_none":      return `${name} — ${T("ingen PDF")}`;
    case "pdf_error":     return `${name} — ${T("PDF-feil")}`;
    case "complete":      return `${T("Ferdig")} — ${ev.fetched ?? 0} ${T("hentet")}, ${ev.skipped ?? 0} ${T("hoppet over")}, ${ev.errors ?? 0} ${T("feil")}`;
    default:              return ev.message ?? ev.type;
  }
}

interface Props {
  portfolioId: number;
  onDone?: () => void;
}

export function PortfolioIngest({ portfolioId, onDone }: Props) {
  const T = useT();
  const [running, setRunning]     = useState(false);
  const [events, setEvents]       = useState<IngestEvent[]>([]);
  const [complete, setComplete]   = useState(false);
  const [includePdfs, setIncludePdfs] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const logRef   = useRef<HTMLDivElement>(null);

  // CSV import state
  const [csvRunning, setCsvRunning] = useState(false);
  const [csvEvents, setCsvEvents]   = useState<IngestEvent[]>([]);
  const [csvComplete, setCsvComplete] = useState(false);
  const csvFileRef = useRef<HTMLInputElement>(null);

  function scrollToBottom() {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }

  async function startIngest() {
    setRunning(true);
    setComplete(false);
    setEvents([]);

    const ac = new AbortController();
    abortRef.current = ac;

    // Use the dedicated streaming Route Handler (/api/portfolio/[id]/ingest-stream)
    // rather than the /bapi rewrite, which may buffer chunks before forwarding.
    const url = `/api/portfolio/${portfolioId}/ingest-stream${includePdfs ? "?include_pdfs=true" : ""}`;

    try {
      const res = await fetch(url, { signal: ac.signal });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          try {
            const ev: IngestEvent = JSON.parse(trimmed);
            setEvents((prev) => [...prev, ev]);
            setTimeout(scrollToBottom, 20);
            if (ev.type === "complete") {
              setComplete(true);
              onDone?.();
            }
          } catch {
            // malformed line — skip
          }
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setEvents((prev) => [...prev, { type: "error", message: String(e) }]);
      }
    } finally {
      setRunning(false);
    }
  }

  function cancel() {
    abortRef.current?.abort();
    setRunning(false);
  }

  async function startCsvImport(file: File) {
    setCsvRunning(true); setCsvComplete(false); setCsvEvents([]);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch(`/bapi/batch/import?portfolio_id=${portfolioId}`, { method: "POST", body: fd });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          try {
            const ev: IngestEvent = JSON.parse(trimmed);
            setCsvEvents((prev) => [...prev, ev]);
            if (ev.type === "complete") { setCsvComplete(true); onDone?.(); }
          } catch { /* skip malformed */ }
        }
      }
    } catch (e) {
      setCsvEvents((prev) => [...prev, { type: "error", message: String(e) }]);
    } finally {
      setCsvRunning(false);
    }
  }

  return (
    <div className="space-y-3 pt-3 border-t border-border">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-xs font-semibold text-foreground">
          {T("Innhent selskapdata (BRREG + økonomi)")}
        </p>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
            <input
              type="checkbox"
              checked={includePdfs}
              onChange={(e) => setIncludePdfs(e.target.checked)}
              className="rounded"
            />
            {T("Inkluder årsrapport-PDF")}
          </label>
          {running ? (
            <button onClick={cancel}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-red-200 text-red-600 hover:bg-red-50">
              <X className="w-3.5 h-3.5" /> {T("Avbryt")}
            </button>
          ) : (
            <button onClick={startIngest}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-primary text-primary-foreground hover:bg-primary/90">
              <Play className="w-3.5 h-3.5" /> {T("Start innhenting")}
            </button>
          )}
        </div>
      </div>

      {(events.length > 0 || running) && (
        <div
          ref={logRef}
          className="h-48 overflow-y-auto rounded-lg bg-primary p-3 font-mono text-xs space-y-1"
        >
          {events.map((ev, i) => (
            <div key={i} className="flex items-start gap-2">
              {EVENT_ICON[ev.type] ?? (
                running && ev.type === "searching"
                  ? <Loader2 className="w-3.5 h-3.5 text-accent-foreground animate-spin flex-shrink-0" />
                  : <span className="w-3.5 h-3.5 flex-shrink-0" />
              )}
              <span className={
                ev.type === "complete" ? "text-green-400 font-semibold"
                : ev.type === "error" || ev.type === "pdf_error" ? "text-red-400"
                : ev.type === "done" || ev.type === "pdf_found" ? "text-green-300"
                : ev.type === "skipped" || ev.type === "pdf_none" ? "text-muted-foreground"
                : "text-accent-foreground"
              }>
                {eventLabel(ev, T)}
              </span>
            </div>
          ))}
          {running && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
              <span>{T("Arbeider…")}</span>
            </div>
          )}
        </div>
      )}

      {complete && (
        <p className="text-xs text-green-600 flex items-center gap-1.5">
          <CheckCircle className="w-3.5 h-3.5" />
          {T("Innhenting fullført. Porteføljedata er oppdatert.")}
        </p>
      )}

      {/* ── CSV import ── */}
      <div className="pt-3 border-t border-border space-y-2">
        <p className="text-xs font-semibold text-foreground">{T("Importer fra CSV")}</p>
        <p className="text-xs text-muted-foreground">
          {T("Last opp en CSV-fil med orgnr (én per linje). Selskaper hentes fra BRREG og legges til porteføljen.")}
        </p>
        <input
          ref={csvFileRef}
          type="file"
          accept=".csv,.txt"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) startCsvImport(f);
            if (csvFileRef.current) csvFileRef.current.value = "";
          }}
        />
        <button
          onClick={() => csvFileRef.current?.click()}
          disabled={csvRunning}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-border text-foreground hover:bg-muted disabled:opacity-50"
        >
          {csvRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileUp className="w-3.5 h-3.5" />}
          {T("Velg CSV-fil")}
        </button>
        {csvEvents.length > 0 && (
          <div className="h-32 overflow-y-auto rounded-lg bg-primary p-3 font-mono text-xs space-y-1">
            {csvEvents.map((ev, i) => (
              <div key={i} className="flex items-start gap-2">
                {EVENT_ICON[ev.type] ?? <span className="w-3.5 h-3.5 flex-shrink-0" />}
                <span className={ev.type === "complete" ? "text-green-400 font-semibold" : ev.type === "error" ? "text-red-400" : "text-accent-foreground"}>
                  {eventLabel(ev, T)}
                </span>
              </div>
            ))}
            {csvRunning && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                <span>{T("Importerer…")}</span>
              </div>
            )}
          </div>
        )}
        {csvComplete && (
          <p className="text-xs text-green-600 flex items-center gap-1.5">
            <CheckCircle className="w-3.5 h-3.5" />
            {T("Import fullført.")}
          </p>
        )}
      </div>
    </div>
  );
}
