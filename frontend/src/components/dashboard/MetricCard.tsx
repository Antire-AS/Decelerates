import { cn } from "@/lib/cn";

interface MetricCardProps {
  label: string;
  value: string | number;
  help?: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export default function MetricCard({
  label,
  value,
  help,
  className,
}: MetricCardProps) {
  return (
    <div className={cn("broker-card flex flex-col gap-1", className)} title={help}>
      <p className="text-xs text-[#8A7F74] font-medium">{label}</p>
      <p className="text-2xl font-bold text-[#2C3E50]">{value}</p>
      {help && <p className="text-xs text-[#8A7F74]">{help}</p>}
    </div>
  );
}
