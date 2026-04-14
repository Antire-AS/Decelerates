import React from "react";
import { colors } from "../theme";

/**
 * Scale (balance/justice) icon — matches the Lucide `Scale` used in the real
 * AppShell sidebar. Rendered as inline SVG so we don't need lucide-react as a
 * dependency in the video package.
 */
const ScaleIcon: React.FC<{ size: number; color?: string }> = ({
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

/** Full brand logo matching the AppShell sidebar layout: icon + stacked text */
export const BrandLogo: React.FC<{
  size?: "sm" | "md" | "lg";
  variant?: "light" | "dark";
}> = ({ size = "md", variant = "dark" }) => {
  const dims = { sm: { icon: 24, name: 14, sub: 11, gap: 8 }, md: { icon: 36, name: 20, sub: 14, gap: 12 }, lg: { icon: 64, name: 40, sub: 24, gap: 20 } }[size];
  const fg = variant === "light" ? colors.white : colors.dark;
  const accent = colors.mid;
  const muted = variant === "light" ? colors.light : colors.muted;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: dims.gap }}>
      <ScaleIcon size={dims.icon} color={accent} />
      <div style={{ display: "flex", flexDirection: "column" }}>
        <span style={{ fontSize: dims.name, fontWeight: 700, color: fg, lineHeight: 1.15, letterSpacing: "-0.01em" }}>
          Broker
        </span>
        <span style={{ fontSize: dims.sub, color: muted, lineHeight: 1.15 }}>
          Accelerator
        </span>
      </div>
    </div>
  );
};

/** Standalone icon mark for compact use (intro/outro hero) */
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
