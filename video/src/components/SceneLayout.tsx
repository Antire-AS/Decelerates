import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { colors, fonts } from "../theme";
import { FadeIn } from "./FadeIn";
import { ProgressBar } from "./ProgressBar";
import { BrandLogo } from "./BrandLogo";

export const SceneLayout: React.FC<{
  step: number;
  totalSteps: number;
  icon: string;
  title: string;
  body: string;
  children?: React.ReactNode;
}> = ({ step, totalSteps, icon, title, body, children }) => {
  const frame = useCurrentFrame();

  // Fade out at end of scene
  const fadeOut = interpolate(frame, [120, 150], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: colors.beige,
        fontFamily: fonts.body,
        opacity: fadeOut,
      }}
    >
      {/* Top bar */}
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
        <span
          style={{
            color: "rgba(255,255,255,0.5)",
            fontSize: 14,
            textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}
        >
          Veiledning &middot; Steg {step} av {totalSteps}
        </span>
      </div>

      {/* Progress */}
      <div style={{ padding: "0 60px", marginTop: 0 }}>
        <ProgressBar step={step} total={totalSteps} />
      </div>

      {/* Content area — two columns */}
      <div
        style={{
          flex: 1,
          display: "flex",
          padding: "60px 80px",
          gap: 80,
          alignItems: "center",
        }}
      >
        {/* Left: text */}
        <div style={{ flex: 1 }}>
          <FadeIn delay={10} duration={15}>
            <div style={{ fontSize: 80, marginBottom: 24 }}>{icon}</div>
          </FadeIn>
          <FadeIn delay={20} duration={18}>
            <h1
              style={{
                fontSize: 48,
                fontWeight: 700,
                color: colors.dark,
                margin: "0 0 20px",
                lineHeight: 1.2,
              }}
            >
              {title}
            </h1>
          </FadeIn>
          <FadeIn delay={35} duration={18}>
            <p
              style={{
                fontSize: 24,
                color: colors.muted,
                lineHeight: 1.6,
                maxWidth: 600,
              }}
            >
              {body}
            </p>
          </FadeIn>
        </div>

        {/* Right: visual / children */}
        <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
          <FadeIn delay={25} duration={20} direction="right">
            {children}
          </FadeIn>
        </div>
      </div>

      {/* Bottom dots */}
      <div
        style={{
          padding: "0 0 40px",
          display: "flex",
          justifyContent: "center",
          gap: 12,
        }}
      >
        {Array.from({ length: totalSteps }).map((_, i) => (
          <div
            key={i}
            style={{
              width: i + 1 === step ? 32 : 10,
              height: 10,
              borderRadius: 5,
              background: i + 1 === step ? colors.mid : colors.stone,
              transition: "width 0.3s",
            }}
          />
        ))}
      </div>
    </AbsoluteFill>
  );
};
