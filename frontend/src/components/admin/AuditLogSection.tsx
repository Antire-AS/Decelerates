"use client";

import { useState } from "react";
import useSWR from "swr";
import { getAuditLog, type AuditLogEntryOut, type AuditLogPageOut } from "@/lib/api";
import { Loader2, RefreshCw, Download, ChevronDown, ChevronRight } from "lucide-react";
import { downloadCsv } from "@/lib/csv-export";
import { SectionHeader } from "./shared";

/**
 * Browse-and-filter audit log — plan §🟢 #13.
 *
 * Backed by GET /audit?{filters}&offset=&limit= which returns AuditLogPageOut.
 * The filter bar pushes state into a key the SWR cache uses, so changing
 * filters refetches the right page automatically.
 */
export function AuditLogSection() {
  const [limit, setLimit]               = useState(50);
  const [offset, setOffset]             = useState(0);
  const [orgnr, setOrgnr]               = useState("");
  const [action, setAction]             = useState("");
  const [actorEmail, setActorEmail]     = useState("");
  const [fromDate, setFromDate]         = useState("");
  const [toDate, setToDate]             = useState("");
  const [expanded, setExpanded]         = useState<Set<number>>(new Set());

  const cacheKey = `audit-${limit}-${offset}-${orgnr}-${action}-${actorEmail}-${fromDate}-${toDate}`;
  const { data, isLoading, mutate } = useSWR<AuditLogPageOut>(
    cacheKey,
    () => getAuditLog({
      orgnr: orgnr || undefined,
      action: action || undefined,
      actor_email: actorEmail || undefined,
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
      limit,
      offset,
    }),
  );

  const items: AuditLogEntryOut[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasMore = data?.has_more ?? false;

  function toggleRow(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) { next.delete(id); } else { next.add(id); }
      return next;
    });
  }

  function handleDownload() {
    if (!items.length) return;
    downloadCsv(
      items.map((r) => ({
        Tidspunkt: String(r.created_at).slice(0, 19).replace("T", " "),
        Bruker: r.actor_email ?? "–",
        Handling: r.action,
        Orgnr: r.orgnr ?? "–",
        Detaljer: r.detail ?? "–",
      })),
      `aktivitetslogg_${new Date().toISOString().slice(0, 10)}.csv`,
    );
  }

  function clearFilters() {
    setOrgnr(""); setAction(""); setActorEmail("");
    setFromDate(""); setToDate(""); setOffset(0);
  }

  const hasFilters = orgnr || action || actorEmail || fromDate || toDate;

  return (
    <div className="broker-card">
      <div className="flex items-center justify-between mb-3">
        <SectionHeader title="Aktivitetslogg" subtitle="Compliance gate — Finanstilsynet evidence trail. Hvem har brukt applikasjonen og hvilke handlinger de har utført." />
        <div className="flex items-center gap-2">
          <select
            value={limit}
            onChange={(e) => { setLimit(Number(e.target.value)); setOffset(0); }}
            className="text-xs border border-border rounded px-2 py-1 bg-card focus:outline-none"
          >
            {[10, 25, 50, 100, 200].map((v) => <option key={v} value={v}>{v} rader</option>)}
          </select>
          <button onClick={() => mutate()} className="text-muted-foreground hover:text-foreground">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2 mb-3 p-2 bg-muted rounded-lg">
        <input
          value={orgnr}
          onChange={(e) => { setOrgnr(e.target.value); setOffset(0); }}
          placeholder="Orgnr"
          className="text-xs border border-border rounded px-2 py-1.5 bg-card"
        />
        <input
          value={action}
          onChange={(e) => { setAction(e.target.value); setOffset(0); }}
          placeholder="Handling (f.eks. policy.create)"
          className="text-xs border border-border rounded px-2 py-1.5 bg-card"
        />
        <input
          value={actorEmail}
          onChange={(e) => { setActorEmail(e.target.value); setOffset(0); }}
          placeholder="Bruker e-post"
          className="text-xs border border-border rounded px-2 py-1.5 bg-card"
        />
        <input
          type="date"
          value={fromDate}
          onChange={(e) => { setFromDate(e.target.value); setOffset(0); }}
          className="text-xs border border-border rounded px-2 py-1.5 bg-card"
        />
        <input
          type="date"
          value={toDate}
          onChange={(e) => { setToDate(e.target.value); setOffset(0); }}
          className="text-xs border border-border rounded px-2 py-1.5 bg-card"
        />
      </div>
      {hasFilters && (
        <button onClick={clearFilters} className="text-xs text-primary hover:underline mb-2">
          Fjern filter
        </button>
      )}

      {data && total > 0 && (
        <p className="text-xs text-muted-foreground mb-2">
          Viser {offset + 1}–{offset + items.length} av {total}
        </p>
      )}

      {isLoading && <Loader2 className="w-5 h-5 animate-spin text-primary" />}
      {!isLoading && !items.length && (
        <p className="text-xs text-muted-foreground">Ingen aktivitet matcher filteret.</p>
      )}
      {items.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 pr-3 text-muted-foreground font-semibold w-6"></th>
                  {["Tidspunkt", "Bruker", "Handling", "Orgnr"].map((h) => (
                    <th key={h} className="text-left py-2 pr-3 text-muted-foreground font-semibold whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((r) => {
                  const isOpen = expanded.has(r.id);
                  return (
                    <>
                      <tr key={r.id}>
                        <td className="py-2 pr-1">
                          {r.detail && (
                            <button onClick={() => toggleRow(r.id)} className="text-muted-foreground hover:text-foreground">
                              {isOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                            </button>
                          )}
                        </td>
                        <td className="py-2 pr-3 whitespace-nowrap text-muted-foreground">
                          {String(r.created_at).slice(0, 19).replace("T", " ")}
                        </td>
                        <td className="py-2 pr-3 text-foreground">{r.actor_email ?? "–"}</td>
                        <td className="py-2 pr-3 text-foreground">{r.action}</td>
                        <td className="py-2 pr-3 text-muted-foreground">{r.orgnr ?? "–"}</td>
                      </tr>
                      {isOpen && r.detail && (
                        <tr key={`${r.id}-detail`}>
                          <td colSpan={5} className="py-2 pr-3 pl-6 bg-muted">
                            <pre className="text-[10px] text-foreground whitespace-pre-wrap font-mono">{r.detail}</pre>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination + export */}
          <div className="flex items-center justify-between mt-3">
            <button
              onClick={handleDownload}
              className="flex items-center gap-1.5 text-xs text-primary hover:underline"
            >
              <Download className="w-3 h-3" /> Eksporter CSV (denne siden)
            </button>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setOffset(Math.max(0, offset - limit))}
                disabled={offset === 0}
                className="text-xs px-2 py-1 rounded border border-border disabled:opacity-40"
              >
                Forrige
              </button>
              <button
                onClick={() => setOffset(offset + limit)}
                disabled={!hasMore}
                className="text-xs px-2 py-1 rounded border border-border disabled:opacity-40"
              >
                Neste
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
