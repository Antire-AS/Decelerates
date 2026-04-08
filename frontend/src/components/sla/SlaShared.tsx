"use client";

import { Loader2 } from "lucide-react";

export function StepHeader({ step, total, label }: { step: number; total: number; label: string }) {
  return (
    <div className="mb-4">
      <div className="flex items-center gap-3 mb-2">
        <div className="h-1.5 flex-1 bg-[#EDE8E3] rounded-full overflow-hidden">
          <div className="h-full bg-[#2C3E50] rounded-full transition-all" style={{ width: `${(step / total) * 100}%` }} />
        </div>
        <span className="text-xs text-[#8A7F74] whitespace-nowrap">Steg {step} av {total}</span>
      </div>
      <h2 className="text-sm font-semibold text-[#2C3E50]">{label}</h2>
    </div>
  );
}

export function NavButtons({ onBack, onNext, nextLabel = "Neste →", nextDisabled = false, loading = false }: {
  onBack?: () => void; onNext: () => void; nextLabel?: string; nextDisabled?: boolean; loading?: boolean;
}) {
  return (
    <div className="flex gap-2 mt-4">
      {onBack && (
        <button onClick={onBack}
          className="px-3 py-1.5 text-xs rounded border border-[#D4C9B8] text-[#8A7F74] hover:bg-[#EDE8E3]">
          ← Tilbake
        </button>
      )}
      <button onClick={onNext} disabled={nextDisabled || loading}
        className="px-4 py-1.5 text-xs rounded bg-[#2C3E50] text-white hover:bg-[#3d5166] disabled:opacity-50 flex items-center gap-1">
        {loading && <Loader2 className="w-3 h-3 animate-spin" />}
        {nextLabel}
      </button>
    </div>
  );
}
