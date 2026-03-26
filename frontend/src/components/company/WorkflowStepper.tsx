"use client";

import { cn } from "@/lib/cn";

export interface WorkflowStep {
  label: string;
  desc: string;
  done: boolean;
}

interface WorkflowStepperProps {
  steps: WorkflowStep[];
}

export default function WorkflowStepper({ steps }: WorkflowStepperProps) {
  const activeIdx = steps.findIndex((s) => !s.done);
  const allDone = activeIdx === -1;

  return (
    <div className="space-y-2 mb-4">
      {/* Step circles */}
      <div className="flex items-start gap-0 bg-white rounded-xl border border-[#E0DBD5] shadow-sm px-4 py-3">
        {steps.map((step, i) => {
          const isDone   = step.done;
          const isActive = i === activeIdx;

          return (
            <div key={i} className="flex items-center flex-1 min-w-0">
              {/* Circle + label */}
              <div className="flex flex-col items-center gap-1 flex-shrink-0">
                <div
                  className={cn(
                    "w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold",
                    isDone   && "bg-[#2C3E50] text-[#D4C9B8]",
                    isActive && !isDone && "bg-[#4A6FA5] text-white ring-2 ring-[#C5D8F0]",
                    !isDone && !isActive && "bg-[#EDEAE6] text-[#A09890] border border-[#D0CBC3]",
                  )}
                >
                  {isDone ? "✓" : i + 1}
                </div>
                <span
                  className={cn(
                    "text-[9px] text-center leading-tight max-w-[56px]",
                    isDone   && "text-[#5A8A5A] font-semibold",
                    isActive && !isDone && "text-[#1A2E40] font-bold",
                    !isDone && !isActive && "text-[#A09890]",
                  )}
                >
                  {step.label.replace(" ", "\u00A0")}
                </span>
              </div>

              {/* Connector line */}
              {i < steps.length - 1 && (
                <div
                  className={cn(
                    "flex-1 h-0.5 mx-1 mt-[-14px]",
                    isDone ? "bg-[#2C3E50]" : "bg-[#D0CBC3]",
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Active step hint */}
      {allDone ? (
        <div className="bg-[#F0F7F0] border-l-4 border-[#5A8A5A] rounded px-3 py-2 text-xs">
          <span className="font-bold text-[#2C3E50]">✓ Alle {steps.length} steg fullført</span>
          <span className="text-[#5A6A7A] ml-2">Klientprosessen er komplett.</span>
        </div>
      ) : (
        <div className="bg-[#EEF4FC] border-l-4 border-[#4A6FA5] rounded px-3 py-2 text-xs">
          <span className="font-bold text-[#2C3E50]">
            Neste: Steg {activeIdx + 1} — {steps[activeIdx].label}
          </span>
          <span className="text-[#5A6A7A] ml-2">{steps[activeIdx].desc}</span>
        </div>
      )}
    </div>
  );
}
