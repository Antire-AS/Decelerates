"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { getDashboard, getCompanies, type DashboardData, type Company } from "@/lib/api";
import MetricCard from "@/components/dashboard/MetricCard";
import RiskBadge from "@/components/company/RiskBadge";
import { Search, RotateCcw, BarChart2, FolderOpen, AlertTriangle } from "lucide-react";
import { fmt } from "@/lib/format";

const ACTIVITY_ICONS: Record<string, string> = {
  call: "📞", email: "📧", meeting: "🤝", note: "📝", task: "✅",
};


export default function DashboardPage() {
  const { data, isLoading: dashLoading } = useSWR<DashboardData>(
    "dashboard",
    getDashboard,
    { refreshInterval: 60_000 },
  );
  const { data: companies } = useSWR<Company[]>(
    "companies-recent",
    () => getCompanies(5),
  );

  const hasCrm = Boolean(data && (data.total_active_policies ?? 0) > 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[#2C3E50]">Velkommen</h1>
        <p className="text-sm text-[#8A7F74] mt-1">
          Forsikringsmegling · Due Diligence · Risikoprofil
        </p>
      </div>

      {/* Key metrics */}
      {dashLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="broker-card h-20 animate-pulse bg-[#EDE8E3]" />
          ))}
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label="Fornyelser neste 30 dager"
              value={data.renewals_30d}
              help={`kr ${fmt(data.premium_at_risk_30d)} i premie`}
            />
            <MetricCard label="Aktive avtaler"     value={data.total_active_policies} />
            <MetricCard label="Åpne skader"        value={data.open_claims} />
            <MetricCard label="Aktiviteter forfalt" value={data.activities_due} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Premium book */}
            <div className="broker-card space-y-2">
              <p className="text-xs text-[#8A7F74] font-medium">Samlet premievolum</p>
              <p className="text-2xl font-bold text-[#2C3E50]">
                kr {fmt(data.total_premium_book)}
              </p>
              {data.renewals_90d > 0 && (
                <p className="text-xs text-[#C8A951]">
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
                    <p className="text-sm font-semibold text-[#2C3E50]">
                      {data.renewals_30d} avtale(r) forfaller innen 30 dager
                    </p>
                    <p className="text-xs text-[#8A7F74]">
                      kr {fmt(data.premium_at_risk_30d)} i premie er til fornyelse
                    </p>
                  </div>
                </>
              ) : hasCrm ? (
                <p className="text-sm text-[#5A8A5A]">
                  ✓ Ingen avtaler forfaller de neste 30 dagene
                </p>
              ) : (
                <p className="text-sm text-[#8A7F74]">Ingen aktive avtaler ennå</p>
              )}
            </div>
          </div>

          {/* Recent activities */}
          {data.recent_activities?.length > 0 && (
            <div className="broker-card">
              <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">
                Siste aktiviteter
              </h2>
              <div className="space-y-2">
                {data.recent_activities.map((a) => (
                  <div key={a.id} className="flex items-start gap-2 text-sm">
                    <span className="mt-0.5">{ACTIVITY_ICONS[a.type] ?? "•"}</span>
                    <span
                      className={a.completed ? "line-through text-[#8A7F74]" : "text-[#2C3E50]"}
                    >
                      {a.subject}
                    </span>
                    <span className="ml-auto text-xs text-[#8A7F74]">
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

      {/* Quick navigation */}
      <div className="broker-card">
        <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">Hurtignavigering</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { href: "/search",    label: "Selskapsøk",  icon: Search },
            { href: "/renewals",  label: "Fornyelser",  icon: RotateCcw },
            { href: "/portfolio", label: "Portefølje",  icon: BarChart2 },
            { href: "/documents", label: "Dokumenter",  icon: FolderOpen },
          ].map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="flex items-center justify-center gap-2 px-4 py-3 rounded-lg
                         bg-[#2C3E50] text-white text-sm font-medium
                         hover:bg-[#3d5166] transition-colors"
            >
              <Icon className="w-4 h-4" />
              {label}
            </Link>
          ))}
        </div>
      </div>

      {/* Companies in DB (shown when no CRM data yet) */}
      {!hasCrm && companies && companies.length > 0 && (
        <div className="broker-card">
          <h2 className="text-sm font-semibold text-[#2C3E50] mb-3">
            Selskaper i databasen
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                <th className="text-left pb-2 font-medium">Selskap</th>
                <th className="text-left pb-2 font-medium">Bransje</th>
                <th className="text-left pb-2 font-medium">Kommune</th>
                <th className="text-left pb-2 font-medium">Risiko</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDE8E3]">
              {companies.map((c) => (
                <tr key={c.orgnr} className="hover:bg-[#F9F7F4]">
                  <td className="py-2 font-medium text-[#2C3E50]">
                    <Link href={`/search/${c.orgnr}`} className="hover:underline">
                      {c.navn ?? c.orgnr}
                    </Link>
                  </td>
                  <td className="py-2 text-[#8A7F74] text-xs max-w-[140px] truncate">
                    {(c.naeringskode1_beskrivelse ?? "").slice(0, 30)}
                  </td>
                  <td className="py-2 text-[#8A7F74] text-xs">{c.kommune ?? "–"}</td>
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
        <div className="broker-card bg-[#EEF4FC] border-[#C5D8F0]">
          <p className="text-sm text-[#2C3E50]">
            <strong>Kom i gang:</strong> Gå til{" "}
            <Link href="/admin" className="text-[#4A6FA5] underline">Admin</Link>{" "}
            og trykk <em>Seed CRM demo-data</em> for å fylle opp med realistiske testdata.
          </p>
        </div>
      )}
    </div>
  );
}
