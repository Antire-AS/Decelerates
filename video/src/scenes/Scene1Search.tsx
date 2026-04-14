import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { SceneLayout } from "../components/SceneLayout";
import { MockSearchBar } from "../components/MockSearchBar";
import { MockCard, RiskBadge } from "../components/MockCard";
import { FadeIn } from "../components/FadeIn";
import { colors } from "../theme";

/** Scene 1: Company search — shows search bar typing + result card */
export const Scene1Search: React.FC = () => {
  const frame = useCurrentFrame();
  const showResult = interpolate(frame, [75, 80], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <SceneLayout
      step={1}
      totalSteps={6}
      icon="&#x1F50D;"
      title="Sok opp et selskap"
      body="Skriv inn et firmanavn eller organisasjonsnummer. Data hentes automatisk fra BRREG, og risikoscore beregnes i sanntid."
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 24, width: "100%" }}>
        <MockSearchBar query="DNB Bank ASA" delay={20} />

        {/* Search result card */}
        <div style={{ opacity: showResult }}>
          <MockCard>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 22, fontWeight: 700, color: colors.dark }}>
                  DNB Bank ASA
                </div>
                <div style={{ fontSize: 14, color: colors.muted, marginTop: 4 }}>
                  Org.nr 984 851 006 &middot; Oslo
                </div>
              </div>
              <RiskBadge level="low" label="Lav risiko" />
            </div>
            <FadeIn delay={85} duration={15}>
              <div
                style={{
                  display: "flex",
                  gap: 32,
                  marginTop: 20,
                  paddingTop: 16,
                  borderTop: `1px solid ${colors.stone}`,
                }}
              >
                {[
                  { label: "Omsetning", value: "24,3 mrd" },
                  { label: "Ansatte", value: "9 220" },
                  { label: "Risikoscore", value: "3/20" },
                ].map((m) => (
                  <div key={m.label} style={{ textAlign: "center", flex: 1 }}>
                    <div style={{ fontSize: 13, color: colors.muted }}>{m.label}</div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: colors.dark, marginTop: 4 }}>
                      {m.value}
                    </div>
                  </div>
                ))}
              </div>
            </FadeIn>
          </MockCard>
        </div>
      </div>
    </SceneLayout>
  );
};
