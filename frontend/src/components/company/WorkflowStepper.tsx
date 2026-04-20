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
      <div className="flex items-start gap-0 bg-card rounded-xl border border-border shadow-sm px-4 py-3">
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
                    isDone   && "bg-primary text-muted-foreground",
                    isActive && !isDone && "bg-primary text-primary-foreground ring-2 ring-ring",
                    !isDone && !isActive && "bg-muted text-muted-foreground border border-border",
                  )}
                >
                  {isDone ? "✓" : isActive ? "●" : ""}
                </div>
                <span
                  className={cn(
                    "text-[9px] text-center leading-tight max-w-[56px]",
                    isDone   && "text-brand-success font-semibold",
                    isActive && !isDone && "text-foreground font-bold",
                    !isDone && !isActive && "text-muted-foreground",
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
                    isDone ? "bg-primary" : "bg-muted",
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Active step hint */}
      {allDone ? (
        <div className="bg-brand-success/10 border-l-4 border-brand-success rounded px-3 py-2 text-xs">
          <span className="font-bold text-foreground">✓ Alle {steps.length} steg fullført</span>
          <span className="text-muted-foreground ml-2">Klientprosessen er komplett.</span>
        </div>
      ) : (
        <div className="bg-accent border-l-4 border-primary rounded px-3 py-2 text-xs">
          <span className="font-bold text-foreground">
            Neste: Steg {activeIdx + 1} — {steps[activeIdx].label}
          </span>
          <span className="text-muted-foreground ml-2">{steps[activeIdx].desc}</span>
        </div>
      )}
    </div>
  );
}
