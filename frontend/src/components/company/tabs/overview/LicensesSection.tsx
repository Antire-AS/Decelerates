import { Shield } from "lucide-react";
import { Section } from "./shared";
import { useT } from "@/lib/i18n";

interface Props {
  licenses: Record<string, unknown> | null | undefined;
}

export default function LicensesSection({ licenses }: Props) {
  const T = useT();
  const licList = ((licenses as Record<string, unknown> | null)?.licenses as Record<string, unknown>[] | undefined) ?? [];
  if (licList.length === 0) return null;

  return (
    <Section title={T("Finanstilsynet — konsesjoner")}>
      <div className="flex items-center gap-1.5 mb-2 text-xs text-muted-foreground">
        <Shield className="w-3.5 h-3.5" />
        <span>{T("Registrerte finanskonsesjoner")}</span>
      </div>
      <div className="space-y-1.5">
        {licList.slice(0, 6).map((l, i) => (
          <div key={i} className="text-xs text-foreground flex items-start gap-1.5">
            <span className="text-brand-warning mt-0.5">•</span>
            <span>
              {String(l.license_type ?? l.name ?? T("Konsesjon"))}
              {!!l.license_status && (
                <span className="text-muted-foreground ml-1">({String(l.license_status)})</span>
              )}
            </span>
          </div>
        ))}
      </div>
    </Section>
  );
}
