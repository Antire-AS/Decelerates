"use client";

import { useRiskConfig } from "@/lib/useRiskConfig";
import { cn } from "@/lib/cn";

interface RiskBadgeProps {
  score?: number | null;
  className?: string;
}

const EMOJI_BY_LABEL: Record<string, string> = {
  "Lav": "🟢",
  "Moderat": "🟡",
  "Høy": "🔴",
  "Svært høy": "🔴",
  "Ukjent": "⚪",
};

const CSS_BY_LABEL: Record<string, string> = {
  "Lav": "broker-badge-low",
  "Moderat": "broker-badge-mid",
  "Høy": "broker-badge-high",
  "Svært høy": "broker-badge-high",
  "Ukjent": "broker-badge-none",
};

export default function RiskBadge({ score, className }: RiskBadgeProps) {
  const { bandFor } = useRiskConfig();
  const band = bandFor(score);
  const emoji = EMOJI_BY_LABEL[band.label] ?? "";
  const cls = CSS_BY_LABEL[band.label] ?? "broker-badge-none";
  const text = score == null ? "–" : `${emoji} ${band.label}`.trim();
  return <span className={cn(cls, className)}>{text}</span>;
}
