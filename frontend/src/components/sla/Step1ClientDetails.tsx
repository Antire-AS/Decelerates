"use client";

import { Loader2 } from "lucide-react";
import { StepHeader, NavButtons } from "./SlaShared";
import type { SlaData } from "./slaConstants";
import { useT } from "@/lib/i18n";

interface Props {
  data: SlaData;
  set: (patch: Partial<SlaData>) => void;
  err: string | null;
  setErr: (e: string | null) => void;
  lookupLoading: boolean;
  onLookup: () => void;
  onNext: () => void;
}

export function Step1ClientDetails({ data, set, err, setErr, lookupLoading, onLookup, onNext }: Props) {
  const T = useT();
  function handleNext() {
    if (!data.client_navn?.trim()) { setErr(T("Klientnavn er påkrevd.")); return; }
    setErr(null);
    onNext();
  }

  return (
    <>
      <StepHeader step={1} total={5} label={T("Klientdetaljer")} />
      <div className="space-y-3">
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="label-xs" htmlFor="sla-client-orgnr">{T("Org.nr")} *</label>
            <input id="sla-client-orgnr" value={data.client_orgnr ?? ""} onChange={(e) => set({ client_orgnr: e.target.value })}
              placeholder={T("9 siffer")} className="input-sm w-full" />
          </div>
          <button onClick={onLookup} disabled={lookupLoading}
            className="self-end px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1">
            {lookupLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
            {T("Slå opp")}
          </button>
        </div>
        <div>
          <label className="label-xs" htmlFor="sla-client-navn">{T("Klientnavn")} *</label>
          <input id="sla-client-navn" value={data.client_navn ?? ""} onChange={(e) => set({ client_navn: e.target.value })}
            className="input-sm w-full" />
        </div>
        <div>
          <label className="label-xs" htmlFor="sla-client-adresse">{T("Adresse")}</label>
          <textarea id="sla-client-adresse" value={data.client_adresse ?? ""} onChange={(e) => set({ client_adresse: e.target.value })}
            rows={2} className="w-full px-2 py-1.5 text-xs border border-border rounded-lg bg-card resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring" />
        </div>
        <div>
          <label className="label-xs" htmlFor="sla-client-kontakt">{T("Kontaktperson (navn + e-post)")}</label>
          <input id="sla-client-kontakt" value={data.client_kontakt ?? ""} onChange={(e) => set({ client_kontakt: e.target.value })}
            className="input-sm w-full" />
        </div>
      </div>
      {err && <p className="text-xs text-red-600 mt-2">{err}</p>}
      <NavButtons onNext={handleNext} />
    </>
  );
}
