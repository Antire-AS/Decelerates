import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

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

  return (
    <div style={{ opacity, transform, ...style }}>
      {children}
    </div>
  );
};
