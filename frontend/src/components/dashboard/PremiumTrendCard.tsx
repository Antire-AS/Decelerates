"use client";

import useSWR from "swr";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { TrendingUp, TrendingDown } from "lucide-react";
import { getPremiumTrend, type PremiumTrendOut } from "@/lib/api";
import { fmt } from "@/lib/format";
import { useT } from "@/lib/i18n";

const NB_MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Des"];

function fmtMnok(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)} M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)} K`;
  return v.toFixed(0);
}

function monthLabel(iso: string): string {
  const [y, m] = iso.split("-");
  const monthIdx = Number(m) - 1;
  if (monthIdx < 0 || monthIdx > 11) return iso;
  return `${NB_MONTHS[monthIdx]} ${y.slice(2)}`;
}

export default function PremiumTrendCard() {
  const T = useT();
  const { data, isLoading, error } = useSWR<PremiumTrendOut>(
    "dashboard-premium-trend",
    getPremiumTrend,
  );

  if (isLoading) {
    return <div className="broker-card h-48 animate-pulse bg-muted" />;
  }
  if (error || !data) return null;

  const points = data.months ?? [];
  const hasData = points.some((p) => p.premium_book > 0);
  if (!hasData) return null;

  const chartData = points.map((p) => ({ name: monthLabel(p.month), value: p.premium_book }));
  const latest = points[points.length - 1]?.premium_book ?? 0;
  const yoy = data.yoy_delta_pct;

  return (
    <div className="broker-card">
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-xs text-muted-foreground font-medium">{T("Samlet premievolum")}</p>
          <p className="text-2xl font-bold text-foreground">kr {fmt(latest)}</p>
        </div>
        {yoy !== null && yoy !== undefined && (
          <span
            className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded ${
              yoy >= 0 ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
            }`}
          >
            {yoy >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            {yoy >= 0 ? "+" : ""}{yoy.toFixed(1)}% {T("12 mnd")}
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <BarChart data={chartData} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={fmtMnok} tickLine={false} axisLine={false} width={40} />
          <Tooltip formatter={(v: number) => [`kr ${fmt(v)}`, T("Premievolum")]} />
          <Bar dataKey="value" fill="#4A6FA5" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
