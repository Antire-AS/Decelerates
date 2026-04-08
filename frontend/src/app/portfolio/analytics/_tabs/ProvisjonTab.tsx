"use client";

import useSWR from "swr";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { Loader2 } from "lucide-react";
import { getCommissionAnalytics, type CommissionAnalytics } from "@/lib/api";
import { fmt, fmtMnok, MetricCard } from "./_shared";

// Typical Norwegian broker commission ranges by product type (industry reference)
const TYPICAL_RATES: Record<string, string> = {
  "Motorvognforsikring":      "5–12%",
  "Næringseiendom":           "10–17.5%",
  "Reiseforsikring":          "10–20%",
  "Ansvarsforsikring":        "8–15%",
  "Personforsikring":         "10–20%",
  "Yrkesskadeforsikring":     "5–10%",
  "Cyberforsikring":          "10–18%",
  "Styreansvarsforsikring":   "8–15%",
};

export default function ProvisjonTab() {
  const { data, isLoading, error } = useSWR<CommissionAnalytics>(
    "commission-analytics", getCommissionAnalytics,
  );

  if (isLoading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-[#4A6FA5]" /></div>;
  if (error || !data) return (
    <div className="broker-card text-center py-10 text-sm text-[#8A7F74]">
      Ingen provisjonsdata ennå. Legg til provisjonssats på policyer i Selskapsøk → CRM-fanen.
    </div>
  );

  const byProduct = data.by_product ?? [];
  const byInsurer = data.by_insurer ?? [];

  return (
    <div className="space-y-6">
      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <MetricCard label="Total provisjon (estimert)" value={fmtMnok(data.total_commission_nok)} />
        <MetricCard label="Policyer med provisjon" value={String(data.policy_count)} />
        <MetricCard
          label="Gj.snitt provisjonsandel"
          value={byProduct.length
            ? `${(byProduct.reduce((s, r) => s + r.avg_rate_pct, 0) / byProduct.length).toFixed(1)}%`
            : "–"}
          sub="av premievolum"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {byProduct.length > 0 && (
          <div className="broker-card">
            <h3 className="text-sm font-semibold text-[#2C3E50] mb-4">Provisjon per produkttype</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={byProduct} layout="vertical" margin={{ left: 8, right: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v / 1e3).toFixed(0)}k`} />
                <YAxis type="category" dataKey="product_type" tick={{ fontSize: 10 }} width={130} />
                <Tooltip formatter={(v: number) => [`kr ${fmt(v)}`, "Provisjon"]} />
                <Bar dataKey="commission" fill="#C8A951" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {byInsurer.length > 0 && (
          <div className="broker-card">
            <h3 className="text-sm font-semibold text-[#2C3E50] mb-4">Provisjon per forsikringsselskap</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={byInsurer} layout="vertical" margin={{ left: 8, right: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v / 1e3).toFixed(0)}k`} />
                <YAxis type="category" dataKey="insurer" tick={{ fontSize: 10 }} width={110} />
                <Tooltip formatter={(v: number) => [`kr ${fmt(v)}`, "Provisjon"]} />
                <Bar dataKey="commission" fill="#4A6FA5" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Rate table */}
      {byProduct.length > 0 && (
        <div className="broker-card overflow-x-auto">
          <h3 className="text-sm font-semibold text-[#2C3E50] mb-3">Provisjon per produkttype — detaljer</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                <th className="text-left pb-2 font-medium">Produkttype</th>
                <th className="text-right pb-2 font-medium">Avtaler</th>
                <th className="text-right pb-2 font-medium">Premie (kr)</th>
                <th className="text-right pb-2 font-medium">Provisjon (kr)</th>
                <th className="text-right pb-2 font-medium">Gj.snitt %</th>
                <th className="text-right pb-2 font-medium hidden md:table-cell">Typisk bransje</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EDE8E3]">
              {byProduct.map((r) => (
                <tr key={r.product_type} className="hover:bg-[#F9F7F4]">
                  <td className="py-2 text-[#2C3E50] font-medium">{r.product_type}</td>
                  <td className="py-2 text-right text-[#8A7F74]">{r.count}</td>
                  <td className="py-2 text-right text-[#8A7F74]">{fmt(r.premium)}</td>
                  <td className="py-2 text-right font-semibold text-[#C8A951]">{fmt(r.commission)}</td>
                  <td className="py-2 text-right text-[#2C3E50]">{r.avg_rate_pct.toFixed(1)}%</td>
                  <td className="py-2 text-right text-[#8A7F74] hidden md:table-cell text-xs">
                    {TYPICAL_RATES[r.product_type] ?? "–"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Reference rates */}
      <details className="broker-card">
        <summary className="text-sm font-semibold text-[#2C3E50] cursor-pointer">
          Typiske provisjonssatser (bransjereferanse)
        </summary>
        <p className="text-xs text-[#8A7F74] mt-2 mb-3">
          Provisjonssatser er konfidensielle bilaterale avtaler mellom megler og forsikringsselskap.
          Disse er typiske markedsintervaller — ikke bindende tall.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {Object.entries(TYPICAL_RATES).map(([product, range]) => (
            <div key={product} className="rounded-lg bg-[#F9F7F4] border border-[#EDE8E3] px-3 py-2">
              <p className="text-xs font-medium text-[#2C3E50]">{product}</p>
              <p className="text-sm font-bold text-[#C8A951]">{range}</p>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
