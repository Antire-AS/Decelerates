"use client";

import { useId } from "react";
import { StepHeader, NavButtons } from "./SlaShared";
import type { SlaData } from "./slaConstants";

interface Props {
  data: SlaData;
  set: (patch: Partial<SlaData>) => void;
  allLines: string[];
  onBack: () => void;
  onNext: () => void;
}

export function Step3Fees({ data, set, allLines, onBack, onNext }: Props) {
  const baseId = useId();
  return (
    <>
      <StepHeader step={3} total={5} label="Honorar (Vedlegg B)" />
      <div className="space-y-4">
        {allLines.map((line, idx) => {
          const existing = data.fee_structure?.lines.find((f) => f.line === line) ?? { line, type: "provisjon", rate: null };
          const update = (patch: Partial<typeof existing>) => {
            const lines = [...(data.fee_structure?.lines ?? [])];
            const lineIdx = lines.findIndex((f) => f.line === line);
            const updated = { ...existing, ...patch };
            if (lineIdx >= 0) lines[lineIdx] = updated; else lines.push(updated);
            set({ fee_structure: { lines } });
          };
          const typeId = `${baseId}-fee-${idx}-type`;
          const rateId = `${baseId}-fee-${idx}-rate`;
          return (
            <div key={line} className="p-3 bg-[#F9F7F4] rounded-lg">
              <p className="text-xs font-semibold text-[#2C3E50] mb-2">{line}</p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="label-xs" htmlFor={typeId}>Honorartype</label>
                  <select id={typeId} value={existing.type} onChange={(e) => update({ type: e.target.value, rate: null })}
                    className="input-sm w-full">
                    <option value="provisjon">Provisjon (%)</option>
                    <option value="fast">Fast honorar (NOK/år)</option>
                    <option value="ikke_avklart">Ikke avklart</option>
                  </select>
                </div>
                {existing.type !== "ikke_avklart" && (
                  <div>
                    <label className="label-xs" htmlFor={rateId}>{existing.type === "provisjon" ? "Sats (%)" : "Beløp (NOK/år)"}</label>
                    <input id={rateId} type="number" min={0} value={existing.rate ?? ""}
                      onChange={(e) => update({ rate: e.target.value ? Number(e.target.value) : null })}
                      className="input-sm w-full" />
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <NavButtons onBack={onBack} onNext={onNext} />
    </>
  );
}
