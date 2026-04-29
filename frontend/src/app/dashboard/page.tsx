"use client";

import Link from "next/link";
import useSWR from "swr";
import { getDashboard, getCompanies, getRenewals, type DashboardData, type Company, type Renewal } from "@/lib/api";
import MetricCard from "@/components/dashboard/MetricCard";
import RiskBadge from "@/components/company/RiskBadge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Search, BarChart2, AlertTriangle, ClipboardCheck, FilePlus2, Calendar, ChevronRight } from "lucide-react";
import { fmt } from "@/lib/format";
import { useT } from "@/lib/i18n";

const ACTIVITY_ICONS: Record<string, string> = {
  call: "📞", email: "📧", meeting: "🤝", note: "📝", task: "✅",
};


export default function DashboardPage() {
  const T = useT();
  const { data, isLoading: dashLoading, error: dashError, mutate: retryDash } = useSWR<DashboardData>(
    "dashboard",
    getDashboard,
    { refreshInterval: 60_000 },
  );
  const { data: companies } = useSWR<Company[]>(
    "companies-recent",
    () => getCompanies(5),
  );

  const hasCrm = Boolean(data && (data.total_active_policies ?? 0) > 0);

  const shouldFetchRenewals = hasCrm && (data?.renewals_30d ?? 0) > 0;
  const { data: renewals } = useSWR<Renewal[]>(
    shouldFetchRenewals ? "dashboard-top-renewals" : null,
    () => getRenewals(30),
  );
  const topRenewals = (renewals ?? [])
    .slice()
    .sort((a, b) => a.days_until_renewal - b.days_until_renewal)
    .slice(0, 3);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">{T("Velkommen")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Forsikringsmegling · Due Diligence · Risikoprofil
        </p>
      </div>

      {dashError && (
        <Alert variant="destructive">
          <AlertTitle>Kunne ikke laste dashboard</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{dashError instanceof Error ? dashError.message : "Ukjent feil."}</span>
            <button
              onClick={() => retryDash()}
              className="px-3 py-1 rounded-md border border-brand-stone text-xs text-brand-dark hover:bg-brand-beige"
            >
              Prøv igjen
            </button>
          </AlertDescription>
        </Alert>
      )}

      {/* Key metrics */}
      {dashLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="broker-card h-20 animate-pulse bg-muted" />
          ))}
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label={T("Fornyelser neste 30 dager")}
              value={data.renewals_30d}
              help={`kr ${fmt(data.premium_at_risk_30d)} i premie`}
            />
            <MetricCard label={T("Aktive avtaler")}     value={data.total_active_policies} />
            <MetricCard label={T("Åpne skader")}        value={data.open_claims} />
            <MetricCard label={T("Aktiviteter forfalt")} value={data.activities_due} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Premium book */}
            <div className="broker-card space-y-2">
              <p className="text-xs text-muted-foreground font-medium">Samlet premievolum</p>
              <p className="text-2xl font-bold text-foreground">
                kr {fmt(data.total_premium_book)}
              </p>
              {data.renewals_90d > 0 && (
                <p className="text-xs text-brand-warning">
                  ⚠️ {data.renewals_90d} avtale(r) forfaller innen 90 dager
                </p>
              )}
            </div>

            {/* Renewal alert */}
            <div className="broker-card flex items-start gap-3">
              {data.renewals_30d > 0 ? (
                <>
                  <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {data.renewals_30d} avtale(r) forfaller innen 30 dager
                    </p>
                    <p className="text-xs text-muted-foreground">
                      kr {fmt(data.premium_at_risk_30d)} i premie er til fornyelse
                    </p>
                  </div>
                </>
              ) : hasCrm ? (
                <p className="text-sm text-brand-success">
                  ✓ Ingen avtaler forfaller de neste 30 dagene
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">Ingen aktive avtaler ennå</p>
              )}
            </div>
          </div>

          {/* Top 3 upcoming renewals — surfaces the actual policies, so the
              broker doesn't have to bounce to /renewals just to see what's
              landing. Only renders when ≥1 renewal is due in 30 days. */}
          {topRenewals.length > 0 && (
            <div className="broker-card">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-foreground">
                  Forfaller først
                </h2>
                <Link
                  href="/renewals"
                  className="text-xs text-primary hover:underline flex items-center gap-1"
                >
                  Se alle
                  <ChevronRight className="w-3 h-3" />
                </Link>
              </div>
              <div className="space-y-2">
                {topRenewals.map((r) => {
                  const days = r.days_until_renewal;
                  const urgencyClass =
                    days <= 14 ? "text-red-700 bg-red-100"
                    : days <= 30 ? "text-amber-700 bg-amber-100"
                    : "text-muted-foreground bg-muted";
                  const premium = r.annual_premium_nok ?? r.premium ?? 0;
                  return (
                    <Link
                      key={r.id}
                      href={`/search/${r.orgnr}`}
                      className="flex items-center gap-3 px-3 py-2 -mx-3 rounded-md hover:bg-muted transition-colors"
                    >
                      <Calendar className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-foreground truncate">
                          {r.client_name}
                        </p>
                        <p className="text-xs text-muted-foreground truncate">
                          {r.product_type ?? r.insurance_type} · kr {fmt(premium)}
                        </p>
                      </div>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${urgencyClass}`}>
                        {days <= 0 ? "I dag" : `${days} d`}
                      </span>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}

          {/* Recent activities */}
          {data.recent_activities?.length > 0 && (
            <div className="broker-card">
              <h2 className="text-sm font-semibold text-foreground mb-3">
                Siste aktiviteter
              </h2>
              <div className="space-y-2">
                {data.recent_activities.map((a) => (
                  <div key={a.id} className="flex items-start gap-2 text-sm">
                    <span className="mt-0.5">{ACTIVITY_ICONS[a.type] ?? "•"}</span>
                    <span
                      className={a.completed ? "line-through text-muted-foreground" : "text-foreground"}
                    >
                      {a.subject}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {a.created_by}
                      {a.orgnr && ` · ${a.orgnr}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Hurtighandlinger — verb-first quick actions matching mockup 135111
          (megler-bilder polish §3 partial). Each card answers "what's the
          next thing I should do?" rather than just listing destinations. */}
      <div className="broker-card">
        <h2 className="text-sm font-semibold text-foreground mb-3">{T("Hurtighandlinger")}</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { href: "/search",     label: T("Søk selskap"),       icon: Search,         hint: "⌘K" },
            { href: "/idd",        label: T("Ny behovsanalyse"),  icon: ClipboardCheck, hint: null },
            { href: "/tenders",    label: T("Generer anbudspakke"), icon: FilePlus2,    hint: null },
            { href: "/portfolio",  label: T("Vis portefølje"),    icon: BarChart2,      hint: null },
          ].map(({ href, label, icon: Icon, hint }) => (
            <Link
              key={href}
              href={href}
              className="group relative flex flex-col items-start gap-1.5 px-4 py-3 rounded-lg
                         bg-primary text-primary-foreground text-sm font-medium
                         hover:bg-primary/90 transition-colors"
            >
              <div className="flex items-center gap-2 w-full">
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span className="flex-1">{label}</span>
                {hint && (
                  <kbd
                    className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-primary-foreground/20 text-primary-foreground/90"
                    aria-hidden
                  >
                    {hint}
                  </kbd>
                )}
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Companies in DB (shown when no CRM data yet) */}
      {!hasCrm && companies && companies.length > 0 && (
        <div className="broker-card">
          <h2 className="text-sm font-semibold text-foreground mb-3">
            Selskaper i databasen
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-muted-foreground border-b border-border">
                <th className="text-left pb-2 font-medium">Selskap</th>
                <th className="text-left pb-2 font-medium">Bransje</th>
                <th className="text-left pb-2 font-medium">Kommune</th>
                <th className="text-left pb-2 font-medium">Risiko</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {companies.map((c) => (
                <tr key={c.orgnr} className="hover:bg-muted">
                  <td className="py-2 font-medium text-foreground">
                    <Link href={`/search/${c.orgnr}`} className="hover:underline">
                      {c.navn ?? c.orgnr}
                    </Link>
                  </td>
                  <td className="py-2 text-muted-foreground text-xs max-w-[140px] truncate">
                    {(c.naeringskode1_beskrivelse ?? "").slice(0, 30)}
                  </td>
                  <td className="py-2 text-muted-foreground text-xs">{c.kommune ?? "–"}</td>
                  <td className="py-2">
                    <RiskBadge score={c.risk_score} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!hasCrm && (
        <div className="broker-card bg-accent border-border">
          <p className="text-sm text-foreground">
            <strong>Kom i gang:</strong> Gå til{" "}
            <Link href="/admin" className="text-primary underline">Admin</Link>{" "}
            og trykk <em>Seed CRM demo-data</em> for å fylle opp med realistiske testdata.
          </p>
        </div>
      )}
    </div>
  );
}
