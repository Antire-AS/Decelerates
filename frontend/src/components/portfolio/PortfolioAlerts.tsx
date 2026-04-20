"use client";

import { AlertTriangle } from "lucide-react";

interface Alert {
  orgnr: string;
  navn?: string;
  severity: string;
  message: string;
  year?: number;
}

interface Props {
  alerts: Alert[];
}

export function PortfolioAlerts({ alerts }: Props) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-foreground flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-500" /> Varsler
      </p>
      {alerts.map((a, i) => (
        <div key={i} className={`flex items-start gap-2 text-xs rounded-lg px-3 py-2 ${
          a.severity === "high" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          <span><strong>{a.navn ?? a.orgnr}</strong>: {a.message}</span>
        </div>
      ))}
    </div>
  );
}
