import { Shield } from "lucide-react";
import { Section } from "./shared";

interface Props {
  licenses: Record<string, unknown> | null | undefined;
}

export default function LicensesSection({ licenses }: Props) {
  const licList = ((licenses as Record<string, unknown> | null)?.licenses as Record<string, unknown>[] | undefined) ?? [];
  if (licList.length === 0) return null;

  return (
    <Section title="Finanstilsynet — konsesjoner">
      <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8A7F74]">
        <Shield className="w-3.5 h-3.5" />
        <span>Registrerte finanskonsesjoner</span>
      </div>
      <div className="space-y-1.5">
        {licList.slice(0, 6).map((l, i) => (
          <div key={i} className="text-xs text-[#2C3E50] flex items-start gap-1.5">
            <span className="text-[#C8A951] mt-0.5">•</span>
            <span>
              {String(l.license_type ?? l.name ?? "Konsesjon")}
              {!!l.license_status && (
                <span className="text-[#8A7F74] ml-1">({String(l.license_status)})</span>
              )}
            </span>
          </div>
        ))}
      </div>
    </Section>
  );
}
