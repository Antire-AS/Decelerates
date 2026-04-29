"use client";

import Link from "next/link";
import useSWR from "swr";
import { Sparkles, AlertTriangle, TrendingUp, ChevronRight } from "lucide-react";
import {
  getDashboardRecommendations,
  type DashboardRecommendationsOut,
} from "@/lib/api";
import { useT } from "@/lib/i18n";

const ICON_BY_KIND: Record<string, typeof Sparkles> = {
  pep: AlertTriangle,
  stale_narrative: Sparkles,
  peer_overage: TrendingUp,
};

const ICON_COLOR_BY_KIND: Record<string, string> = {
  pep: "text-amber-600",
  stale_narrative: "text-primary",
  peer_overage: "text-emerald-600",
};

export default function RecommendationsPanel() {
  const T = useT();
  const { data } = useSWR<DashboardRecommendationsOut>(
    "dashboard-recommendations",
    getDashboardRecommendations,
  );
  const items = data?.items ?? [];
  if (items.length === 0) return null;

  return (
    <div className="broker-card">
      <h2 className="text-sm font-semibold text-foreground mb-3">
        {T("AI-anbefalinger")}
      </h2>
      <div className="space-y-3">
        {items.map((r, i) => {
          const Icon = ICON_BY_KIND[r.kind] ?? Sparkles;
          const color = ICON_COLOR_BY_KIND[r.kind] ?? "text-muted-foreground";
          return (
            <div key={`${r.kind}-${r.orgnr}-${i}`} className="flex items-start gap-3">
              <Icon className={`w-4 h-4 ${color} shrink-0 mt-0.5`} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground">{r.headline}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{r.body}</p>
                <Link
                  href={r.cta_href}
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline mt-1.5"
                >
                  {r.cta_label}
                  <ChevronRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
