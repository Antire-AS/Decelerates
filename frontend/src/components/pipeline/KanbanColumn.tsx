"use client";

import { useDroppable } from "@dnd-kit/core";
import { Plus } from "lucide-react";
import type { DealOut, PipelineStageOut } from "@/lib/api";
import { fmtNok } from "@/lib/format";
import { DealCard } from "./DealCard";
import { useT } from "@/lib/i18n";

/**
 * One kanban column = one PipelineStage. Drop target for cards being dragged
 * from other columns. Shows the running total of expected premium so brokers
 * see funnel value at a glance.
 */
export function KanbanColumn({
  stage,
  deals,
  companyNames,
  onAddDeal,
  onDeleteDeal,
}: {
  stage: PipelineStageOut;
  deals: DealOut[];
  companyNames: Record<string, string>;
  onAddDeal: (stageId: number) => void;
  onDeleteDeal: (deal: DealOut) => void;
}) {
  const T = useT();
  const { setNodeRef, isOver } = useDroppable({
    id: `stage-${stage.id}`,
    data: { stageId: stage.id },
  });

  const total = deals.reduce((sum, d) => sum + (d.expected_premium_nok ?? 0), 0);
  // Per-column accent stripe — falls back to slate when the firm hasn't set a color.
  const accent = stage.color ?? "#94A3B8";

  return (
    <div className="flex-shrink-0 w-72 flex flex-col bg-muted rounded-lg border border-border">
      <div
        className="flex items-center justify-between px-3 py-2 border-b border-border rounded-t-lg"
        style={{ borderTopColor: accent, borderTopWidth: 3 }}
      >
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground truncate">{stage.name}</p>
          <p className="text-[10px] text-muted-foreground">
            {deals.length} {deals.length === 1 ? T("deal") : T("deals")}
            {total > 0 && ` · ${fmtNok(total)}`}
          </p>
        </div>
        <button
          onClick={() => onAddDeal(stage.id)}
          aria-label={`${T("Legg til deal i")} ${stage.name}`}
          className="text-muted-foreground hover:text-foreground flex-shrink-0"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      <div
        ref={setNodeRef}
        className={`flex-1 min-h-[200px] p-2 space-y-2 transition-colors ${
          isOver ? "bg-blue-50/60" : ""
        }`}
      >
        {deals.length === 0 ? (
          <p className="text-[10px] text-muted-foreground text-center py-6">
            {T("Slipp en deal her, eller klikk + over.")}
          </p>
        ) : (
          deals.map((d) => (
            <DealCard
              key={d.id}
              deal={d}
              companyName={companyNames[d.orgnr]}
              onDelete={onDeleteDeal}
            />
          ))
        )}
      </div>
    </div>
  );
}
