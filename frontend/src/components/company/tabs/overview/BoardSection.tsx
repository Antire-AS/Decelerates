import { Users } from "lucide-react";
import type { BoardMember } from "@/lib/api";
import { Section } from "./shared";

interface Props {
  members: BoardMember[];
}

export default function BoardSection({ members }: Props) {
  if (members.length === 0) return null;

  const active = members.filter((m) => !m.resigned && !m.deceased);
  const inactive = members.filter((m) => m.resigned || m.deceased);

  return (
    <Section title="Styremedlemmer">
      <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
        <Users className="w-3.5 h-3.5" />
        <span>Fra Brønnøysundregistrene</span>
      </div>
      {active.length > 0 && (
        <div className="space-y-1.5">
          {active.slice(0, 10).map((m, i) => (
            <div key={i} className="flex justify-between items-baseline text-sm gap-2">
              <div className="min-w-0">
                <span className="text-[#2C3E50] font-medium">{m.name || "–"}</span>
                {m.birth_year && (
                  <span className="text-[#C4BDB4] text-[10px] ml-1.5">f. {m.birth_year}</span>
                )}
              </div>
              <span className="text-[#8A7F74] text-xs text-right flex-shrink-0">{m.role || ""}</span>
            </div>
          ))}
        </div>
      )}
      {inactive.length > 0 && (
        <details className="mt-3 pt-2 border-t border-[#EDE8E3]">
          <summary className="text-xs text-[#8A7F74] cursor-pointer hover:text-[#2C3E50]">
            Tidligere medlemmer ({inactive.length})
          </summary>
          <div className="space-y-1 mt-2">
            {inactive.slice(0, 10).map((m, i) => (
              <div key={i} className="flex justify-between items-baseline text-xs gap-2 opacity-70">
                <div className="min-w-0">
                  <span className="text-[#8A7F74]">{m.name || "–"}</span>
                  {m.birth_year && (
                    <span className="text-[#C4BDB4] text-[10px] ml-1.5">f. {m.birth_year}</span>
                  )}
                </div>
                <span className="text-[#C4BDB4] text-[10px] text-right flex-shrink-0">
                  {m.deceased ? "Avdød" : "Fratrådt"} · {m.role || ""}
                </span>
              </div>
            ))}
          </div>
        </details>
      )}
    </Section>
  );
}
