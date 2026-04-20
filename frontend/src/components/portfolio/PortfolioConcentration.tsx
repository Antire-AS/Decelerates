"use client";

import { useT } from "@/lib/i18n";

interface ConcentrationItem {
  label: string;
  count: number;
}

interface ConcentrationData {
  industry: ConcentrationItem[];
  geography: ConcentrationItem[];
  size: ConcentrationItem[];
}

interface Props {
  concentration: ConcentrationData;
}

export function PortfolioConcentration({ concentration }: Props) {
  const T = useT();
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {(["industry", "geography", "size"] as const).map((key) => {
        const items = concentration[key] ?? [];
        const labels: Record<string, string> = { industry: T("Bransje"), geography: T("Geografi"), size: T("Størrelse") };
        return (
          <div key={key}>
            <p className="text-xs font-semibold text-foreground mb-1">{labels[key]}</p>
            <div className="space-y-1">
              {items.slice(0, 5).map((item) => (
                <div key={item.label} className="flex justify-between text-xs">
                  <span className="text-muted-foreground truncate max-w-[120px]">{item.label}</span>
                  <span className="font-medium text-foreground">{item.count}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
