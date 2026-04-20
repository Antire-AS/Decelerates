"use client";

import { StepHeader, NavButtons } from "./SlaShared";
import { INSURANCE_LINES, type SlaData } from "./slaConstants";
import { useT } from "@/lib/i18n";

interface Props {
  data: SlaData;
  set: (patch: Partial<SlaData>) => void;
  err: string | null;
  setErr: (e: string | null) => void;
  allLines: string[];
  toggleLine: (line: string) => void;
  onBack: () => void;
  onNext: () => void;
}

export function Step2Services({ data, set, err, setErr, allLines, toggleLine, onBack, onNext }: Props) {
  const T = useT();
  function handleNext() {
    if (!allLines.length) { setErr(T("Velg minst én forsikringslinje.")); return; }
    setErr(null);
    onNext();
  }

  return (
    <>
      <StepHeader step={2} total={5} label={T("Tjenester (Vedlegg A)")} />
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-xs" htmlFor="sla-start-date">{T("Avtalestartdato")}</label>
            <input id="sla-start-date" type="date" value={data.start_date ?? new Date().toISOString().slice(0, 10)}
              onChange={(e) => set({ start_date: e.target.value })} className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs" htmlFor="sla-account-manager">{T("Kundeansvarlig")}</label>
            <input id="sla-account-manager" value={data.account_manager ?? ""} onChange={(e) => set({ account_manager: e.target.value })}
              className="input-sm w-full" />
          </div>
        </div>
        <div>
          <p className="label-xs mb-2">{T("Forsikringslinjer som megleres:")}</p>
          {Object.entries(INSURANCE_LINES).map(([cat, lines]) => (
            <div key={cat} className="mb-3">
              <p className="text-xs font-medium text-muted-foreground mb-1">{T(cat)}</p>
              <div className="flex flex-wrap gap-2">
                {lines.map((line) => (
                  <label key={line}
                    className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border cursor-pointer transition-colors ${
                      data.insurance_lines?.includes(line)
                        ? "bg-primary text-primary-foreground border-primary"
                        : "border-border text-foreground hover:bg-muted"
                    }`}>
                    <input type="checkbox" className="hidden"
                      checked={!!data.insurance_lines?.includes(line)}
                      onChange={() => toggleLine(line)} />
                    {T(line)}
                  </label>
                ))}
              </div>
            </div>
          ))}
          <div>
            <label className="label-xs" htmlFor="sla-other-lines">{T("Andre (spesifiser)")}</label>
            <input id="sla-other-lines" value={data.other_lines ?? ""} onChange={(e) => set({ other_lines: e.target.value })}
              className="input-sm w-full" />
          </div>
        </div>
      </div>
      <NavButtons onBack={onBack} onNext={handleNext} />
      {err && <p className="text-xs text-red-600 mt-2">{err}</p>}
    </>
  );
}
