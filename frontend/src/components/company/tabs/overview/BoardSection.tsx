import { Users } from "lucide-react";
import type { BoardMember } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Section } from "./shared";

interface Props {
  members: BoardMember[];
}

export default function BoardSection({ members }: Props) {
  const T = useT();
  if (members.length === 0) return null;

  const active = members.filter((m) => !m.resigned && !m.deceased);
  const inactive = members.filter((m) => m.resigned || m.deceased);

  return (
    <Section title={T("Styremedlemmer")}>
      <div className="flex items-center gap-1.5 mb-2 text-xs text-muted-foreground">
        <Users className="w-3.5 h-3.5" />
        <span>{T("Fra Brønnøysundregistrene")}</span>
      </div>
      {active.length > 0 && (
        <div className="space-y-1.5">
          {active.slice(0, 10).map((m, i) => (
            <div key={i} className="flex justify-between items-baseline text-sm gap-2">
              <div className="min-w-0">
                <span className="text-foreground font-medium">{m.name || "–"}</span>
                {m.birth_year && (
                  <span className="text-muted-foreground text-[10px] ml-1.5">{T("f.")} {m.birth_year}</span>
                )}
              </div>
              <span className="text-muted-foreground text-xs text-right flex-shrink-0">{m.role || ""}</span>
            </div>
          ))}
        </div>
      )}
      {inactive.length > 0 && (
        <details className="mt-3 pt-2 border-t border-border">
          <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
            {T("Tidligere medlemmer")} ({inactive.length})
          </summary>
          <div className="space-y-1 mt-2">
            {inactive.slice(0, 10).map((m, i) => (
              <div key={i} className="flex justify-between items-baseline text-xs gap-2 opacity-70">
                <div className="min-w-0">
                  <span className="text-muted-foreground">{m.name || "–"}</span>
                  {m.birth_year && (
                    <span className="text-muted-foreground text-[10px] ml-1.5">{T("f.")} {m.birth_year}</span>
                  )}
                </div>
                <span className="text-muted-foreground text-[10px] text-right flex-shrink-0">
                  {m.deceased ? T("Avdød") : T("Fratrådt")} · {m.role || ""}
                </span>
              </div>
            ))}
          </div>
        </details>
      )}
    </Section>
  );
}
