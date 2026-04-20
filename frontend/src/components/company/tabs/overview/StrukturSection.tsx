import type { StrukturOut } from "@/lib/api";
import { Section } from "./shared";

interface Props {
  struktur?: StrukturOut | null;
}

export default function StrukturSection({ struktur }: Props) {
  if (!struktur) return null;
  const hasParent = !!struktur.parent;
  const subUnits = (struktur.sub_units as Record<string, unknown>[] | undefined) ?? [];
  if (!hasParent && subUnits.length === 0) return null;

  const p = (struktur.parent ?? {}) as Record<string, unknown>;
  const totalSubs = (struktur.total_sub_units as number | undefined) ?? subUnits.length;

  return (
    <Section title="Konsernstruktur">
      {hasParent && (
        <div className="rounded-lg bg-accent border border-border px-3 py-2 mb-3">
          <p className="text-[10px] font-bold uppercase tracking-wide text-primary mb-1">Morselskap</p>
          <p className="text-sm font-semibold text-foreground">{String(p.navn ?? "–")}</p>
          <p className="text-xs text-muted-foreground">
            {[p.orgnr, p.kommune, p.organisasjonsform].filter(Boolean).join(" · ")}
          </p>
        </div>
      )}
      {subUnits.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1.5">
            Underenheter ({totalSubs})
          </p>
          <div className="space-y-1">
            {subUnits.slice(0, 8).map((s, i) => (
              <div key={i} className="flex justify-between text-xs">
                <span className="text-foreground font-medium">{String(s.navn ?? "–")}</span>
                <span className="text-muted-foreground">{String(s.orgnr ?? "")}</span>
              </div>
            ))}
            {totalSubs > 8 && (
              <p className="text-xs text-muted-foreground">+ {totalSubs - 8} flere</p>
            )}
          </div>
        </div>
      )}
    </Section>
  );
}
