import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { SceneLayout } from "../components/SceneLayout";
import { MockCard } from "../components/MockCard";
import { FadeIn } from "../components/FadeIn";
import { colors } from "../theme";

/** Scene 3: Portfolio building — shows a mini portfolio list */
export const Scene3Portfolio: React.FC = () => {
  const frame = useCurrentFrame();

  const rows = [
    { name: "DNB Bank ASA", premium: "kr 1,2M", risk: "Lav" },
    { name: "Equinor ASA", premium: "kr 3,8M", risk: "Moderat" },
    { name: "Gjensidige ASA", premium: "kr 890k", risk: "Lav" },
  ];

  return (
    <SceneLayout
      step={3}
      totalSteps={6}
      icon="&#x1F4C1;"
      title="Bygg en portefolje"
      body="Opprett portefoljer, legg til selskaper og fa konsentrasjonsanalyse, kart og fornyelsesvarsel."
    >
      <MockCard style={{ width: "100%", maxWidth: 480 }}>
        <div
          style={{
            fontSize: 16,
            fontWeight: 700,
            color: colors.dark,
            marginBottom: 16,
            paddingBottom: 12,
            borderBottom: `1px solid ${colors.stone}`,
          }}
        >
          Min portefolje
        </div>
        {rows.map((row, i) => {
          const show = interpolate(frame, [30 + i * 15, 45 + i * 15], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const riskColor =
            row.risk === "Lav" ? colors.success : row.risk === "Moderat" ? colors.warning : colors.danger;

          return (
            <div
              key={row.name}
              style={{
                opacity: show,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "12px 0",
                borderBottom: i < rows.length - 1 ? `1px solid ${colors.stone}` : undefined,
              }}
            >
              <div>
                <div style={{ fontSize: 16, fontWeight: 600, color: colors.dark }}>{row.name}</div>
                <div style={{ fontSize: 13, color: colors.muted }}>{row.premium}</div>
              </div>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: riskColor,
                  padding: "3px 10px",
                  borderRadius: 12,
                  background: riskColor + "18",
                }}
              >
                {row.risk}
              </span>
            </div>
          );
        })}
      </MockCard>
    </SceneLayout>
  );
};
