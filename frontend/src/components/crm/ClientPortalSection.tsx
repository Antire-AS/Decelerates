"use client";

import { useState } from "react";
import useSWR from "swr";
import { Link2, Plus, Copy, CheckCircle, Loader2, ExternalLink } from "lucide-react";
import {
  getOrgClientTokens,
  createOrgClientToken,
  type ClientToken,
} from "@/lib/api";

export default function ClientPortalSection({ orgnr }: { orgnr: string }) {
  const { data: tokens, isLoading, mutate } = useSWR<ClientToken[]>(
    `client-tokens-${orgnr}`,
    () => getOrgClientTokens(orgnr),
  );

  const [label, setLabel] = useState("");
  const [creating, setCreating] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const origin = typeof window !== "undefined" ? window.location.origin : "";

  async function handleCreate() {
    setCreating(true); setErr(null);
    try {
      await createOrgClientToken(orgnr, label || undefined);
      setLabel("");
      mutate();
    } catch (e) {
      setErr(String(e));
    } finally {
      setCreating(false);
    }
  }

  function copyLink(token: string) {
    const url = `${origin}/portal/${token}`;
    navigator.clipboard.writeText(url);
    setCopied(token);
    setTimeout(() => setCopied(null), 2000);
  }

  const active = (tokens ?? []).filter(
    (t) => new Date(t.expires_at) > new Date(),
  );

  return (
    <div className="broker-card space-y-4">
      <div className="flex items-center gap-2">
        <Link2 className="w-4 h-4 text-[#4A6FA5]" />
        <h3 className="text-sm font-semibold text-[#2C3E50]">Del med klient</h3>
      </div>

      <p className="text-xs text-[#8A7F74]">
        Generer en 30-dagers lenke klienten kan bruke til å se sine forsikringer, skader og dokumenter — uten innlogging.
      </p>

      {/* Create form */}
      <div className="flex gap-2">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Etikett (valgfri, f.eks. «Sendt til kontakt»)"
          className="flex-1 text-sm border border-[#D4C9B8] rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#4A6FA5] text-[#2C3E50] placeholder:text-[#C4BDB4]"
        />
        <button
          onClick={handleCreate}
          disabled={creating}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2C3E50] text-white text-sm rounded-lg hover:bg-[#1a252f] disabled:opacity-50"
        >
          {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          Generer
        </button>
      </div>

      {err && <p className="text-xs text-red-500">{err}</p>}

      {/* Active tokens */}
      {isLoading ? (
        <div className="flex justify-center py-3">
          <Loader2 className="w-4 h-4 animate-spin text-[#4A6FA5]" />
        </div>
      ) : active.length > 0 ? (
        <div className="space-y-2">
          {active.map((t) => {
            const url = `${origin}/portal/${t.token}`;
            const expires = new Date(t.expires_at).toLocaleDateString("nb-NO");
            return (
              <div key={t.token}
                className="flex items-center justify-between gap-2 bg-[#F9F7F4] border border-[#EDE8E3] rounded-lg px-3 py-2">
                <div className="min-w-0">
                  {t.label && (
                    <p className="text-xs font-medium text-[#2C3E50] truncate">{t.label}</p>
                  )}
                  <p className="text-xs text-[#8A7F74] truncate">{url}</p>
                  <p className="text-xs text-[#8A7F74]">Utløper {expires}</p>
                </div>
                <div className="flex gap-1.5 flex-shrink-0">
                  <button
                    onClick={() => copyLink(t.token)}
                    title="Kopier lenke"
                    className="p-1.5 rounded-lg hover:bg-[#EDE8E3] text-[#4A6FA5]"
                  >
                    {copied === t.token
                      ? <CheckCircle className="w-4 h-4 text-green-600" />
                      : <Copy className="w-4 h-4" />}
                  </button>
                  <a href={url} target="_blank" rel="noopener noreferrer"
                    title="Åpne portal"
                    className="p-1.5 rounded-lg hover:bg-[#EDE8E3] text-[#4A6FA5]">
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-xs text-[#8A7F74]">Ingen aktive lenker.</p>
      )}
    </div>
  );
}
