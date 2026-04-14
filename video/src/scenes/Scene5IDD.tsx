import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { SceneLayout } from "../components/SceneLayout";
import { MockCard } from "../components/MockCard";
import { FadeIn } from "../components/FadeIn";
import { colors } from "../theme";

/** Scene 5: IDD compliance + client portal sharing */
export const Scene5IDD: React.FC = () => {
  const frame = useCurrentFrame();

  const steps = [
    { label: "Behovsanalyse", done: true },
    { label: "Anbefalinger", done: true },
    { label: "Tilbud", done: false },
    { label: "Signering", done: false },
  ];

  return (
    <SceneLayout
      step={5}
      totalSteps={6}
      icon="&#x1F4C4;"
      title="IDD og klientdeling"
      body="Lag behovsanalyser etter forsikringsformidlingsloven. Del en skrivebeskyttet portal med klienten."
    >
      <MockCard style={{ width: "100%", maxWidth: 420 }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: colors.dark, marginBottom: 20 }}>
          IDD Arbeidsflyt
        </div>
        <div style={{ display: "flex", gap: 0, alignItems: "center" }}>
          {steps.map((s, i) => {
            const show = interpolate(frame, [30 + i * 12, 42 + i * 12], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            return (
              <React.Fragment key={s.label}>
                <div style={{ opacity: show, textAlign: "center", flex: 1 }}>
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: "50%",
                      background: s.done ? colors.success : colors.stone,
                      color: s.done ? colors.white : colors.muted,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      margin: "0 auto 8px",
                      fontSize: 16,
                      fontWeight: 700,
                    }}
                  >
                    {s.done ? "\u2713" : "\u25CB"}
                  </div>
                  <div style={{ fontSize: 12, color: colors.muted }}>{s.label}</div>
                </div>
                {i < steps.length - 1 && (
                  <div
                    style={{
                      flex: 0.5,
                      height: 2,
                      background: s.done ? colors.success : colors.stone,
                      marginBottom: 22,
                      opacity: show,
                    }}
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>

        <FadeIn delay={80} duration={15}>
          <div
            style={{
              marginTop: 24,
              padding: "12px 16px",
              background: colors.light + "40",
              borderRadius: 8,
              display: "flex",
              alignItems: "center",
              gap: 10,
              fontSize: 14,
              color: colors.mid,
            }}
          >
            <span style={{ fontSize: 18 }}>&#x1F517;</span>
            Delt med klient via sikker portal
          </div>
        </FadeIn>
      </MockCard>
    </SceneLayout>
  );
};
