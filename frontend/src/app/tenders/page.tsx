"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import TenderChatPanel from "@/components/tenders/TenderChatPanel";
import { NewTenderModal } from "@/components/tenders/NewTenderModal";
import {
  getTenders,
  deleteTender,
  getInsurers,
  type TenderListItem,
  type Insurer,
} from "@/lib/api";
import {
  Plus,
  FileText,
  Trash2,
  Send,
  Clock,
  Loader2,
} from "lucide-react";
import Link from "next/link";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useT } from "@/lib/i18n";

const STATUS_KEYS: Record<string, { labelKey: string; color: string }> = {
  draft: { labelKey: "Utkast", color: "bg-gray-100 text-gray-700" },
  sent: { labelKey: "Sendt", color: "bg-blue-50 text-blue-700" },
  closed: { labelKey: "Lukket", color: "bg-yellow-50 text-yellow-700" },
  analysed: { labelKey: "Analysert", color: "bg-green-50 text-green-700" },
};

export default function TendersPage() {
  const T = useT();
  const searchParams = useSearchParams();
  const initialSessionId = searchParams.get("session") ? Number(searchParams.get("session")) : undefined;
  const { data: tenders, isLoading, mutate } = useSWR<TenderListItem[]>("tenders", () => getTenders());
  const { data: insurers } = useSWR<Insurer[]>("insurers", getInsurers);
  const [showNew, setShowNew] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  return (
    <div className="flex gap-6 items-start">
      {/* Left column — tender list (2/3) */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-foreground">{T("Anbud")}</h1>
            <p className="text-sm text-muted-foreground">{T("Opprett og administrer anbudsforespørsler til forsikringsselskaper")}</p>
          </div>
          <button
            onClick={() => setShowNew(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/80"
          >
            <Plus className="w-4 h-4" />
            {T("Nytt anbud")}
          </button>
        </div>

        {/* Tender list */}
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
          </div>
        ) : !tenders?.length ? (
          <div className="broker-card text-center py-12">
            <FileText className="w-10 h-10 mx-auto text-muted-foreground mb-3" />
            <p className="text-muted-foreground">{T("Ingen anbud ennå. Opprett ditt første anbud.")}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {tenders.map((t) => {
              const s = STATUS_KEYS[t.status] || STATUS_KEYS.draft;
              return (
                <Link
                  key={t.id}
                  href={`/tenders/${t.id}`}
                  className="broker-card flex items-center justify-between hover:shadow-md transition-shadow"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="font-semibold text-foreground">{t.title}</h3>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${s.color}`}>
                        {T(s.labelKey)}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span>{t.product_types.join(", ")}</span>
                      {t.deadline && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {T("Frist")}: {t.deadline}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-6 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Send className="w-3.5 h-3.5" />
                      {t.recipient_count} {T("selskaper")}
                    </span>
                    <span className="flex items-center gap-1">
                      <FileText className="w-3.5 h-3.5" />
                      {t.offer_count} {T("tilbud")}
                    </span>
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        setDeleteId(t.id);
                      }}
                      className="p-1.5 hover:bg-red-50 rounded text-muted-foreground hover:text-red-500"
                      aria-label={T("Slett anbud")}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </Link>
              );
            })}
          </div>
        )}

        {showNew && (
          <NewTenderModal
            insurers={insurers || []}
            onClose={() => setShowNew(false)}
            onCreated={() => {
              setShowNew(false);
              mutate();
            }}
          />
        )}

        <ConfirmDialog
          open={deleteId !== null}
          onOpenChange={(o) => { if (!o) setDeleteId(null); }}
          title={T("Slett dette anbudet?")}
          description={T("Handlingen kan ikke angres.")}
          confirmLabel={T("Slett")}
          destructive
          onConfirm={() => {
            if (deleteId !== null) {
              deleteTender(deleteId).then(() => mutate());
            }
          }}
        />
      </div>

      {/* Right column — chat panel, sticky, flush to right edge */}
      <div className="w-80 xl:w-96 flex-shrink-0 sticky top-6 -mr-4 md:-mr-6 xl:-mr-8">
        <TenderChatPanel tenders={tenders ?? []} initialSessionId={initialSessionId} />
      </div>
    </div>
  );
}
