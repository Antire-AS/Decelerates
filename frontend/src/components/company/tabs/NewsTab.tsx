"use client";

import { useState } from "react";
import useSWR from "swr";
import { AlertTriangle, ExternalLink, Loader2, RefreshCw } from "lucide-react";
import { getOrgNews, refreshOrgNews, type CompanyNewsItem } from "@/lib/api";
import { useT } from "@/lib/i18n";

interface Props {
  orgnr: string;
}

const EVENT_BADGE: Record<string, { label: string; bg: string; text: string }> = {
  lawsuit: { label: "Søksmål", bg: "bg-red-100", text: "text-red-800" },
  mgmt_change: { label: "Ledelse", bg: "bg-amber-100", text: "text-amber-800" },
  credit_event: { label: "Kreditthendelse", bg: "bg-orange-100", text: "text-orange-800" },
  bankruptcy: { label: "Konkurs", bg: "bg-red-200", text: "text-red-900" },
  ma: { label: "Oppkjøp/fusjon", bg: "bg-blue-100", text: "text-blue-800" },
  other: { label: "Annet", bg: "bg-muted", text: "text-muted-foreground" },
};

function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 60) return `${mins} min siden`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs} t siden`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days} d siden`;
  const months = Math.round(days / 30);
  return `${months} md siden`;
}

export default function NewsTab({ orgnr }: Props) {
  const T = useT();
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [onlyMaterial, setOnlyMaterial] = useState(false);

  const { data, mutate, isLoading } = useSWR(
    `news-${orgnr}-${onlyMaterial}`,
    () => getOrgNews(orgnr, onlyMaterial),
  );

  async function handleRefresh(): Promise<void> {
    setRefreshing(true);
    setErr(null);
    try {
      await refreshOrgNews(orgnr);
      await mutate();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setRefreshing(false);
    }
  }

  const items: CompanyNewsItem[] = data?.items ?? [];
  const materialCount = items.filter((i) => i.material).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-foreground">
            {T("Nyhetsovervåking")}
          </h2>
          <p className="text-xs text-muted-foreground">
            {T("Hentet fra åpne nyhetskilder og klassifisert av AI.")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={onlyMaterial}
              onChange={(e) => setOnlyMaterial(e.target.checked)}
              className="accent-primary"
            />
            {T("Kun materielle")}
          </label>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border border-muted-foreground/30 hover:bg-muted disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            {T("Oppdater")}
          </button>
        </div>
      </div>

      {err && <p className="text-xs text-red-600">{err}</p>}

      {materialCount > 0 && !onlyMaterial && (
        <div className="inline-flex items-center gap-1.5 text-xs bg-red-50 border border-red-200 px-2 py-1 rounded-md text-red-700">
          <AlertTriangle className="w-3.5 h-3.5" />
          {materialCount} {T("materielle hendelser")}
        </div>
      )}

      {isLoading && items.length === 0 ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> {T("Laster")}…
        </div>
      ) : items.length === 0 ? (
        <div className="broker-card text-sm text-muted-foreground">
          {T(
            "Ingen nyheter lagret enda. Trykk «Oppdater» for å hente ferske artikler.",
          )}
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => {
            const badge = item.event_type
              ? EVENT_BADGE[item.event_type] ?? EVENT_BADGE.other
              : EVENT_BADGE.other;
            return (
              <li
                key={item.id}
                className={`broker-card ${item.material ? "border-l-4 border-red-400" : ""}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-medium text-foreground hover:underline inline-flex items-start gap-1"
                    >
                      {item.headline}
                      <ExternalLink className="w-3 h-3 mt-1 flex-shrink-0 opacity-60" />
                    </a>
                    {item.summary && (
                      <p className="text-xs text-muted-foreground mt-1 italic">
                        {item.summary}
                      </p>
                    )}
                    {item.snippet && !item.summary && (
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {item.snippet}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5 text-[11px] text-muted-foreground">
                      {item.source && <span>{item.source}</span>}
                      {item.published_at && (
                        <>
                          <span>·</span>
                          <span>{fmtRelative(item.published_at)}</span>
                        </>
                      )}
                    </div>
                  </div>
                  {item.material && (
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${badge.bg} ${badge.text}`}
                    >
                      {T(badge.label)}
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
