"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { useT } from "@/lib/i18n";

interface Props {
  orgnr: string;
}

/**
 * One-click download of the anbudspakke PDF — the "package" the broker
 * emails to Gjensidige/Tryg/If when soliciting offers. We hit the PDF
 * endpoint directly and trigger a browser download rather than opening
 * in a tab because brokers overwhelmingly want the file attached to an
 * email they're already drafting.
 */
export default function AnbudPackageButton({ orgnr }: Props) {
  const T = useT();
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleClick(): Promise<void> {
    setLoading(true);
    setErr(null);
    try {
      const res = await fetch(`/bapi/org/${orgnr}/anbudspakke.pdf`);
      if (!res.ok) {
        throw new Error(`${res.status} ${res.statusText}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `anbudspakke-${orgnr}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="inline-flex flex-col items-end gap-0.5">
      <button
        onClick={handleClick}
        disabled={loading}
        className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border border-primary text-primary hover:bg-primary/10 disabled:opacity-50"
        title={T(
          "Last ned et samlet PDF-dokument med selskapsinfo, okonomi, risikoprofil, behov, notater, materielle nyheter og aktive poliser. Send dette til forsikringsselskaper for a be om tilbud.",
        )}
      >
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Download className="w-4 h-4" />
        )}
        {T("Generer anbudspakke")}
      </button>
      {err && <span className="text-[11px] text-red-600">{err}</span>}
    </div>
  );
}
