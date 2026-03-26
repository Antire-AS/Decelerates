"use client";

import { useState } from "react";
import useSWR from "swr";
import { getRenewals, type Renewal } from "@/lib/api";

function fmt(n: number) {
  return new Intl.NumberFormat("nb-NO").format(n);
}

function fmtDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("nb-NO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function urgencyClass(days: number) {
  if (days <= 14) return "bg-red-100 text-red-700";
  if (days <= 30) return "bg-amber-100 text-amber-700";
  return "bg-green-100 text-green-700";
}

const DAYS_OPTIONS = [30, 60, 90, 180];

export default function RenewalsPage() {
  const [days, setDays] = useState(90);

  const { data: renewals, isLoading } = useSWR<Renewal[]>(
    ["renewals", days],
    () => getRenewals(days),
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#2C3E50]">Fornyelser</h1>
          <p className="text-sm text-[#8A7F74] mt-1">
            Kommende polisefornyelseringer som krever oppfølging
          </p>
        </div>

        {/* Days filter */}
        <div className="flex gap-1">
          {DAYS_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                days === d
                  ? "bg-[#2C3E50] text-white"
                  : "bg-[#EDE8E3] text-[#8A7F74] hover:bg-[#DDD8D3]"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="broker-card space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-8 rounded animate-pulse bg-[#EDE8E3]" />
          ))}
        </div>
      )}

      {/* Renewals table */}
      {!isLoading && renewals && renewals.length > 0 && (
        <div className="broker-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                <th className="text-left pb-2 font-medium">Klient</th>
                <th className="text-left pb-2 font-medium">Forsikringstype</th>
                <th className="text-left pb-2 font-medium">Forsikringsgiver</th>
                <th className="text-right pb-2 font-medium">Premie (kr)</th>
                <th className="text-right pb-2 font-medium">Fornyelsesdato</th>
                <th className="text-right pb-2 font-medium">Dager igjen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDE8E3]">
              {renewals.map((r) => (
                <tr key={r.id} className="hover:bg-[#F9F7F4]">
                  <td className="py-2">
                    <span className="font-medium text-[#2C3E50]">{r.client_name}</span>
                    <span className="block text-xs text-[#8A7F74]">{r.orgnr}</span>
                  </td>
                  <td className="py-2 text-[#2C3E50]">{r.insurance_type}</td>
                  <td className="py-2 text-[#8A7F74]">{r.insurer}</td>
                  <td className="py-2 text-right font-medium text-[#2C3E50]">
                    {fmt(r.premium)}
                  </td>
                  <td className="py-2 text-right text-[#8A7F74]">
                    {fmtDate(r.renewal_date)}
                  </td>
                  <td className="py-2 text-right">
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded-full ${urgencyClass(r.days_until_renewal)}`}
                    >
                      {r.days_until_renewal}d
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-[#8A7F74] mt-3">
            Viser {renewals.length} fornyelse(r) innen {days} dager
          </p>
        </div>
      )}

      {!isLoading && renewals && renewals.length === 0 && (
        <div className="broker-card text-center py-12">
          <p className="text-sm font-medium text-[#2C3E50]">Ingen kommende fornyelser</p>
          <p className="text-xs text-[#8A7F74] mt-1">
            Ingen avtaler forfaller innen de neste {days} dagene.
          </p>
        </div>
      )}

      {!isLoading && !renewals && (
        <div className="broker-card text-center py-12">
          <p className="text-sm text-[#8A7F74]">
            Ingen data tilgjengelig. Legg til avtaler via selskapsprofilene.
          </p>
        </div>
      )}
    </div>
  );
}
