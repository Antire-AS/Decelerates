// Shared formatters, color palette, and small UI primitives used across all
// analytics tabs. Kept private to /portfolio/analytics — not exported globally.

export const COLORS = ["#4A6FA5", "#2C3E50", "#C8A951", "#7B9E87", "#9B6B6B", "#6B8FAB", "#B8860B"];

export function fmt(n: number | undefined | null) {
  if (n == null) return "–";
  return new Intl.NumberFormat("nb-NO").format(Math.round(n));
}

export function fmtMnok(n: number | undefined | null) {
  if (n == null) return "–";
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(1)} mrd`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(0)} MNOK`;
  return `${(n / 1e3).toFixed(0)} TNOK`;
}

export function MetricCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="broker-card">
      <p className="text-xs text-[#8A7F74] font-medium mb-1">{label}</p>
      <p className="text-2xl font-bold text-[#2C3E50]">{value}</p>
      {sub && <p className="text-xs text-[#8A7F74] mt-1">{sub}</p>}
    </div>
  );
}
