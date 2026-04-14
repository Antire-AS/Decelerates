import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../theme";

/** Animated search bar that types out a query */
export const MockSearchBar: React.FC<{
  query?: string;
  delay?: number;
}> = ({ query = "DNB Bank ASA", delay = 20 }) => {
  const frame = useCurrentFrame();

  const charsVisible = Math.floor(
    interpolate(frame, [delay, delay + query.length * 3], [0, query.length], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    })
  );

  const showCursor = frame > delay && frame % 16 < 10;
  const typed = query.slice(0, charsVisible);

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
        {typed}
        {showCursor && (
          <span style={{ borderRight: `2px solid ${colors.mid}`, marginLeft: 1 }}>
            &nbsp;
          </span>
        )}
      </span>
    </div>
  );
};
