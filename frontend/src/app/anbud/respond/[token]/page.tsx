"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  FileText,
  Upload,
  CheckCircle2,
  Clock,
  Building,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { useT } from "@/lib/i18n";

type PortalView = {
  insurer_name: string;
  status: string;
  tender: {
    title: string;
    orgnr: string;
    company_name: string;
    product_types: string[];
    deadline: string | null;
    notes: string | null;
  };
};

/**
 * Insurer portal — NO AUTH. A broker invites insurers to a tender and gets
 * a unique URL per recipient. The insurer opens the URL, sees what the
 * broker is asking for, and uploads their quote PDF.
 *
 * Route: /anbud/respond/[token]
 * Backend: GET /bapi/tenders/portal/{token}  +  POST .../upload
 */
export default function AnbudPortalPage() {
  const T = useT();
  const params = useParams();
  const token = Array.isArray(params.token) ? params.token[0] : (params.token as string);

  const [view, setView] = useState<PortalView | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await fetch(`/bapi/tenders/portal/${encodeURIComponent(token)}`);
      if (res.status === 404) {
        setErr(T("Ugyldig eller utløpt lenke. Kontakt megleren som sendte den."));
        return;
      }
      if (!res.ok) {
        setErr(`${T("Kunne ikke laste anbudsdetaljer")}: HTTP ${res.status}`);
        return;
      }
      setView(await res.json());
    } catch {
      setErr(T("Nettverksfeil. Prøv igjen om et øyeblikk."));
    } finally {
      setLoading(false);
    }
  }, [token, T]);

  useEffect(() => {
    if (token) void load();
  }, [token, load]);

  async function handleUpload() {
    if (!file || uploading) return;
    setUploading(true);
    setErr(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/bapi/tenders/portal/${encodeURIComponent(token)}/upload`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        setErr(detail.detail ?? `${T("Opplasting feilet")}: HTTP ${res.status}`);
        return;
      }
      setUploaded(true);
      await load();
    } catch {
      setErr(T("Nettverksfeil ved opplasting."));
    } finally {
      setUploading(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <div className="broker-card flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" /> {T("Laster anbud…")}
        </div>
      </div>
    );
  }

  if (err && !view) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <div className="broker-card border-l-4 border-red-500 flex gap-2">
          <AlertTriangle className="w-5 h-5 text-red-500 shrink-0" />
          <p className="text-sm text-foreground">{err}</p>
        </div>
      </div>
    );
  }

  if (!view) return null;

  const alreadyReceived = view.status === "received";
  const deadlinePast =
    view.tender.deadline !== null && new Date(view.tender.deadline) < new Date();

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">
            {T("Anbudsforespørsel")}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {T("Til")}: <strong>{view.insurer_name}</strong>
          </p>
        </div>
        <span className="text-xs px-2 py-1 rounded bg-accent text-accent-foreground font-medium shrink-0">
          meglerai.no
        </span>
      </header>

      <section className="broker-card space-y-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Building className="w-4 h-4 text-primary" /> {view.tender.company_name}
        </div>
        <div className="text-xs text-muted-foreground">
          {T("Org.nr")}: {view.tender.orgnr}
        </div>
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">{T("Produkter")}</p>
          <div className="flex flex-wrap gap-1.5">
            {view.tender.product_types.map((p) => (
              <span
                key={p}
                className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground"
              >
                {p}
              </span>
            ))}
          </div>
        </div>
        {view.tender.deadline && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="w-3.5 h-3.5" />
            {T("Frist")}: {new Date(view.tender.deadline).toLocaleDateString("nb-NO")}
            {deadlinePast && (
              <span className="text-red-600 ml-1">({T("utløpt")})</span>
            )}
          </div>
        )}
        {view.tender.notes && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">{T("Merknader")}</p>
            <p className="text-sm text-foreground whitespace-pre-wrap">
              {view.tender.notes}
            </p>
          </div>
        )}
      </section>

      {/* Upload */}
      {alreadyReceived || uploaded ? (
        <section className="broker-card border-l-4 border-green-600 flex items-start gap-2">
          <CheckCircle2 className="w-5 h-5 text-green-600 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-foreground">
              {T("Takk! Tilbudet er mottatt.")}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {T(
                "Megleren blir varslet. Du kan laste opp på nytt hvis du har en oppdatert versjon.",
              )}
            </p>
          </div>
        </section>
      ) : null}

      <section className="broker-card space-y-3">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Upload className="w-4 h-4" /> {T("Last opp tilbudet")}
        </h2>
        {deadlinePast && !alreadyReceived && (
          <p className="text-xs text-red-600">
            {T("Fristen er utløpt, men du kan fortsatt laste opp — megleren vurderer case-by-case.")}
          </p>
        )}
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm text-foreground block w-full"
        />
        {file && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <FileText className="w-3 h-3" />
            {file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB
          </div>
        )}
        <button
          type="button"
          onClick={handleUpload}
          disabled={!file || uploading}
          className="px-4 py-2 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1"
        >
          {uploading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Upload className="w-4 h-4" />
          )}
          {T("Send tilbud")}
        </button>
        {err && (
          <p className="text-xs text-red-600 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            {err}
          </p>
        )}
      </section>

      <footer className="text-center text-xs text-muted-foreground">
        {T("Denne lenken er personlig for")} {view.insurer_name}.{" "}
        {T("Ikke videresend.")}
      </footer>
    </div>
  );
}
