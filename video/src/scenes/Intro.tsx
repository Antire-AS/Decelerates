import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { colors, fonts } from "../theme";
import { BrandMark, BrandLogo } from "../components/BrandLogo";
import { BrandMark, BrandLogo } from "../components/BrandLogo";

export const Intro: React.FC = () => {
  const frame = useCurrentFrame();

  const logoScale = interpolate(frame, [0, 30], [0.6, 1], {
    extrapolateRight: "clamp",
  });
  const logoOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateRight: "clamp",
  });
  const titleOpacity = interpolate(frame, [25, 45], [0, 1], {
    extrapolateRight: "clamp",
  });
  const titleY = interpolate(frame, [25, 45], [30, 0], {
    extrapolateRight: "clamp",
  });
  const subtitleOpacity = interpolate(frame, [50, 70], [0, 1], {
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(frame, [110, 135], [1, 0], {
    extrapolateLeft: "clamp",
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
        opacity: fadeOut,
      }}
    >
      {/* Logo mark */}
      <div
        style={{
          opacity: logoOpacity,
          transform: `scale(${logoScale})`,
          marginBottom: 48,
        }}
      >
        <BrandMark boxSize={140} borderRadius={32} />
      </div>

      {/* Title — uses the real brand logo layout */}
      <div
        style={{
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
        }}
      >
        <BrandLogo size="lg" variant="light" />
      </div>

      {/* Subtitle */}
      <p
        style={{
          opacity: subtitleOpacity,
          color: colors.light,
          fontSize: 28,
          marginTop: 16,
          fontWeight: 400,
        }}
      >
        Din komplette plattform for forsikringsmegling
      </p>
    </AbsoluteFill>
  );
};
