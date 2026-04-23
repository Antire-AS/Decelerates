"use client";

import { useState } from "react";
import useSWR from "swr";
import { Loader2, RefreshCw } from "lucide-react";
import {
  getInboundEmailLog,
  type IncomingEmailLogEntryOut,
  type IncomingEmailLogPageOut,
} from "@/lib/api";
import { SectionHeader } from "./shared";
import { useT } from "@/lib/i18n";

/**
 * Read-only browser for `incoming_email_log` — msgraph activation Task 11.
 *
 * Useful when a broker says "the insurer swears they replied but it
 * didn't show up". One glance at this surface answers:
 *   - did the reply reach our webhook at all? (matched / orphaned / error)
 *   - did it match a tender? (tender_id / offer_id set)
 *   - if it errored, what broke? (error_message)
 */

type StatusFilter = "" | "matched" | "orphaned" | "error" | "dedup";

const STATUS_LABEL: Record<Exclude<StatusFilter, "">, string> = {
  matched: "Matchet",
  orphaned: "Ukjent",
  error: "Feil",
  dedup: "Duplikat",
};

const STATUS_CLASS: Record<Exclude<StatusFilter, "">, string> = {
  matched: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  orphaned: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  error: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
  dedup: "bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-300",
};

export function InboundEmailSection() {
  const T = useT();
  const [status, setStatus] = useState<StatusFilter>("");
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);

  const cacheKey = `inbound-email-${status}-${limit}-${offset}`;
  const { data, isLoading, mutate } = useSWR<IncomingEmailLogPageOut>(
    cacheKey,
    () =>
      getInboundEmailLog({
        status: (status || undefined) as Exclude<StatusFilter, ""> | undefined,
        limit,
        offset,
      }),
  );

  const items: IncomingEmailLogEntryOut[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasMore = data?.has_more ?? false;

  return (
    <div className="broker-card">
      <div className="flex items-center justify-between mb-3">
        <SectionHeader
          title={T("Innkommende e-post")}
          subtitle={T(
            "Audit-spor for forsikringssvar som har truffet webhooken. Nyttig når et tilbud 'forsvinner'.",
          )}
        />
        <div className="flex items-center gap-2">
          <select
            value={limit}
            onChange={(e) => {
              setLimit(Number(e.target.value));
              setOffset(0);
            }}
            className="text-xs border border-border rounded px-2 py-1 bg-card focus:outline-none"
          >
            {[25, 50, 100, 200].map((v) => (
              <option key={v} value={v}>
                {v} {T("rader")}
              </option>
            ))}
          </select>
          <button
            onClick={() => mutate()}
            className="text-muted-foreground hover:text-foreground"
            aria-label={T("Oppdater")}
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Status filter chips */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-muted-foreground">{T("Status")}:</span>
        {([
          ["", "Alle"],
          ["matched", STATUS_LABEL.matched],
          ["orphaned", STATUS_LABEL.orphaned],
          ["error", STATUS_LABEL.error],
          ["dedup", STATUS_LABEL.dedup],
        ] as const).map(([key, label]) => {
          const active = status === key;
          return (
            <button
              key={key || "all"}
              type="button"
              onClick={() => {
                setStatus(key as StatusFilter);
                setOffset(0);
              }}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                active
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:bg-muted"
              }`}
            >
              {T(label)}
            </button>
          );
        })}
      </div>

      {data && total > 0 && (
        <p className="text-xs text-muted-foreground mb-2">
          {T("Viser")} {offset + 1}–{offset + items.length} {T("av")} {total}
        </p>
      )}

      {isLoading && <Loader2 className="w-5 h-5 animate-spin text-primary" />}
      {!isLoading && !items.length && (
        <p className="text-xs text-muted-foreground">
          {T("Ingen e-post matcher filteret.")}
        </p>
      )}

      {items.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  {["Mottatt", "Avsender", "Emne", "Status", "Tender", "Tilbud", "Vedlegg"].map(
                    (h) => (
                      <th
                        key={h}
                        className="text-left py-2 pr-3 text-muted-foreground font-semibold whitespace-nowrap"
                      >
                        {T(h)}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((r) => (
                  <tr key={r.id}>
                    <td className="py-2 pr-3 whitespace-nowrap text-muted-foreground">
                      {String(r.received_at).slice(0, 19).replace("T", " ")}
                    </td>
                    <td className="py-2 pr-3 text-foreground max-w-[240px] truncate" title={r.sender ?? ""}>
                      {r.sender ?? "–"}
                    </td>
                    <td className="py-2 pr-3 text-foreground max-w-[340px] truncate" title={r.subject ?? ""}>
                      {r.subject ?? "–"}
                    </td>
                    <td className="py-2 pr-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${
                          STATUS_CLASS[r.status as keyof typeof STATUS_CLASS] ??
                          "bg-muted text-muted-foreground"
                        }`}
                        title={r.error_message ?? ""}
                      >
                        {STATUS_LABEL[r.status as keyof typeof STATUS_LABEL] ?? r.status}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-muted-foreground">
                      {r.tender_id ? `#${r.tender_id}` : "–"}
                    </td>
                    <td className="py-2 pr-3 text-muted-foreground">
                      {r.offer_id ? `#${r.offer_id}` : "–"}
                    </td>
                    <td className="py-2 pr-3 text-muted-foreground">
                      {r.attachment_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-end gap-2 mt-3">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="text-xs px-2 py-1 rounded border border-border disabled:opacity-40"
            >
              {T("Forrige")}
            </button>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={!hasMore}
              className="text-xs px-2 py-1 rounded border border-border disabled:opacity-40"
            >
              {T("Neste")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
