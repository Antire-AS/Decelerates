import { cn } from "@/lib/cn";

interface RiskBadgeProps {
  score?: number | null;
  className?: string;
}

function riskLabel(score?: number | null): { text: string; cls: string } {
  if (score == null) return { text: "–",          cls: "broker-badge-none" };
  if (score <= 3)    return { text: "🟢 Lav",     cls: "broker-badge-low" };
  if (score <= 7)    return { text: "🟡 Moderat", cls: "broker-badge-mid" };
  return               { text: "🔴 Høy",     cls: "broker-badge-high" };
}

export default function RiskBadge({ score, className }: RiskBadgeProps) {
  const { text, cls } = riskLabel(score);
  return <span className={cn(cls, className)}>{text}</span>;
}
