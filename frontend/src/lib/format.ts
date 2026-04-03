/** Shared number / date formatters for Norwegian locale. */

export function fmt(v: unknown): string {
  if (v == null) return "–";
  if (typeof v === "number") return new Intl.NumberFormat("nb-NO").format(v);
  return String(v);
}

export function fmtMnok(v: unknown): string {
  if (v == null || v === "") return "–";
  const n = Number(v);
  if (isNaN(n)) return "–";
  return `${(n / 1_000_000).toLocaleString("nb-NO", { maximumFractionDigits: 1 })} MNOK`;
}

export function fmtNok(n?: number | null): string {
  if (n == null) return "–";
  return `kr ${new Intl.NumberFormat("nb-NO").format(n)}`;
}

export function fmtDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("nb-NO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}
