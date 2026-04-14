import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../theme";

export const ProgressBar: React.FC<{
  step: number;
  total: number;
}> = ({ step, total }) => {
  const frame = useCurrentFrame();
  const width = interpolate(frame, [0, 15], [0, (step / total) * 100], {
    extrapolateRight: "clamp",
  });

  return (
    <div style={{ height: 6, background: colors.stone, borderRadius: 3, overflow: "hidden" }}>
      <div
        style={{
          height: "100%",
          width: `${width}%`,
          background: colors.mid,
          borderRadius: 3,
        }}
      />
    </div>
  );
};
