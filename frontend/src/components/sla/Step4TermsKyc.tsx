"use client";

import { StepHeader, NavButtons } from "./SlaShared";
import { STANDARD_VILKAAR, type SlaData } from "./slaConstants";

interface Props {
  data: SlaData;
  set: (patch: Partial<SlaData>) => void;
  err: string | null;
  setErr: (e: string | null) => void;
  onBack: () => void;
  onNext: () => void;
}

export function Step4TermsKyc({ data, set, err, setErr, onBack, onNext }: Props) {
  function handleNext() {
    const kyc = data.kyc_id_ref && data.kyc_signatory && data.kyc_firmadato;
    const accepted = (data as Record<string, unknown>).kyc_accept_0 && (data as Record<string, unknown>).kyc_accept_1;
    if (!kyc || !accepted) { setErr("Fyll ut alle KYC-felt og bekreft vilkårene."); return; }
    setErr(null);
    onNext();
  }

  return (
    <>
      <StepHeader step={4} total={5} label="Vilkår og KYC" />
      <div className="space-y-4">
        <div className="bg-[#F9F7F4] rounded-lg p-3 max-h-48 overflow-y-auto">
          <p className="text-xs text-[#2C3E50] whitespace-pre-line">{STANDARD_VILKAAR}</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-xs" htmlFor="kyc-id-type">Type legitimasjon</label>
            <select id="kyc-id-type" value={data.kyc_id_type ?? "Pass"} onChange={(e) => set({ kyc_id_type: e.target.value })}
              className="input-sm w-full">
              {["Pass", "Nasjonalt ID-kort", "Bankkort med bilde", "Annet"].map((v) => <option key={v}>{v}</option>)}
            </select>
          </div>
          <div>
            <label className="label-xs" htmlFor="kyc-id-ref">Dokumentreferanse / ID-nummer</label>
            <input id="kyc-id-ref" value={data.kyc_id_ref ?? ""} onChange={(e) => set({ kyc_id_ref: e.target.value })}
              placeholder="e.g. N12345678" className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs" htmlFor="kyc-signatory">Signatarens navn</label>
            <input id="kyc-signatory" value={data.kyc_signatory ?? ""} onChange={(e) => set({ kyc_signatory: e.target.value })}
              className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs" htmlFor="kyc-firmadato">Firmaattest dato</label>
            <input id="kyc-firmadato" value={data.kyc_firmadato ?? ""} onChange={(e) => set({ kyc_firmadato: e.target.value })}
              placeholder="DD.MM.ÅÅÅÅ" className="input-sm w-full" />
          </div>
        </div>
        {[
          "Kunden bekrefter å ha lest og forstått vilkårene.",
          "Kunden bekrefter at kundekontroll (KYC/AML) er gjennomført og legitimasjon er fremlagt.",
        ].map((label, i) => {
          const key = `kyc_accept_${i}` as keyof SlaData;
          return (
            <label key={i} className="flex items-start gap-2 text-xs text-[#2C3E50] cursor-pointer">
              <input type="checkbox" className="mt-0.5 accent-[#4A6FA5]"
                checked={!!(data as Record<string, unknown>)[key]}
                onChange={(e) => set({ [key]: e.target.checked } as Partial<SlaData>)} />
              {label}
            </label>
          );
        })}
      </div>
      <NavButtons onBack={onBack} onNext={handleNext} />
      {err && <p className="text-xs text-red-600 mt-2">{err}</p>}
    </>
  );
}
