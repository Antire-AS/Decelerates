"use client";

import { Info } from "lucide-react";

interface ExtractionStatus {
  status?: string;
  pending_years: number[];
  missing_target_years: number[];
}

interface Props {
  extractionStatus: ExtractionStatus | undefined;
  foreignCurrencies: string[];
  fxRates: Record<string, number>;
  hasEstimated: boolean;
  hasHistory: boolean;
}

export default function FinancialsBanners({
  extractionStatus,
  foreignCurrencies,
  fxRates,
  hasEstimated,
  hasHistory,
}: Props) {
  return (
    <>
      {extractionStatus && extractionStatus.pending_years.length > 0 && (
        <div className="broker-card border-l-4 border-amber-400 flex items-start gap-2">
          <Info className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-[#2C3E50]">
            <span className="font-medium">PDF-utdrag pågår</span> — venter på år:{" "}
            {extractionStatus.pending_years.join(", ")}. Siden oppdateres automatisk.
          </div>
        </div>
      )}
      {extractionStatus?.status === "no_sources" && !hasHistory && (
        <div className="broker-card border-l-4 border-[#D4C9B8] flex items-start gap-2">
          <Info className="w-4 h-4 text-[#C4BDB4] flex-shrink-0 mt-0.5" />
          <p className="text-xs text-[#8A7F74]">
            Ingen PDF-kilder funnet ennå. Lim inn en årsrapport-URL nedenfor for å hente tall.
          </p>
        </div>
      )}
      {extractionStatus &&
        extractionStatus.missing_target_years.length > 0 &&
        extractionStatus.pending_years.length === 0 && (
          <div className="broker-card border-l-4 border-[#D4C9B8] flex items-start gap-2">
            <Info className="w-4 h-4 text-[#C4BDB4] flex-shrink-0 mt-0.5" />
            <p className="text-xs text-[#8A7F74]">
              Mangler årsrapporter for{" "}
              {extractionStatus.missing_target_years.join(", ")}.
              Lim inn PDF-lenker nedenfor for å hente tall.
            </p>
          </div>
        )}
      {foreignCurrencies.length > 0 && (
        <div className="broker-card border-l-4 border-[#4A6FA5] flex items-start gap-2">
          <Info className="w-4 h-4 text-[#4A6FA5] flex-shrink-0 mt-0.5" />
          <p className="text-xs text-[#2C3E50]">
            <span className="font-medium">Fremmed valuta</span> — tall i{" "}
            {foreignCurrencies.join(", ")}.
            {Object.entries(fxRates).map(([ccy, rate]) => (
              <span key={ccy}>
                {" "}
                Dagskurs: 1 {ccy} = {rate.toFixed(4)} NOK.
              </span>
            ))}
          </p>
        </div>
      )}
      {hasEstimated && (
        <div className="broker-card border-l-4 border-[#C8A951] flex items-start gap-2">
          <Info className="w-4 h-4 text-[#C8A951] flex-shrink-0 mt-0.5" />
          <p className="text-xs text-[#8A7F74]">
            Noen tall er hentet fra PDF-årsrapporter og kan avvike fra
            offisielle BRREG-tall.
          </p>
        </div>
      )}
    </>
  );
}
