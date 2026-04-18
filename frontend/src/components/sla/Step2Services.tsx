"use client";

import { StepHeader, NavButtons } from "./SlaShared";
import { INSURANCE_LINES, type SlaData } from "./slaConstants";

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
  function handleNext() {
    if (!allLines.length) { setErr("Velg minst én forsikringslinje."); return; }
    setErr(null);
    onNext();
  }

  return (
    <>
      <StepHeader step={2} total={5} label="Tjenester (Vedlegg A)" />
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-xs" htmlFor="sla-start-date">Avtalestartdato</label>
            <input id="sla-start-date" type="date" value={data.start_date ?? new Date().toISOString().slice(0, 10)}
              onChange={(e) => set({ start_date: e.target.value })} className="input-sm w-full" />
          </div>
          <div>
            <label className="label-xs" htmlFor="sla-account-manager">Kundeansvarlig</label>
            <input id="sla-account-manager" value={data.account_manager ?? ""} onChange={(e) => set({ account_manager: e.target.value })}
              className="input-sm w-full" />
          </div>
        </div>
        <div>
          <p className="label-xs mb-2">Forsikringslinjer som megleres:</p>
          {Object.entries(INSURANCE_LINES).map(([cat, lines]) => (
            <div key={cat} className="mb-3">
              <p className="text-xs font-medium text-[#8A7F74] mb-1">{cat}</p>
              <div className="flex flex-wrap gap-2">
                {lines.map((line) => (
                  <label key={line}
                    className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border cursor-pointer transition-colors ${
                      data.insurance_lines?.includes(line)
                        ? "bg-[#2C3E50] text-white border-[#2C3E50]"
                        : "border-[#D4C9B8] text-[#2C3E50] hover:bg-[#EDE8E3]"
                    }`}>
                    <input type="checkbox" className="hidden"
                      checked={!!data.insurance_lines?.includes(line)}
                      onChange={() => toggleLine(line)} />
                    {line}
                  </label>
                ))}
              </div>
            </div>
          ))}
          <div>
            <label className="label-xs" htmlFor="sla-other-lines">Andre (spesifiser)</label>
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
