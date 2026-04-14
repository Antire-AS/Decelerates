import React from "react";
import { colors } from "../theme";

/** Reusable card that matches the broker-card styling from the real app */
export const MockCard: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ children, style }) => (
  <div
    style={{
      background: colors.white,
      border: `1px solid ${colors.stone}`,
      borderRadius: 12,
      padding: 28,
      boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
      ...style,
    }}
  >
    {children}
  </div>
);

/** Simulated metric badge (like MetricCard on the dashboard) */
export const MockMetric: React.FC<{
  label: string;
  value: string;
  color?: string;
}> = ({ label, value, color = colors.dark }) => (
  <MockCard style={{ textAlign: "center", minWidth: 160 }}>
    <div style={{ fontSize: 14, color: colors.muted, marginBottom: 8 }}>{label}</div>
    <div style={{ fontSize: 32, fontWeight: 700, color }}>{value}</div>
  </MockCard>
);

/** Risk badge matching broker-badge-* classes */
export const RiskBadge: React.FC<{
  level: "low" | "mid" | "high";
  label: string;
}> = ({ level, label }) => {
  const bg = { low: "#EBF5EB", mid: "#FFF8E1", high: "#FDEDED" }[level];
  const fg = { low: colors.success, mid: colors.warning, high: colors.danger }[level];
  return (
    <span
      style={{
        display: "inline-block",
        padding: "4px 14px",
        borderRadius: 20,
        background: bg,
        color: fg,
        fontSize: 14,
        fontWeight: 600,
      }}
    >
      {label}
    </span>
  );
};
