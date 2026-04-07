"use client";

import { useDroppable } from "@dnd-kit/core";
import { Plus } from "lucide-react";
import type { DealOut, PipelineStageOut } from "@/lib/api";
import { fmtNok } from "@/lib/format";
import { DealCard } from "./DealCard";

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
  const { setNodeRef, isOver } = useDroppable({
    id: `stage-${stage.id}`,
    data: { stageId: stage.id },
  });

  const total = deals.reduce((sum, d) => sum + (d.expected_premium_nok ?? 0), 0);
  // Per-column accent stripe — falls back to slate when the firm hasn't set a color.
  const accent = stage.color ?? "#94A3B8";

  return (
    <div className="flex-shrink-0 w-72 flex flex-col bg-[#F9F7F4] rounded-lg border border-[#EDE8E3]">
      <div
        className="flex items-center justify-between px-3 py-2 border-b border-[#EDE8E3] rounded-t-lg"
        style={{ borderTopColor: accent, borderTopWidth: 3 }}
      >
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[#2C3E50] truncate">{stage.name}</p>
          <p className="text-[10px] text-[#8A7F74]">
            {deals.length} deal{deals.length === 1 ? "" : "s"}
            {total > 0 && ` · ${fmtNok(total)}`}
          </p>
        </div>
        <button
          onClick={() => onAddDeal(stage.id)}
          aria-label={`Legg til deal i ${stage.name}`}
          className="text-[#8A7F74] hover:text-[#2C3E50] flex-shrink-0"
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
          <p className="text-[10px] text-[#C4BDB4] text-center py-6">
            Slipp en deal her, eller klikk + over.
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
