import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { SceneLayout } from "../components/SceneLayout";
import { MockCard } from "../components/MockCard";
import { colors } from "../theme";

/** Scene 6: AI assistant / knowledge base chat */
export const Scene6AI: React.FC = () => {
  const frame = useCurrentFrame();

  const messages: Array<{ role: "user" | "ai"; text: string }> = [
    { role: "user", text: "Hva er DNBs risikoprofil?" },
    {
      role: "ai",
      text: "DNB Bank ASA har en lav risikoscore (3/20). Selskapet har stabil omsetning pa 24,3 mrd, positiv egenkapitalutvikling og ingen PEP-treff.",
    },
  ];

  return (
    <SceneLayout
      step={6}
      totalSteps={6}
      icon="&#x1F4AC;"
      title="AI-assistent"
      body="Still sporsmal om okonomi og risiko. Kunnskapsbasen lar deg chatte med opplastede dokumenter og videoer."
    >
      <MockCard style={{ width: "100%", maxWidth: 460 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {messages.map((msg, i) => {
            const show = interpolate(frame, [25 + i * 30, 45 + i * 30], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const isUser = msg.role === "user";
            return (
              <div
                key={i}
                style={{
                  opacity: show,
                  alignSelf: isUser ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                  padding: "12px 18px",
                  borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
                  background: isUser ? colors.dark : colors.beige,
                  color: isUser ? colors.white : colors.dark,
                  fontSize: 15,
                  lineHeight: 1.5,
                }}
              >
                {msg.text}
              </div>
            );
          })}
        </div>

        {/* Typing indicator */}
        <div
          style={{
            opacity: interpolate(frame, [90, 100], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            display: "flex",
            gap: 6,
            marginTop: 16,
            paddingLeft: 8,
          }}
        >
          {[0, 1, 2].map((dot) => (
            <div
              key={dot}
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: colors.muted,
                opacity: ((frame + dot * 5) % 20) < 10 ? 1 : 0.3,
              }}
            />
          ))}
        </div>
      </MockCard>
    </SceneLayout>
  );
};
