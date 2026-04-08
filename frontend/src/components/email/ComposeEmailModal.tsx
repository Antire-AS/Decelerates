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
        className="bg-white rounded-lg shadow-xl w-full max-w-xl my-8"
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-[#EDE8E3]">
          <h2 className="text-base font-semibold text-[#2C3E50] flex items-center gap-2">
            <Mail className="w-4 h-4 text-[#4A6FA5]" /> Send e-post
          </h2>
          <button onClick={onClose} className="text-[#8A7F74] hover:text-[#2C3E50]">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSend} className="p-5 space-y-3">
          <div>
            <label className="label-xs">Til *</label>
            <input
              type="email"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              required
              placeholder="kunde@example.no"
              className="input-sm w-full"
            />
          </div>
          <div>
            <label className="label-xs">Emne *</label>
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              required
              className="input-sm w-full"
            />
          </div>
          <div>
            <label className="label-xs">Melding</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={8}
              placeholder="Skriv meldingen din her…"
              className="w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded-lg bg-white resize-none focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]"
            />
          </div>
          {err && <p className="text-xs text-red-600">{err}</p>}
          <p className="text-[10px] text-[#8A7F74]">
            Sendt e-post logges automatisk som aktivitet på selskapet.
          </p>
          <div className="flex flex-col sm:flex-row gap-2 pt-2">
            <button
              type="submit"
              disabled={sending || !to.trim() || !subject.trim()}
              className="w-full sm:w-auto px-4 py-2 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50"
            >
              {sending ? "Sender…" : "Send e-post"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="w-full sm:w-auto px-3 py-2 text-xs rounded border border-[#D4C9B8] text-[#8A7F74]"
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
