"use client";

import { useState } from "react";
import { CheckCircle2, Download, Loader2, Mail, X } from "lucide-react";
import { useT } from "@/lib/i18n";

interface Props {
  orgnr: string;
}

/**
 * Two-track UX for the broker:
 *
 *   1. "Generer anbudspakke" — downloads the PDF locally so the broker
 *      can attach it to an email they're already drafting elsewhere
 *      (same as v3 I4, unchanged).
 *   2. "Send på epost" — opens a small dialog that emails the PDF as
 *      an attachment via ACS without the broker leaving the app. New
 *      in v4 PR3.
 *
 * Both call the same underlying endpoint that generates the PDF freshly
 * per request, so Altman / news / peer numbers are always current.
 */
export default function AnbudPackageButton({ orgnr }: Props) {
  const T = useT();
  const [downloading, setDownloading] = useState(false);
  const [downloadErr, setDownloadErr] = useState<string | null>(null);
  const [showEmailDialog, setShowEmailDialog] = useState(false);

  async function handleDownload(): Promise<void> {
    setDownloading(true);
    setDownloadErr(null);
    try {
      const res = await fetch(`/bapi/org/${orgnr}/anbudspakke.pdf`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
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
      setDownloadErr(e instanceof Error ? e.message : String(e));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="inline-flex flex-col items-end gap-0.5">
      <div className="inline-flex items-center gap-2">
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border border-primary text-primary hover:bg-primary/10 disabled:opacity-50"
          title={T(
            "Last ned samlet PDF — selskapsinfo, økonomi, risikoprofil, behov, notater, nyheter og poliser.",
          )}
        >
          {downloading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Download className="w-4 h-4" />
          )}
          {T("Generer anbudspakke")}
        </button>
        <button
          onClick={() => setShowEmailDialog(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border border-primary bg-primary text-primary-foreground hover:bg-primary/90"
          title={T("Send anbudspakken som epostvedlegg til et forsikringsselskap.")}
        >
          <Mail className="w-4 h-4" />
          {T("Send på epost")}
        </button>
      </div>
      {downloadErr && <span className="text-[11px] text-red-600">{downloadErr}</span>}
      {showEmailDialog && (
        <AnbudEmailDialog orgnr={orgnr} onClose={() => setShowEmailDialog(false)} />
      )}
    </div>
  );
}


interface DialogProps {
  orgnr: string;
  onClose: () => void;
}

/**
 * Simple controlled dialog — no shadcn/Dialog dep, native backdrop +
 * rounded panel. Broker fills in recipient, optional message, clicks
 * Send. We POST /org/{orgnr}/anbudspakke/email and surface ACS status.
 */
function AnbudEmailDialog({ orgnr, onClose }: DialogProps) {
  const T = useT();
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function handleSend(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setSending(true);
    setErr(null);
    try {
      const res = await fetch(`/bapi/org/${orgnr}/anbudspakke/email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          to: to.trim(),
          subject: subject.trim() || undefined,
          message: message.trim() || undefined,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `${res.status} ${res.statusText}`);
      }
      setSent(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-background w-full max-w-md rounded-lg shadow-xl p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 className="text-base font-semibold">{T("Send anbudspakke")}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {T("Pakken genereres på nytt og sendes som PDF-vedlegg via vår demomailboks.")}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground -mt-1 -mr-1"
            aria-label={T("Lukk")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {sent ? (
          <div className="py-4 text-center">
            <CheckCircle2 className="w-10 h-10 text-green-600 mx-auto mb-2" />
            <p className="text-sm font-medium text-foreground">
              {T("Anbudspakken er sendt.")}
            </p>
            <p className="text-xs text-muted-foreground mt-1">{to}</p>
            <button
              onClick={onClose}
              className="mt-4 px-4 py-1.5 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {T("Lukk")}
            </button>
          </div>
        ) : (
          <form onSubmit={handleSend} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">
                {T("Til (forsikringsselskap)")} <span className="text-red-500">*</span>
              </label>
              <input
                type="email"
                required
                value={to}
                onChange={(e) => setTo(e.target.value)}
                placeholder="anbud@gjensidige.no"
                className="w-full px-3 py-1.5 text-sm rounded border border-muted-foreground/30 bg-background focus:border-primary outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">
                {T("Emne (valgfritt)")}
              </label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder={T("Forespørsel om forsikringstilbud — ...")}
                className="w-full px-3 py-1.5 text-sm rounded border border-muted-foreground/30 bg-background focus:border-primary outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">
                {T("Melding (valgfritt, vises over standardinnledningen)")}
              </label>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={4}
                placeholder={T("Hei — her er risikounderlag for NN. Gi oss gjerne et indikativt tilbud innen ...")}
                className="w-full px-3 py-1.5 text-sm rounded border border-muted-foreground/30 bg-background focus:border-primary outline-none resize-y"
              />
            </div>
            {err && <p className="text-xs text-red-600">{err}</p>}
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-muted">
              <button
                type="button"
                onClick={onClose}
                disabled={sending}
                className="px-3 py-1.5 text-sm rounded-lg text-muted-foreground hover:bg-muted disabled:opacity-50"
              >
                {T("Avbryt")}
              </button>
              <button
                type="submit"
                disabled={sending || !to.trim()}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {sending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Mail className="w-4 h-4" />
                )}
                {T("Send")}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
