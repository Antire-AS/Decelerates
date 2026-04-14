import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "./theme";

/* ── FadeIn ─────────────────────────────────────────────────── */

export const FadeIn: React.FC<{
  children: React.ReactNode;
  delay?: number;
  duration?: number;
  direction?: "up" | "down" | "left" | "right" | "none";
  style?: React.CSSProperties;
}> = ({ children, delay = 0, duration = 20, direction = "up", style }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [delay, delay + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const offset = interpolate(frame, [delay, delay + duration], [40, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const transform = {
    up: `translateY(${offset}px)`,
    down: `translateY(${-offset}px)`,
    left: `translateX(${offset}px)`,
    right: `translateX(${-offset}px)`,
    none: "none",
  }[direction];

  return <div style={{ opacity, transform, ...style }}>{children}</div>;
};

/* ── ProgressBar ────────────────────────────────────────────── */

export const ProgressBar: React.FC<{ step: number; total: number }> = ({
  step,
  total,
}) => {
  const frame = useCurrentFrame();
  const width = interpolate(frame, [0, 15], [0, (step / total) * 100], {
    extrapolateRight: "clamp",
  });
  return (
    <div style={{ height: 6, background: colors.stone, borderRadius: 3, overflow: "hidden" }}>
      <div style={{ height: "100%", width: `${width}%`, background: colors.mid, borderRadius: 3 }} />
    </div>
  );
};

/* ── MockCard / MockMetric / RiskBadge ──────────────────────── */

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

/* ── MockSearchBar ──────────────────────────────────────────── */

export const MockSearchBar: React.FC<{ query?: string; delay?: number }> = ({
  query = "DNB Bank ASA",
  delay = 20,
}) => {
  const frame = useCurrentFrame();
  const charsVisible = Math.floor(
    interpolate(frame, [delay, delay + query.length * 3], [0, query.length], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    })
  );
  const showCursor = frame > delay && frame % 16 < 10;
  return (
    <div
      style={{
        background: colors.white,
        border: `2px solid ${colors.mid}`,
        borderRadius: 10,
        padding: "16px 24px",
        display: "flex",
        alignItems: "center",
        gap: 12,
        fontSize: 20,
        color: colors.dark,
        minWidth: 400,
      }}
    >
      <span style={{ fontSize: 22, color: colors.muted }}>&#x1F50D;</span>
      <span>
        {query.slice(0, charsVisible)}
        {showCursor && (
          <span style={{ borderRight: `2px solid ${colors.mid}`, marginLeft: 1 }}>&nbsp;</span>
        )}
      </span>
    </div>
  );
};

/* ── ScaleIcon (inline SVG — matches Lucide Scale) ──────────── */

export const ScaleIcon: React.FC<{ size: number; color?: string }> = ({
  size,
  color = "currentColor",
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
    <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
    <path d="M7 21h10" />
    <path d="M12 3v18" />
    <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2" />
  </svg>
);

/* ── BrandMark / BrandLogo ──────────────────────────────────── */

export const BrandMark: React.FC<{
  boxSize: number;
  borderRadius?: number;
}> = ({ boxSize, borderRadius = 24 }) => (
  <div
    style={{
      width: boxSize,
      height: boxSize,
      borderRadius,
      background: `linear-gradient(135deg, ${colors.mid}, ${colors.dark})`,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      boxShadow: `0 8px 32px ${colors.mid}44`,
    }}
  >
    <ScaleIcon size={boxSize * 0.5} color={colors.white} />
  </div>
);

export const BrandLogo: React.FC<{
  size?: "sm" | "md" | "lg";
  variant?: "light" | "dark";
}> = ({ size = "md", variant = "dark" }) => {
  const dims = {
    sm: { icon: 24, name: 14, sub: 11, gap: 8 },
    md: { icon: 36, name: 20, sub: 14, gap: 12 },
    lg: { icon: 64, name: 40, sub: 24, gap: 20 },
  }[size];
  const fg = variant === "light" ? colors.white : colors.dark;
  const muted = variant === "light" ? colors.light : colors.muted;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: dims.gap }}>
      <ScaleIcon size={dims.icon} color={colors.mid} />
      <div style={{ display: "flex", flexDirection: "column" }}>
        <span style={{ fontSize: dims.name, fontWeight: 700, color: fg, lineHeight: 1.15 }}>Broker</span>
        <span style={{ fontSize: dims.sub, color: muted, lineHeight: 1.15 }}>Accelerator</span>
      </div>
    </div>
  );
};

/* ── SceneLayout ────────────────────────────────────────────── */

export const SceneLayout: React.FC<{
  step: number;
  totalSteps: number;
  icon: string;
  title: string;
  body: string;
  children?: React.ReactNode;
}> = ({ step, totalSteps, icon, title, body, children }) => {
  const frame = useCurrentFrame();
  const fadeOut = interpolate(frame, [120, 150], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: colors.beige,
        fontFamily: fonts.body,
        opacity: fadeOut,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          background: colors.dark,
          padding: "28px 60px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <BrandLogo size="sm" variant="light" />
        <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 14, textTransform: "uppercase", letterSpacing: "0.1em" }}>
          Veiledning &middot; Steg {step} av {totalSteps}
        </span>
      </div>
      <div style={{ padding: "0 60px" }}>
        <ProgressBar step={step} total={totalSteps} />
      </div>
      <div style={{ flex: 1, display: "flex", padding: "60px 80px", gap: 80, alignItems: "center" }}>
        <div style={{ flex: 1 }}>
          <FadeIn delay={10} duration={15}>
            <div style={{ fontSize: 80, marginBottom: 24 }}>{icon}</div>
          </FadeIn>
          <FadeIn delay={20} duration={18}>
            <h1 style={{ fontSize: 48, fontWeight: 700, color: colors.dark, margin: "0 0 20px", lineHeight: 1.2 }}>{title}</h1>
          </FadeIn>
          <FadeIn delay={35} duration={18}>
            <p style={{ fontSize: 24, color: colors.muted, lineHeight: 1.6, maxWidth: 600 }}>{body}</p>
          </FadeIn>
        </div>
        <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
          <FadeIn delay={25} duration={20} direction="right">{children}</FadeIn>
        </div>
      </div>
      <div style={{ padding: "0 0 40px", display: "flex", justifyContent: "center", gap: 12 }}>
        {Array.from({ length: totalSteps }).map((_, i) => (
          <div
            key={i}
            style={{
              width: i + 1 === step ? 32 : 10,
              height: 10,
              borderRadius: 5,
              background: i + 1 === step ? colors.mid : colors.stone,
            }}
          />
        ))}
      </div>
    </div>
  );
};

import { fonts } from "./theme";
