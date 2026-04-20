"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import { useT } from "@/lib/i18n";

interface IndustryRow {
  name: string;
  count: number;
}

interface RiskRow {
  name: string;
  score?: number;
  orgnr: string;
}

interface Props {
  industryData: IndustryRow[];
  top15Risk: RiskRow[];
  analyticsTab: "industry" | "top-risk";
  setAnalyticsTab: (tab: "industry" | "top-risk") => void;
}

export function PortfolioAnalytics({ industryData, top15Risk, analyticsTab, setAnalyticsTab }: Props) {
  const T = useT();
  return (
    <div className="broker-card">
      <div className="flex items-center gap-2 mb-3">
        <button onClick={() => setAnalyticsTab("industry")}
          className={`text-xs px-2.5 py-1 rounded-lg ${analyticsTab === "industry" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}>
          {T("Bransje")}
        </button>
        <button onClick={() => setAnalyticsTab("top-risk")}
          className={`text-xs px-2.5 py-1 rounded-lg ${analyticsTab === "top-risk" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}>
          {T("Top 15 risiko")}
        </button>
      </div>
      {analyticsTab === "top-risk" && (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={top15Risk} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10 }} domain={[0, 100]} />
            <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 9 }} />
            <Tooltip formatter={(v: number) => [`${v} / 100`]} />
            <Bar dataKey="score" name={T("Risikoscore")} fill="#C0392B" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
      {analyticsTab === "industry" && (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={industryData} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#EDE8E3" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10 }} />
            <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 9 }} />
            <Tooltip formatter={(v: number) => [`${v} ${T("selskaper")}`]} />
            <Bar dataKey="count" name={T("Selskaper")} fill="#4A6FA5" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
