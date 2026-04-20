"use client";

import Link from "next/link";
import { Loader2, Trash2 } from "lucide-react";
import { type PortfolioRiskRow } from "@/lib/api";
import { fmtMnok } from "@/lib/format";
import { useRiskConfig } from "@/lib/useRiskConfig";
import { useT } from "@/lib/i18n";

interface Props {
  portfolioRisk: PortfolioRiskRow[];
  portfolioName?: string;
  removingOrgnr: string | null;
  onRemove: (orgnr: string) => void;
}

export function PortfolioRiskTable({ portfolioRisk, portfolioName, removingOrgnr, onRemove }: Props) {
  const T = useT();
  const { bandFor } = useRiskConfig();

  return (
    <div>
      <p className="text-xs font-semibold text-foreground mb-2">
        {T("Selskaper i")} «{portfolioName}» ({portfolioRisk.length})
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted-foreground border-b border-border">
              <th className="text-left pb-1.5 font-medium">{T("Selskap")}</th>
              <th className="text-right pb-1.5 font-medium hidden sm:table-cell">{T("Omsetning")}</th>
              <th className="text-right pb-1.5 font-medium hidden md:table-cell">{T("Egenkapital")}</th>
              <th className="text-right pb-1.5 font-medium hidden md:table-cell">{T("EK-andel")}</th>
              <th className="text-right pb-1.5 font-medium">{T("Risiko")}</th>
              <th className="w-8 pb-1.5"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {portfolioRisk.map((r) => {
              const band = bandFor(r.risk_score);
              return (
                <tr key={r.orgnr} className="hover:bg-muted">
                  <td className="py-1.5">
                    <Link href={`/search/${r.orgnr}`} className="font-medium text-primary hover:underline">
                      {r.navn ?? r.orgnr}
                    </Link>
                  </td>
                  <td className="py-1.5 text-right text-muted-foreground hidden sm:table-cell">
                    {fmtMnok(r.revenue)}
                  </td>
                  <td className="py-1.5 text-right text-muted-foreground hidden md:table-cell">
                    {fmtMnok(r.equity)}
                  </td>
                  <td className="py-1.5 text-right text-muted-foreground hidden md:table-cell">
                    {r.equity_ratio != null ? `${(r.equity_ratio * 100).toFixed(1)}%` : "–"}
                  </td>
                  <td className="py-1.5 text-right">
                    {r.risk_score != null ? (
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                        style={{
                          background: band.color + "20",
                          color: band.color,
                        }}>{r.risk_score}</span>
                    ) : <span className="text-muted-foreground">–</span>}
                  </td>
                  <td className="py-1.5 text-right">
                    <button onClick={() => onRemove(r.orgnr)}
                      disabled={removingOrgnr === r.orgnr}
                      className="text-muted-foreground hover:text-red-500 disabled:opacity-50">
                      {removingOrgnr === r.orgnr
                        ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        : <Trash2 className="w-3.5 h-3.5" />}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
