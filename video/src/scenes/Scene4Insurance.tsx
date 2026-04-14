import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { SceneLayout } from "../components/SceneLayout";
import { MockCard } from "../components/MockCard";
import { colors } from "../theme";

/** Scene 4: Insurance management — policy cards + renewal timeline */
export const Scene4Insurance: React.FC = () => {
  const frame = useCurrentFrame();

  const policies = [
    { type: "Ansvarsforsikring", insurer: "If", expires: "15.08.2026", premium: "kr 245 000" },
    { type: "Eiendomsforsikring", insurer: "Gjensidige", expires: "01.11.2026", premium: "kr 180 000" },
  ];

  return (
    <SceneLayout
      step={4}
      totalSteps={6}
      icon="&#x1F4CB;"
      title="Administrer avtaler"
      body="Registrer poliser, provisjoner, skader og kontaktpersoner. Fornyelser-siden gir deg en oversiktlig pipeline."
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 16, width: "100%", maxWidth: 480 }}>
        {policies.map((p, i) => {
          const show = interpolate(frame, [25 + i * 20, 45 + i * 20], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <div key={p.type} style={{ opacity: show }}>
              <MockCard>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: colors.dark }}>{p.type}</div>
                    <div style={{ fontSize: 14, color: colors.muted, marginTop: 4 }}>{p.insurer}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: colors.dark }}>{p.premium}</div>
                    <div style={{ fontSize: 13, color: colors.warning, marginTop: 4 }}>
                      Utloper {p.expires}
                    </div>
                  </div>
                </div>
              </MockCard>
            </div>
          );
        })}
      </div>
    </SceneLayout>
  );
};
