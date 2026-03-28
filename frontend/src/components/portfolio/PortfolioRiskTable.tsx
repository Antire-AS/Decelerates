"use client";

import Link from "next/link";
import { Loader2, Trash2 } from "lucide-react";
import { type PortfolioRiskRow } from "@/lib/api";

const RISK_BANDS = [
  { label: "Lav (0–39)",      min: 0,  max: 39,  color: "#27AE60" },
  { label: "Moderat (40–69)", min: 40, max: 69,  color: "#C8A951" },
  { label: "Høy (70–100)",    min: 70, max: 100, color: "#C0392B" },
  { label: "Ukjent",          min: -1, max: -1,  color: "#C4BDB4" },
];

function band(score?: number) {
  if (score == null) return 3;
  if (score < 40) return 0;
  if (score < 70) return 1;
  return 2;
}

function fmtMnok(v?: number) {
  if (!v) return "–";
  return `${(v / 1e6).toLocaleString("nb-NO", { maximumFractionDigits: 1 })} MNOK`;
}

interface Props {
  portfolioRisk: PortfolioRiskRow[];
  portfolioName?: string;
  removingOrgnr: string | null;
  onRemove: (orgnr: string) => void;
}

export function PortfolioRiskTable({ portfolioRisk, portfolioName, removingOrgnr, onRemove }: Props) {
  return (
    <div>
      <p className="text-xs font-semibold text-[#2C3E50] mb-2">
        Selskaper i «{portfolioName}» ({portfolioRisk.length})
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-[#8A7F74] border-b border-[#EDE8E3]">
              <th className="text-left pb-1.5 font-medium">Selskap</th>
              <th className="text-right pb-1.5 font-medium hidden sm:table-cell">Omsetning</th>
              <th className="text-right pb-1.5 font-medium hidden md:table-cell">Egenkapital</th>
              <th className="text-right pb-1.5 font-medium hidden md:table-cell">EK-andel</th>
              <th className="text-right pb-1.5 font-medium">Risiko</th>
              <th className="w-8 pb-1.5"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#EDE8E3]">
            {portfolioRisk.map((r) => (
              <tr key={r.orgnr} className="hover:bg-[#F9F7F4]">
                <td className="py-1.5">
                  <Link href={`/search/${r.orgnr}`} className="font-medium text-[#4A6FA5] hover:underline">
                    {r.navn ?? r.orgnr}
                  </Link>
                </td>
                <td className="py-1.5 text-right text-[#8A7F74] hidden sm:table-cell">
                  {fmtMnok(r.revenue)}
                </td>
                <td className="py-1.5 text-right text-[#8A7F74] hidden md:table-cell">
                  {fmtMnok(r.equity)}
                </td>
                <td className="py-1.5 text-right text-[#8A7F74] hidden md:table-cell">
                  {r.equity_ratio != null ? `${(r.equity_ratio * 100).toFixed(1)}%` : "–"}
                </td>
                <td className="py-1.5 text-right">
                  {r.risk_score != null ? (
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                      style={{
                        background: RISK_BANDS[band(r.risk_score)].color + "20",
                        color: RISK_BANDS[band(r.risk_score)].color,
                      }}>{r.risk_score}</span>
                  ) : <span className="text-[#8A7F74]">–</span>}
                </td>
                <td className="py-1.5 text-right">
                  <button onClick={() => onRemove(r.orgnr)}
                    disabled={removingOrgnr === r.orgnr}
                    className="text-[#C4BDB4] hover:text-red-500 disabled:opacity-50">
                    {removingOrgnr === r.orgnr
                      ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      : <Trash2 className="w-3.5 h-3.5" />}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
