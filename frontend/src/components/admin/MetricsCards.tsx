"use client";

import useSWR from "swr";
import { getAdminMetrics, type AdminMetricsOut } from "@/lib/api";
import { useT } from "@/lib/i18n";

function fmtBytes(b: number): string {
  if (b >= 1e9) return `${(b / 1e9).toFixed(1)} GB`;
  if (b >= 1e6) return `${(b / 1e6).toFixed(1)} MB`;
  return `${(b / 1e3).toFixed(0)} KB`;
}

function fmtNumber(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return String(n);
}

export default function MetricsCards() {
  const T = useT();
  const { data } = useSWR<AdminMetricsOut>("admin-metrics", getAdminMetrics);

  if (!data) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="broker-card h-24 animate-pulse bg-muted" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div className="broker-card">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{T("Aktive brukere")}</p>
        <p className="text-3xl font-bold mt-1 text-foreground tabular-nums">{data.total_users}</p>
        <p className="text-xs text-muted-foreground mt-1">
          {data.admin_count} {T("admin")} · {data.broker_count} {T("meglere")}
        </p>
      </div>
      <div className="broker-card">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{T("API-kall siste 24t")}</p>
        <p className="text-3xl font-bold mt-1 text-foreground tabular-nums">
          {fmtNumber(data.api_calls_24h)}
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          {data.api_success_pct != null ? `${data.api_success_pct.toFixed(1)}% ${T("suksess")}` : T("Logging ikke aktivert")}
        </p>
      </div>
      <div className="broker-card">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{T("AI-tokens i dag")}</p>
        <p className="text-3xl font-bold mt-1 text-foreground tabular-nums">
          {fmtNumber(data.ai_tokens_today)}
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          {data.ai_tokens_budget
            ? `${Math.round((data.ai_tokens_today / data.ai_tokens_budget) * 100)}% ${T("av månedsbudsjett")}`
            : T("Ingen budsjettcap satt")}
        </p>
      </div>
      <div className="broker-card">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{T("Lagring (PG)")}</p>
        <p className="text-3xl font-bold mt-1 text-foreground tabular-nums">
          {fmtBytes(data.storage_bytes)}
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          {data.storage_capacity_bytes
            ? `${Math.round((data.storage_bytes / data.storage_capacity_bytes) * 100)}% ${T("av kapasitet")}`
            : T("Ukjent kapasitet")}
        </p>
      </div>
    </div>
  );
}
