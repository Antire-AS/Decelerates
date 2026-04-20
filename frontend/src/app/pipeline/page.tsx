"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
} from "@dnd-kit/core";
import { Plus, Loader2 } from "lucide-react";
import {
  getDeals,
  getPipelineStages,
  moveDealStage,
  deleteDeal,
  getOrgProfile,
  type DealOut,
  type PipelineStageOut,
} from "@/lib/api";
import { KanbanColumn } from "@/components/pipeline/KanbanColumn";
import { NewDealModal } from "@/components/pipeline/NewDealModal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useT } from "@/lib/i18n";

/**
 * Plan §🟢 #9 — kanban deal pipeline.
 *
 * Two SWR queries (stages + deals) feed a DndContext that handles drag-end
 * by calling PATCH /deals/{id}/stage. We optimistically update the local
 * deal list before the network call so the card snaps to the new column
 * immediately; the SWR mutate at the end reconciles with the server truth.
 */
export default function PipelinePage() {
  const T = useT();
  const { data: stages = [], error: stagesErr, isLoading: stagesLoading } = useSWR<PipelineStageOut[]>(
    "pipeline-stages",
    () => getPipelineStages(),
  );
  const { data: deals = [], mutate: mutateDeals, isLoading: dealsLoading } = useSWR<DealOut[]>(
    "deals",
    () => getDeals(),
  );

  // Local mirror for optimistic drag-end. Whenever the SWR fetch returns
  // fresh data, sync into local. The optimistic updater writes here first
  // so the card moves before the network call resolves.
  const [localDeals, setLocalDeals] = useState<DealOut[]>([]);
  useEffect(() => {
    setLocalDeals(deals);
  }, [deals]);

  // Lazy company-name lookup so cards show "DNB Bank ASA" instead of "984851006".
  // Cached per orgnr — only fires the first time we see a deal for that company.
  const [companyNames, setCompanyNames] = useState<Record<string, string>>({});
  useEffect(() => {
    const missing = Array.from(
      new Set(localDeals.map((d) => d.orgnr).filter((o) => !(o in companyNames)))
    );
    if (missing.length === 0) return;
    let cancelled = false;
    (async () => {
      const updates: Record<string, string> = {};
      await Promise.all(
        missing.map(async (orgnr) => {
          try {
            const prof = await getOrgProfile(orgnr);
            const navn = (prof.org as Record<string, unknown>)?.navn;
            if (typeof navn === "string") updates[orgnr] = navn;
          } catch {
            // Profile fetch is best-effort; fall back to orgnr in the card.
          }
        })
      );
      if (!cancelled && Object.keys(updates).length > 0) {
        setCompanyNames((prev) => ({ ...prev, ...updates }));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [localDeals, companyNames]);

  const [modalOpen, setModalOpen] = useState(false);
  const [modalStageId, setModalStageId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<DealOut | null>(null);

  const sensors = useSensors(
    // 5px activation distance prevents accidental drags on click.
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  // Group deals by stage_id for column rendering.
  const dealsByStage = useMemo(() => {
    const m: Record<number, DealOut[]> = {};
    for (const d of localDeals) {
      (m[d.stage_id] ??= []).push(d);
    }
    return m;
  }, [localDeals]);

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;
    const overData = over.data.current as { stageId?: number } | undefined;
    const newStageId = overData?.stageId;
    if (newStageId == null) return;
    const dealId = Number(active.id);
    const deal = localDeals.find((d) => d.id === dealId);
    if (!deal || deal.stage_id === newStageId) return;

    // Optimistic — move the card immediately.
    setLocalDeals((prev) =>
      prev.map((d) => (d.id === dealId ? { ...d, stage_id: newStageId } : d))
    );

    try {
      await moveDealStage(dealId, newStageId);
      // Re-sync from server (handles server-side mutations like won_at stamping).
      mutateDeals();
    } catch (e) {
      // Roll back on failure.
      setLocalDeals((prev) =>
        prev.map((d) => (d.id === dealId ? { ...d, stage_id: deal.stage_id } : d))
      );
      // Best-effort surfacing — a toast system would be nicer (out of scope).
      console.error("Failed to move deal:", e);
    }
  }

  function handleDeleteDeal(d: DealOut) {
    setPendingDelete(d);
  }

  async function performDeleteDeal(d: DealOut) {
    setLocalDeals((prev) => prev.filter((x) => x.id !== d.id));
    try {
      await deleteDeal(d.id);
      mutateDeals();
    } catch (e) {
      console.error("Failed to delete deal:", e);
      mutateDeals();  // re-fetch to reset state
    }
  }

  function handleAddDeal(stageId: number) {
    setModalStageId(stageId);
    setModalOpen(true);
  }

  const isLoading = stagesLoading || dealsLoading;
  const hasError = stagesErr;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">{T("Pipeline")}</h1>
        <button
          onClick={() => {
            setModalStageId(stages[0]?.id ?? null);
            setModalOpen(true);
          }}
          disabled={stages.length === 0}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Plus className="w-3.5 h-3.5" /> {T("Ny deal")}
        </button>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" /> {T("Laster pipeline…")}
        </div>
      )}

      {hasError && (
        <p className="text-sm text-red-600">{T("Kunne ikke laste pipeline. Sjekk at API-en kjører.")}</p>
      )}

      {!isLoading && stages.length === 0 && (
        <div className="broker-card">
          <p className="text-sm text-muted-foreground">
            {T("Ingen pipeline-stages konfigurert for ditt firma. Standard stages opprettes automatisk via Alembic-migrasjonen — kontakt en admin hvis denne meldingen vises i prod.")}
          </p>
        </div>
      )}

      {stages.length > 0 && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <div className="flex gap-3 overflow-x-auto pb-4 -mx-4 px-4">
            {stages.map((stage) => (
              <KanbanColumn
                key={stage.id}
                stage={stage}
                deals={dealsByStage[stage.id] ?? []}
                companyNames={companyNames}
                onAddDeal={handleAddDeal}
                onDeleteDeal={handleDeleteDeal}
              />
            ))}
          </div>
        </DndContext>
      )}

      {modalOpen && modalStageId != null && (
        <NewDealModal
          stages={stages}
          defaultStageId={modalStageId}
          onClose={() => setModalOpen(false)}
          onCreated={(deal) => {
            setLocalDeals((prev) => [deal, ...prev]);
            mutateDeals();
          }}
        />
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(o) => { if (!o) setPendingDelete(null); }}
        title={pendingDelete ? `${T("Slett deal")} "${pendingDelete.title ?? pendingDelete.orgnr}"?` : ""}
        description={T("Handlingen kan ikke angres.")}
        confirmLabel={T("Slett")}
        destructive
        onConfirm={() => {
          if (pendingDelete) performDeleteDeal(pendingDelete);
        }}
      />
    </div>
  );
}
