"use client";

import { useState } from "react";
import { Mail, X } from "lucide-react";
import { composeEmail } from "@/lib/api";

/**
 * Plan §🟢 #10 — broker-composes-and-sends email modal.
 *
 * Posts to /email/compose which sends via MS Graph and auto-creates an
 * Activity row of type=email. Returns 503 if Graph isn't configured —
 * the modal surfaces that as a friendly setup message.
 */
export function ComposeEmailModal({
  orgnr,
  defaultTo,
  onClose,
  onSent,
}: {
  orgnr: string;
  defaultTo?: string;
  onClose: () => void;
  onSent?: () => void;
}) {
  const [to, setTo] = useState(defaultTo ?? "");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!to.trim() || !subject.trim()) return;
    setSending(true);
    setErr(null);
    try {
      // Plain text → minimal HTML wrapper. The backend stores this verbatim
      // in the activity preview; the actual outbound HTML is what we send
      // here. Keeping it simple — no rich-text editor in v1.
      const html = `<div style="font-family:Segoe UI,Helvetica,Arial,sans-serif;font-size:14px;color:#222;">${body
        .split("\n")
        .map((line) => (line.trim() ? `<p>${escapeHtml(line)}</p>` : "<br/>"))
        .join("")}</div>`;
      await composeEmail({ orgnr, to, subject, body_html: html });
      onSent?.();
      onClose();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSending(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-start sm:items-center justify-center p-4 overflow-y-auto"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-card rounded-lg shadow-xl w-full max-w-xl my-8"
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Mail className="w-4 h-4 text-primary" /> Send e-post
          </h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSend} className="p-5 space-y-3">
          <div>
            <label className="label-xs" htmlFor="email-to">Til *</label>
            <input
              id="email-to"
              type="email"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              required
              placeholder="kunde@example.no"
              className="input-sm w-full"
            />
          </div>
          <div>
            <label className="label-xs" htmlFor="email-subject">Emne *</label>
            <input
              id="email-subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              required
              className="input-sm w-full"
            />
          </div>
          <div>
            <label className="label-xs" htmlFor="email-body">Melding</label>
            <textarea
              id="email-body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={8}
              placeholder="Skriv meldingen din her…"
              className="w-full px-2 py-1.5 text-xs border border-border rounded-lg bg-card resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
          {err && <p className="text-xs text-red-600">{err}</p>}
          <p className="text-[10px] text-muted-foreground">
            Sendt e-post logges automatisk som aktivitet på selskapet.
          </p>
          <div className="flex flex-col sm:flex-row gap-2 pt-2">
            <button
              type="submit"
              disabled={sending || !to.trim() || !subject.trim()}
              className="w-full sm:w-auto px-4 py-2 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {sending ? "Sender…" : "Send e-post"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="w-full sm:w-auto px-3 py-2 text-xs rounded border border-border text-muted-foreground"
            >
              Avbryt
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
