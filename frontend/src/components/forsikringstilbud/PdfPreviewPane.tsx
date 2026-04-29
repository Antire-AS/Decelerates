"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, FileText } from "lucide-react";
import { useT } from "@/lib/i18n";

interface Props {
  /** POSTs JSON to `/bapi{endpoint}?save=false` and renders the response as PDF.
   * Re-renders the PDF whenever `payload` changes (debounced 600ms). */
  endpoint: string;
  payload: Record<string, unknown> | null;
  authToken?: string;
}

export default function PdfPreviewPane({ endpoint, payload, authToken }: Props) {
  const T = useT();
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastUrlRef = useRef<string | null>(null);

  useEffect(() => {
    if (!payload) return;
    const t = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/bapi${endpoint}?save=false`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
          },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current);
        lastUrlRef.current = url;
        setPdfUrl(url);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    }, 600);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(payload), endpoint, authToken]);

  useEffect(() => {
    return () => {
      if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current);
    };
  }, []);

  return (
    <div className="broker-card flex flex-col h-[700px]">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-muted-foreground inline-flex items-center gap-1">
          <FileText className="w-3 h-3" />
          {T("Forhåndsvisning")} · forsikringstilbud.pdf
        </p>
        {loading && (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Loader2 className="w-3 h-3 animate-spin" />
            {T("Renderer…")}
          </span>
        )}
      </div>
      {error && <p className="text-xs text-red-600 mb-2">{error}</p>}
      {pdfUrl && (
        <iframe
          src={pdfUrl}
          title="Forsikringstilbud preview"
          className="flex-1 w-full rounded border border-border bg-white"
        />
      )}
      {!pdfUrl && !loading && (
        <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground italic">
          {T("Fyll inn skjemaet for å se forhåndsvisning")}
        </div>
      )}
    </div>
  );
}
