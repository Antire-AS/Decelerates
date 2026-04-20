"use client";

import { Loader2 } from "lucide-react";
import { useT } from "@/lib/i18n";

export function StepHeader({ step, total, label }: { step: number; total: number; label: string }) {
  const T = useT();
  return (
    <div className="mb-4">
      <div className="flex items-center gap-3 mb-2">
        <div className="h-1.5 flex-1 bg-muted rounded-full overflow-hidden">
          <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${(step / total) * 100}%` }} />
        </div>
        <span className="text-xs text-muted-foreground whitespace-nowrap">{T("Steg")} {step} {T("av")} {total}</span>
      </div>
      <h2 className="text-sm font-semibold text-foreground">{label}</h2>
    </div>
  );
}

export function NavButtons({ onBack, onNext, nextLabel, nextDisabled = false, loading = false }: {
  onBack?: () => void; onNext: () => void; nextLabel?: string; nextDisabled?: boolean; loading?: boolean;
}) {
  const T = useT();
  const label = nextLabel ?? `${T("Neste")} →`;
  return (
    <div className="flex gap-2 mt-4">
      {onBack && (
        <button onClick={onBack}
          className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:bg-muted">
          ← {T("Tilbake")}
        </button>
      )}
      <button onClick={onNext} disabled={nextDisabled || loading}
        className="px-4 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1">
        {loading && <Loader2 className="w-3 h-3 animate-spin" />}
        {label}
      </button>
    </div>
  );
}
