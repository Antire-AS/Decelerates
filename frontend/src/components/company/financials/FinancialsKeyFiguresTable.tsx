"use client";

import type { HistoryRow } from "@/lib/api";
import { fmtMnok } from "@/lib/format";
import { useT } from "@/lib/i18n";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="broker-card space-y-3">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {children}
    </div>
  );
}

type MetricDef = {
  label: string;
  get: (r: HistoryRow) => number | undefined | null;
  fmt: (v: number) => string;
  better: "up" | "down" | null;
};

const METRICS: MetricDef[] = [
  {
    label: "Omsetning",
    get: r => (r.revenue ?? r.sumDriftsinntekter) as number | undefined,
    fmt: fmtMnok, better: "up",
  },
  {
    label: "Nettoresultat",
    get: r => r.arsresultat as number | undefined,
    fmt: fmtMnok, better: "up",
  },
  {
    label: "Margin (%)",
    get: r => {
      const rev = (r.revenue ?? r.sumDriftsinntekter) as number | undefined;
      const net = r.arsresultat as number | undefined;
      return rev && net ? +((net / rev) * 100).toFixed(1) : undefined;
    },
    fmt: v => `${v.toFixed(1)}%`, better: "up",
  },
  {
    label: "Sum eiendeler",
    get: r => (r.sumEiendeler ?? r.total_assets) as number | undefined,
    fmt: fmtMnok, better: null,
  },
  {
    label: "Egenkapital",
    get: r => (r.sumEgenkapital ?? r.equity) as number | undefined,
    fmt: fmtMnok, better: "up",
  },
  {
    label: "EK-andel (%)",
    get: r => r.equity_ratio != null ? +(r.equity_ratio * 100).toFixed(1) : undefined,
    fmt: v => `${v.toFixed(1)}%`, better: "up",
  },
  {
    label: "Ansatte",
    get: r => r.antallAnsatte as number | undefined,
    fmt: v => String(Math.round(v)), better: null,
  },
];

interface Props {
  history: HistoryRow[];
}

export default function FinancialsKeyFiguresTable({ history }: Props) {
  const T = useT();
  const sorted = [...history].sort((a, b) => a.year - b.year);
  const active = METRICS.filter(m => sorted.some(r => m.get(r) != null));

  if (active.length === 0 || sorted.length < 2) return null;

  return (
    <Section title={T("Nøkkeltall per år")}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted-foreground border-b border-border">
              <th className="text-left pb-2 font-medium w-28">{T("Nøkkeltall")}</th>
              {sorted.map(r => (
                <th key={r.year} className="text-right pb-2 font-medium min-w-[80px]">
                  {r.year}
                  {r.source === "pdf" && (
                    <span className="text-brand-warning font-normal ml-1 text-[10px]">PDF</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {active.map(m => (
              <tr key={m.label} className="border-b border-border last:border-0 hover:bg-muted">
                <td className="py-2 text-muted-foreground font-medium">{T(m.label)}</td>
                {sorted.map((r, i) => {
                  const val = m.get(r);
                  const prev = i > 0 ? m.get(sorted[i - 1]) : null;
                  let arrow = "";
                  let arrowCls = "text-muted-foreground";
                  if (val != null && prev != null) {
                    if (val > prev) {
                      arrow = "↑";
                      arrowCls = m.better === "up" ? "text-green-600" : m.better === "down" ? "text-red-600" : "text-muted-foreground";
                    } else if (val < prev) {
                      arrow = "↓";
                      arrowCls = m.better === "up" ? "text-red-600" : m.better === "down" ? "text-green-600" : "text-muted-foreground";
                    }
                  }
                  return (
                    <td key={r.year} className="py-2 text-right">
                      {val != null ? (
                        <span className={`font-medium ${m.label === "Nettoresultat" && (val as number) < 0 ? "text-red-600" : "text-foreground"}`}>
                          {m.fmt(val as number)}
                          {arrow && <span className={`ml-1 text-[10px] ${arrowCls}`}>{arrow}</span>}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">–</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}
