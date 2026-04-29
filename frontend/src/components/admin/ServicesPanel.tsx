"use client";

import useSWR from "swr";
import { CheckCircle2, XCircle, AlertCircle, ShieldAlert } from "lucide-react";
import { getServicesHealth, type ServicesHealthOut } from "@/lib/api";
import { useT } from "@/lib/i18n";

const STATUS_PILL: Record<
  string,
  { bg: string; icon: typeof CheckCircle2; label: string }
> = {
  operational:   { bg: "bg-emerald-100 text-emerald-700", icon: CheckCircle2, label: "Operativ" },
  degraded:      { bg: "bg-amber-100 text-amber-700",     icon: AlertCircle,  label: "Tregt"   },
  auth_required: { bg: "bg-amber-100 text-amber-700",     icon: ShieldAlert,  label: "Krever auth" },
  down:          { bg: "bg-red-100 text-red-700",         icon: XCircle,      label: "Nede"    },
};

export default function ServicesPanel() {
  const T = useT();
  const { data } = useSWR<ServicesHealthOut>(
    "admin-services-health",
    getServicesHealth,
    { refreshInterval: 60_000 },
  );
  const services = data?.services ?? [];

  return (
    <div className="broker-card">
      <h2 className="text-sm font-semibold text-foreground mb-3">{T("Eksterne tjenester")}</h2>
      <div className="space-y-2">
        {services.length === 0 && (
          <p className="text-xs text-muted-foreground italic">{T("Laster…")}</p>
        )}
        {services.map((s) => {
          const meta = STATUS_PILL[s.status] ?? STATUS_PILL.degraded;
          const Icon = meta.icon;
          return (
            <div
              key={s.name}
              className="flex items-center justify-between gap-3 py-2 border-b border-border last:border-0"
            >
              <div className="flex items-center gap-2 min-w-0">
                <Icon className="w-4 h-4 text-muted-foreground shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{s.name}</p>
                  {s.note && (
                    <p className="text-xs text-muted-foreground">{s.note}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={`text-[11px] font-medium px-2 py-0.5 rounded ${meta.bg}`}>
                  {T(meta.label)}
                </span>
                {s.latency_ms != null && (
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {s.latency_ms} ms
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
