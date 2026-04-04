"use client";

import { useState, useRef } from "react";
import { Loader2, Play, CheckCircle, AlertCircle, SkipForward, X } from "lucide-react";

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
  skipped:       <SkipForward className="w-3.5 h-3.5 text-[#C8A951] flex-shrink-0" />,
  error:         <AlertCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />,
  pdf_found:     <CheckCircle className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />,
  pdf_none:      <SkipForward className="w-3.5 h-3.5 text-[#C4BDB4] flex-shrink-0" />,
  pdf_error:     <AlertCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />,
};

function eventLabel(ev: IngestEvent): string {
  const name = ev.navn ?? ev.orgnr ?? "";
  switch (ev.type) {
    case "start":         return `Starter innhenting for ${ev.total ?? "?"} selskaper…`;
    case "searching":     return `Henter ${name}…`;
    case "done":          return `${name} — ferdig`;
    case "skipped":       return `${name} — allerede i database`;
    case "error":         return `${name} — feil: ${ev.message ?? "ukjent"}`;
    case "pdf_searching": return `${name} — søker etter årsrapporter…`;
    case "pdf_found":     return `${name} — PDF funnet`;
    case "pdf_none":      return `${name} — ingen PDF`;
    case "pdf_error":     return `${name} — PDF-feil`;
    case "complete":      return `Ferdig — ${ev.fetched ?? 0} hentet, ${ev.skipped ?? 0} hoppet over, ${ev.errors ?? 0} feil`;
    default:              return ev.message ?? ev.type;
  }
}

interface Props {
  portfolioId: number;
  onDone?: () => void;
}

export function PortfolioIngest({ portfolioId, onDone }: Props) {
  const [running, setRunning]     = useState(false);
  const [events, setEvents]       = useState<IngestEvent[]>([]);
  const [complete, setComplete]   = useState(false);
  const [includePdfs, setIncludePdfs] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const logRef   = useRef<HTMLDivElement>(null);

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

  return (
    <div className="space-y-3 pt-3 border-t border-[#EDE8E3]">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-xs font-semibold text-[#2C3E50]">
          Innhent selskapdata (BRREG + økonomi)
        </p>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-[#8A7F74] cursor-pointer select-none">
            <input
              type="checkbox"
              checked={includePdfs}
              onChange={(e) => setIncludePdfs(e.target.checked)}
              className="rounded"
            />
            Inkluder årsrapport-PDF
          </label>
          {running ? (
            <button onClick={cancel}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-red-200 text-red-600 hover:bg-red-50">
              <X className="w-3.5 h-3.5" /> Avbryt
            </button>
          ) : (
            <button onClick={startIngest}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-[#4A6FA5] text-white hover:bg-[#3a5f95]">
              <Play className="w-3.5 h-3.5" /> Start innhenting
            </button>
          )}
        </div>
      </div>

      {(events.length > 0 || running) && (
        <div
          ref={logRef}
          className="h-48 overflow-y-auto rounded-lg bg-[#2C3E50] p-3 font-mono text-xs space-y-1"
        >
          {events.map((ev, i) => (
            <div key={i} className="flex items-start gap-2">
              {EVENT_ICON[ev.type] ?? (
                running && ev.type === "searching"
                  ? <Loader2 className="w-3.5 h-3.5 text-[#C5D8F0] animate-spin flex-shrink-0" />
                  : <span className="w-3.5 h-3.5 flex-shrink-0" />
              )}
              <span className={
                ev.type === "complete" ? "text-green-400 font-semibold"
                : ev.type === "error" || ev.type === "pdf_error" ? "text-red-400"
                : ev.type === "done" || ev.type === "pdf_found" ? "text-green-300"
                : ev.type === "skipped" || ev.type === "pdf_none" ? "text-[#8A9CB8]"
                : "text-[#C5D8F0]"
              }>
                {eventLabel(ev)}
              </span>
            </div>
          ))}
          {running && (
            <div className="flex items-center gap-2 text-[#8A9CB8]">
              <Loader2 className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
              <span>Arbeider…</span>
            </div>
          )}
        </div>
      )}

      {complete && (
        <p className="text-xs text-green-600 flex items-center gap-1.5">
          <CheckCircle className="w-3.5 h-3.5" />
          Innhenting fullført. Porteføljedata er oppdatert.
        </p>
      )}
    </div>
  );
}
