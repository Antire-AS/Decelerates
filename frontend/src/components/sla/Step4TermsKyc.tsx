"use client";

import { StepHeader, NavButtons } from "./SlaShared";
import { STANDARD_VILKAAR, type SlaData } from "./slaConstants";
import { useT } from "@/lib/i18n";

interface Props {
  data: SlaData;
  set: (patch: Partial<SlaData>) => void;
  err: string | null;
  setErr: (e: string | null) => void;
  onBack: () => void;
  onNext: () => void;
}

export function Step4TermsKyc({ data, set, err, setErr, onBack, onNext }: Props) {
  const T = useT();
  function handleNext() {
    const kyc = data.kyc_id_ref && data.kyc_signatory && data.kyc_firmadato;
    const accepted = (data as Record<string, unknown>).kyc_accept_0 && (data as Record<string, unknown>).kyc_accept_1;
    if (!kyc || !accepted) { setErr(T("Fyll ut alle KYC-felt og bekreft vilkårene.")); return; }
    setErr(null);
    onNext();
  }

  const idOptions: { value: string; label: string }[] = [
    { value: "Pass", label: T("Pass") },
    { value: "Nasjonalt ID-kort", label: T("Nasjonalt ID-kort") },
    { value: "Bankkort med bilde", label: T("Bankkort med bilde") },
    { value: "Annet", label: T("Annet") },
  ];

  const confirmations: string[] = [
    T("Kunden bekrefter å ha lest og forstått vilkårene."),
    T("Kunden bekrefter at kundekontroll (KYC/AML) er gjennomført og legitimasjon er fremlagt."),
  ];

  return (
    <>
      <StepHeader step={4} total={5} label={T("Vilkår og KYC")} />
      <div className="space-y-4">
        <div className="bg-muted rounded-lg p-3 max-h-48 overflow-y-auto">
          <p className="text-xs text-foreground whitespace-pre-line">{STANDARD_VILKAAR}</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-xs" htmlFor="kyc-id-type">{T("Type legitimasjon")}</label>
            <select id="kyc-id-type" value={data.kyc_id_type ?? "Pass"} onChange={(e) => set({ kyc_id_type: e.target.value })}
              className="input-sm w-full">
              {idOptions.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label-xs" htmlFor="kyc-id-ref">{T("Dokumentreferanse / ID-nummer")}</label>
            <input id="kyc-id-ref" value={data.kyc_id_ref ?? ""} onChange={(e) => set({ kyc_id_ref: e.target.value })}
              placeholder="e.g. N12345678" className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs" htmlFor="kyc-signatory">{T("Signatarens navn")}</label>
            <input id="kyc-signatory" value={data.kyc_signatory ?? ""} onChange={(e) => set({ kyc_signatory: e.target.value })}
              className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs" htmlFor="kyc-firmadato">{T("Firmaattest dato")}</label>
            <input id="kyc-firmadato" value={data.kyc_firmadato ?? ""} onChange={(e) => set({ kyc_firmadato: e.target.value })}
              placeholder="DD.MM.ÅÅÅÅ" className="input-sm w-full" />
          </div>
        </div>
        {confirmations.map((label, i) => {
          const key = `kyc_accept_${i}` as keyof SlaData;
          return (
            <label key={i} className="flex items-start gap-2 text-xs text-foreground cursor-pointer">
              <input type="checkbox" className="mt-0.5 accent-primary"
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
