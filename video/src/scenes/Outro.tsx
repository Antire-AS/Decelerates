import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { colors, fonts } from "../theme";
import { BrandMark } from "../components/BrandLogo";

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [0, 25], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scaleY = interpolate(frame, [20, 50], [20, 0], {
    extrapolateRight: "clamp",
  });
  const ctaOpacity = interpolate(frame, [50, 70], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: colors.dark,
        fontFamily: fonts.body,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        opacity,
      }}
    >
      <div style={{ marginBottom: 32 }}>
        <BrandMark boxSize={100} borderRadius={20} />
      </div>

      <h1
        style={{
          color: colors.white,
          fontSize: 52,
          fontWeight: 700,
          margin: 0,
          transform: `translateY(${scaleY}px)`,
        }}
      >
        Klar til a komme i gang?
      </h1>

      <div
        style={{
          opacity: ctaOpacity,
          marginTop: 32,
          padding: "16px 48px",
          borderRadius: 12,
          background: colors.mid,
          color: colors.white,
          fontSize: 24,
          fontWeight: 600,
        }}
      >
        meglerai.no
      </div>

      <p
        style={{
          opacity: ctaOpacity,
          color: colors.light,
          fontSize: 18,
          marginTop: 24,
        }}
      >
        Broker Accelerator &mdash; forsikringsmegling, akselerert.
      </p>
    </AbsoluteFill>
  );
};
