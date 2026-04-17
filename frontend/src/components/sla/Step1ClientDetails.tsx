"use client";

import { Loader2 } from "lucide-react";
import { StepHeader, NavButtons } from "./SlaShared";
import type { SlaData } from "./slaConstants";

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
  function handleNext() {
    if (!data.client_navn?.trim()) { setErr("Klientnavn er påkrevd."); return; }
    setErr(null);
    onNext();
  }

  return (
    <>
      <StepHeader step={1} total={5} label="Klientdetaljer" />
      <div className="space-y-3">
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="label-xs" htmlFor="sla-client-orgnr">Org.nr *</label>
            <input id="sla-client-orgnr" value={data.client_orgnr ?? ""} onChange={(e) => set({ client_orgnr: e.target.value })}
              placeholder="9 siffer" className="input-sm w-full" />
          </div>
          <button onClick={onLookup} disabled={lookupLoading}
            className="self-end px-3 py-1.5 text-xs rounded bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50 flex items-center gap-1">
            {lookupLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
            Slå opp
          </button>
        </div>
        <div>
          <label className="label-xs" htmlFor="sla-client-navn">Klientnavn *</label>
          <input id="sla-client-navn" value={data.client_navn ?? ""} onChange={(e) => set({ client_navn: e.target.value })}
            className="input-sm w-full" />
        </div>
        <div>
          <label className="label-xs" htmlFor="sla-client-adresse">Adresse</label>
          <textarea id="sla-client-adresse" value={data.client_adresse ?? ""} onChange={(e) => set({ client_adresse: e.target.value })}
            rows={2} className="w-full px-2 py-1.5 text-xs border border-[#D4C9B8] rounded-lg bg-white resize-none focus:outline-none focus:ring-1 focus:ring-[#4A6FA5]" />
        </div>
        <div>
          <label className="label-xs" htmlFor="sla-client-kontakt">Kontaktperson (navn + e-post)</label>
          <input id="sla-client-kontakt" value={data.client_kontakt ?? ""} onChange={(e) => set({ client_kontakt: e.target.value })}
            className="input-sm w-full" />
        </div>
      </div>
      {err && <p className="text-xs text-red-600 mt-2">{err}</p>}
      <NavButtons onNext={handleNext} />
    </>
  );
}
