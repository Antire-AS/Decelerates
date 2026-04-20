"use client";

import { Loader2, Link2 } from "lucide-react";
import { useT } from "@/lib/i18n";

interface Props {
  pdfUrl: string;
  setPdfUrl: (v: string) => void;
  pdfYear: number;
  setPdfYear: (v: number) => void;
  pdfLabel: string;
  setPdfLabel: (v: string) => void;
  pdfLoading: boolean;
  pdfErr: string | null;
  pdfOk: boolean;
  handleAddPdf: () => void;
  setPdfOk: (v: boolean) => void;
  missingYearsCount: number;
  pendingYearsCount: number;
}

export default function AddPdfForm({
  pdfUrl, setPdfUrl, pdfYear, setPdfYear,
  pdfLabel, setPdfLabel, pdfLoading, pdfErr, pdfOk,
  handleAddPdf, setPdfOk,
  missingYearsCount, pendingYearsCount,
}: Props) {
  const T = useT();
  return (
    <details
      className="broker-card group"
      open={!!(missingYearsCount && !pendingYearsCount)}
    >
      <summary className="cursor-pointer flex items-center gap-1.5 text-sm font-semibold text-foreground select-none list-none">
        <Link2 className="w-4 h-4 text-primary" />
        {T("Legg til årsrapport-PDF")}
        <span className="ml-auto text-xs text-muted-foreground font-normal group-open:hidden">
          {T("klikk for å åpne")}
        </span>
      </summary>
      <div className="mt-3 space-y-2">
        <p className="text-xs text-muted-foreground">
          {T("Lim inn URL til PDF-årsrapport — AI henter ut regnskapstall automatisk")}
        </p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto_auto]">
          <input
            type="url"
            value={pdfUrl}
            onChange={(e) => { setPdfUrl(e.target.value); setPdfOk(false); }}
            placeholder="https://example.com/arsrapport-2023.pdf"
            className="text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground placeholder:text-muted-foreground"
          />
          <input
            type="number"
            value={pdfYear}
            onChange={(e) => setPdfYear(Number(e.target.value))}
            min={2000}
            max={new Date().getFullYear()}
            className="text-sm border border-border rounded-lg px-3 py-1.5 w-24 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground"
          />
          <button
            onClick={handleAddPdf}
            disabled={pdfLoading || !pdfUrl.trim()}
            className="px-3 py-1.5 text-xs rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1.5 whitespace-nowrap"
          >
            {pdfLoading && <Loader2 className="w-3 h-3 animate-spin" />}
            {pdfLoading ? T("Henter…") : T("Hent tall")}
          </button>
        </div>
        <input
          type="text"
          value={pdfLabel}
          onChange={(e) => setPdfLabel(e.target.value)}
          placeholder={T("Etikett (valgfri, f.eks. «Konsern»)")}
          className="w-full text-sm border border-border rounded-lg px-3 py-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground placeholder:text-muted-foreground"
        />
        {pdfErr && <p className="text-xs text-red-600">{pdfErr}</p>}
        {pdfOk && <p className="text-xs text-green-700">{T("Regnskapstall hentet og lagret.")}</p>}
      </div>
    </details>
  );
}
