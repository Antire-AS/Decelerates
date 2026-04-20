"use client";

import { useDraggable } from "@dnd-kit/core";
import { Calendar, GripVertical, Trash2, User } from "lucide-react";
import type { DealOut } from "@/lib/api";
import { fmtNok } from "@/lib/format";
import { useT } from "@/lib/i18n";

/**
 * One deal card on the kanban board. Draggable via @dnd-kit. The card itself
 * is the drag handle (whole card is grabbable) — we surface a `GripVertical`
 * icon as visual affordance.
 *
 * `companyName` is denormalized from a separate fetch — the Deal model only
 * stores orgnr.
 */
export function DealCard({
  deal,
  companyName,
  onDelete,
}: {
  deal: DealOut;
  companyName?: string;
  onDelete: (deal: DealOut) => void;
}) {
  const T = useT();
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: deal.id.toString(),
    data: { deal },
  });

  const style: React.CSSProperties = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
        zIndex: 50,
      }
    : {};

  const daysInStage = (() => {
    if (!deal.updated_at) return null;
    const updated = new Date(deal.updated_at);
    const diff = Math.floor((Date.now() - updated.getTime()) / (1000 * 60 * 60 * 24));
    return diff;
  })();

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`bg-card border border-border rounded-lg p-3 space-y-2 select-none
                  ${isDragging ? "opacity-50 shadow-lg" : "shadow-sm hover:shadow-md transition-shadow"}`}
    >
      <div className="flex items-start gap-2">
        <button
          {...listeners}
          {...attributes}
          aria-label={T("Dra for å flytte")}
          className="touch-none cursor-grab active:cursor-grabbing text-muted-foreground hover:text-muted-foreground flex-shrink-0 mt-0.5"
        >
          <GripVertical className="w-4 h-4" />
        </button>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground truncate" title={companyName ?? deal.orgnr}>
            {companyName ?? deal.orgnr}
          </p>
          {deal.title && (
            <p className="text-xs text-muted-foreground truncate" title={deal.title}>
              {deal.title}
            </p>
          )}
        </div>
        <button
          onClick={() => onDelete(deal)}
          aria-label={T("Slett deal")}
          className="text-muted-foreground hover:text-red-500 flex-shrink-0"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {deal.expected_premium_nok != null && (
        <p className="text-xs font-medium text-emerald-700">
          {fmtNok(deal.expected_premium_nok)}
        </p>
      )}

      <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
        {deal.expected_close_date && (
          <span className="flex items-center gap-0.5">
            <Calendar className="w-3 h-3" /> {deal.expected_close_date}
          </span>
        )}
        {deal.owner_user_id != null && (
          <span
            className="flex items-center gap-0.5"
            title={`${T("Bruker-ID")} ${deal.owner_user_id} ${T("eier denne dealen")}`}
          >
            <User className="w-3 h-3" /> #{deal.owner_user_id}
          </span>
        )}
        {daysInStage != null && daysInStage >= 0 && (
          <span
            className={daysInStage > 30 ? "text-amber-600" : ""}
            title={`${daysInStage} ${daysInStage === 1 ? T("dag i denne fasen") : T("dager i denne fasen")}`}
          >
            {daysInStage}d
          </span>
        )}
      </div>
    </div>
  );
}
