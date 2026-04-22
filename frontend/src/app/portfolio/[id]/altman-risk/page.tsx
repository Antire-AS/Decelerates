"use client";

import { use, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  ArrowLeft,
  ArrowDownRight,
  ArrowUpRight,
  Loader2,
  RefreshCw,
} from "lucide-react";
import {
  getPortfolio,
  getPortfolioAltmanRisk,
  refreshPortfolioAltmanRisk,
} from "@/lib/api";
import { useT } from "@/lib/i18n";

type ZoneKey = "safe" | "grey" | "distress" | "unknown";

const ZONE_META: Record<
  ZoneKey,
  { label: string; bg: string; text: string; bar: string }
> = {
  safe: { label: "Trygg", bg: "bg-green-100", text: "text-green-800", bar: "bg-green-500" },
  grey: { label: "Gråsone", bg: "bg-yellow-100", text: "text-yellow-800", bar: "bg-yellow-500" },
  distress: { label: "Nødsone", bg: "bg-red-100", text: "text-red-800", bar: "bg-red-500" },
  unknown: { label: "Ukjent", bg: "bg-muted", text: "text-muted-foreground", bar: "bg-muted-foreground/40" },
};

const ZONE_ORDER: ZoneKey[] = ["safe", "grey", "distress", "unknown"];

function fmtNok(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)} MNOK`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)} TNOK`;
  return `${v.toFixed(0)} NOK`;
}

export default function PortfolioAltmanRiskPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const T = useT();
  const { id } = use(params);
  const portfolioId = Number(id);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const { data: portfolio } = useSWR(`portfolio-${portfolioId}`, () =>
    getPortfolio(portfolioId),
  );
  const { data: risk, mutate } = useSWR(
    `portfolio-altman-${portfolioId}`,
    () => getPortfolioAltmanRisk(portfolioId),
  );

  async function handleRefresh() {
    setRefreshing(true);
    setErr(null);
    try {
      await refreshPortfolioAltmanRisk(portfolioId);
      await mutate();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setRefreshing(false);
    }
  }

  if (!risk) {
    return (
      <main className="p-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" /> {T("Laster")}…
        </div>
      </main>
    );
  }

  const zones = risk.zones || {};
  const transitions = risk.transitions ?? [];
  const companies = risk.companies ?? [];
  const totalCompanies = ZONE_ORDER.reduce((s, z) => s + (zones[z] || 0), 0);
  const pctFor = (z: ZoneKey) => (totalCompanies > 0 ? (zones[z] || 0) / totalCompanies : 0);

  const hasSnapshot = Boolean(risk.snapshot_at);

  return (
    <main className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href={`/portfolio/${portfolioId}`}
          className="text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-bold">
            {T("Altman-risikoprofil")} — {portfolio?.name ?? `#${portfolioId}`}
          </h1>
          {risk.snapshot_at && (
            <p className="text-xs text-muted-foreground">
              {T("Snapshot")}: {new Date(risk.snapshot_at).toLocaleString("nb-NO")}
              {risk.prev_snapshot_at && (
                <>
                  {" · "}
                  {T("forrige")}: {new Date(risk.prev_snapshot_at).toLocaleString("nb-NO")}
                </>
              )}
            </p>
          )}
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border border-muted-foreground/30 hover:bg-muted disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
          {hasSnapshot ? T("Oppdater snapshot") : T("Opprett snapshot")}
        </button>
      </div>

      {err && <p className="text-xs text-red-600">{err}</p>}

      {!hasSnapshot ? (
        <div className="broker-card text-sm text-muted-foreground">
          {T(
            "Ingen Altman-snapshot for denne porteføljen enda. Trykk «Opprett snapshot» for å generere den første målingen.",
          )}
        </div>
      ) : (
        <>
          {/* Summary number cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="broker-card">
              <div className="text-xs text-muted-foreground mb-1">
                {T("I nødsone")}
              </div>
              <div className="text-2xl font-bold text-red-600">
                {zones.distress || 0}
                <span className="text-sm text-muted-foreground ml-1">
                  / {totalCompanies}
                </span>
              </div>
            </div>
            <div className="broker-card">
              <div className="text-xs text-muted-foreground mb-1">
                {T("Premie i risiko")}
              </div>
              <div className="text-2xl font-bold text-foreground">
                {fmtNok(risk.premium_at_risk_nok)}
              </div>
              <div className="text-[11px] text-muted-foreground">
                {T("sum årspremie på aktive poliser i nødsone")}
              </div>
            </div>
            <div className="broker-card">
              <div className="text-xs text-muted-foreground mb-1">
                {T("Sonebytter siden forrige snapshot")}
              </div>
              <div className="text-2xl font-bold text-foreground">
                {transitions.length}
              </div>
            </div>
          </div>

          {/* Stacked zone distribution bar */}
          <div className="broker-card">
            <h2 className="text-sm font-semibold mb-2">
              {T("Sonefordeling")}
            </h2>
            <div className="flex h-4 rounded-md overflow-hidden">
              {ZONE_ORDER.map((z) => {
                const pct = pctFor(z) * 100;
                if (pct === 0) return null;
                return (
                  <div
                    key={z}
                    className={ZONE_META[z].bar}
                    style={{ width: `${pct}%` }}
                    title={`${ZONE_META[z].label}: ${zones[z]} (${pct.toFixed(0)}%)`}
                  />
                );
              })}
            </div>
            <div className="grid grid-cols-4 gap-2 mt-2 text-xs">
              {ZONE_ORDER.map((z) => (
                <div key={z} className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${ZONE_META[z].bar}`} />
                  <span className={ZONE_META[z].text}>{T(ZONE_META[z].label)}</span>
                  <span className="text-muted-foreground">{zones[z] || 0}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Transitions */}
          {transitions.length > 0 && (
            <div className="broker-card">
              <h2 className="text-sm font-semibold mb-3">
                {T("Sonebytter siden forrige snapshot")}
              </h2>
              <div className="space-y-1.5">
                {transitions.map((t) => {
                  const worsening =
                    t.prev_zone === "safe" ||
                    (t.prev_zone === "grey" && t.curr_zone === "distress");
                  return (
                    <div
                      key={t.orgnr}
                      className="flex items-center justify-between text-xs border-b border-muted pb-1.5 last:border-0"
                    >
                      <Link
                        href={`/search/${t.orgnr}`}
                        className="flex-1 font-medium hover:underline"
                      >
                        {t.navn || t.orgnr}
                      </Link>
                      <div className="flex items-center gap-1.5">
                        <span className="text-muted-foreground">
                          {t.prev_zone ? T(ZONE_META[t.prev_zone as ZoneKey]?.label ?? t.prev_zone) : "–"}
                        </span>
                        {worsening ? (
                          <ArrowDownRight className="w-3 h-3 text-red-600" />
                        ) : (
                          <ArrowUpRight className="w-3 h-3 text-green-600" />
                        )}
                        <span className={worsening ? "text-red-600 font-semibold" : "text-green-700 font-semibold"}>
                          {t.curr_zone ? T(ZONE_META[t.curr_zone as ZoneKey]?.label ?? t.curr_zone) : "–"}
                        </span>
                        {t.delta_z != null && (
                          <span className="text-muted-foreground ml-1">
                            (Δ {t.delta_z > 0 ? "+" : ""}
                            {t.delta_z.toFixed(2)})
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Ranked company table */}
          <div className="broker-card">
            <h2 className="text-sm font-semibold mb-3">
              {T("Alle selskaper — rangert etter Altman Z″")}
            </h2>
            <div className="space-y-1">
              {companies.map((c) => {
                const meta = ZONE_META[(c.zone as ZoneKey) ?? "unknown"];
                return (
                  <Link
                    key={c.orgnr}
                    href={`/search/${c.orgnr}`}
                    className="flex items-center gap-3 text-xs p-1.5 rounded hover:bg-muted"
                  >
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${meta.bg} ${meta.text}`}
                    >
                      {T(meta.label)}
                    </span>
                    <span className="flex-1">{c.navn || c.orgnr}</span>
                    <span className="text-muted-foreground w-20 text-right">
                      {c.z_score != null ? c.z_score.toFixed(2) : "–"}
                      <span className="opacity-60 ml-1">Z″</span>
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        </>
      )}
    </main>
  );
}
