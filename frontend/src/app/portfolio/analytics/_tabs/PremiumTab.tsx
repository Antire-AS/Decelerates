"use client";

import useSWR from "swr";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";
import { Loader2 } from "lucide-react";
import { getPremiumAnalytics, type PremiumAnalytics } from "@/lib/api";
import { COLORS, fmt, fmtMnok, MetricCard } from "./_shared";

export default function PremiumTab() {
  const { data, isLoading, error } = useSWR<PremiumAnalytics>("premium-analytics", getPremiumAnalytics);

  if (isLoading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-[#4A6FA5]" /></div>;
  if (error || !data) return <div className="broker-card text-center py-10 text-sm text-[#8A7F74]">Ingen policyer registrert ennå. Legg til policyer i Selskapsøk → CRM-fanen.</div>;

  const insurerData = (data.by_insurer ?? []).map((b) => ({ name: b.insurer, value: b.total_premium, count: b.count, pct: b.share_pct }));
  const productData = (data.by_product ?? []).map((b) => ({ name: b.product_type, value: b.total_premium, count: b.count, pct: b.share_pct }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Total premievolum" value={fmtMnok(data.total_premium_book)} />
        <MetricCard label="Aktive avtaler" value={String(data.active_policy_count ?? 0)} />
        <MetricCard label="Forfaller 90 dager" value={fmtMnok(data.renewals_90d_premium)} />
        <MetricCard label="Snitt per avtale" value={fmt(data.avg_premium_per_policy)} sub="kr" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {insurerData.length > 0 && (
          <div className="broker-card">
            <h3 className="text-sm font-semibold text-[#2C3E50] mb-4">Premie per forsikringsselskap</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={insurerData} layout="vertical" margin={{ left: 8, right: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v / 1e6).toFixed(0)}M`} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={110} />
                <Tooltip formatter={(v: number) => [`kr ${fmt(v)}`, "Premie"]} />
                <Bar dataKey="value" fill="#4A6FA5" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-3 space-y-1.5">
              {insurerData.map((d, i) => (
                <div key={d.name} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                    <span className="text-[#2C3E50]">{d.name}</span>
                  </div>
                  <span className="text-[#8A7F74]">{d.count} avtaler · {d.pct.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {productData.length > 0 && (
          <div className="broker-card">
            <h3 className="text-sm font-semibold text-[#2C3E50] mb-4">Premie per produkttype</h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={productData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                  innerRadius={50} outerRadius={90}
                  label={({ percent }) => percent > 0.05 ? `${(percent * 100).toFixed(0)}%` : ""}
                  labelLine={false}>
                  {productData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v: number) => `kr ${fmt(v)}`} />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-2 space-y-1.5">
              {productData.map((d, i) => (
                <div key={d.name} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                    <span className="text-[#2C3E50]">{d.name}</span>
                  </div>
                  <span className="text-[#8A7F74]">{d.count} avtaler · {d.pct.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {(data.by_status ?? []).length > 0 && (
        <div className="broker-card">
          <h3 className="text-sm font-semibold text-[#2C3E50] mb-3">Fordeling per status</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-[#8A7F74] border-b border-[#EDE8E3]">
                  <th className="text-left pb-2 font-medium">Status</th>
                  <th className="text-right pb-2 font-medium">Avtaler</th>
                  <th className="text-right pb-2 font-medium">Premie (kr)</th>
                  <th className="text-right pb-2 font-medium">Andel</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EDE8E3]">
                {data.by_status.map((s) => (
                  <tr key={s.status} className="hover:bg-[#F9F7F4]">
                    <td className="py-2 text-[#2C3E50] capitalize">{s.status}</td>
                    <td className="py-2 text-right text-[#8A7F74]">{s.count}</td>
                    <td className="py-2 text-right font-medium text-[#2C3E50]">{fmt(s.total_premium)}</td>
                    <td className="py-2 text-right text-[#8A7F74]">{s.share_pct.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
