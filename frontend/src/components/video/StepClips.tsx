/**
 * Compact animated clips for each onboarding step.
 * Hybrid approach: real app screenshot as background + animated overlays.
 * Designed for 560x320 — small, focused, and readable at modal size.
 */
import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, staticFile } from "remotion";
import { colors, fonts } from "./theme";
import { FadeIn, MockCard, MockMetric, RiskBadge } from "./Primitives";

/** Background: real app screenshot with a subtle zoom-in */
const AppBg: React.FC<{ src: string; children: React.ReactNode }> = ({
  src,
  children,
}) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 120], [1, 1.04], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ fontFamily: fonts.body, overflow: "hidden" }}>
      {/* Screenshot layer */}
      <Img
        src={staticFile(`demo/${src}`)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale})`,
          filter: "brightness(0.6)",
        }}
      />
      {/* Overlay content */}
      <AbsoluteFill
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 24,
        }}
      >
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* ── Clip 1: Search ─────────────────────────────────────────── */

export const Clip1Search: React.FC = () => {
  const frame = useCurrentFrame();
  const query = "DNB Bank ASA";
  const charsVisible = Math.floor(
    interpolate(frame, [5, 5 + query.length * 2], [0, query.length], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    })
  );
  const showCursor = frame > 5 && frame % 16 < 10;
  const showResult = interpolate(frame, [40, 50], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AppBg src="search.png">
      <div
        style={{
          width: "100%",
          maxWidth: 400,
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        <div
          style={{
            background: colors.white,
            border: `2px solid ${colors.mid}`,
            borderRadius: 8,
            padding: "10px 16px",
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 15,
            color: colors.dark,
            boxShadow: "0 4px 20px rgba(0,0,0,0.15)",
          }}
        >
          <span style={{ fontSize: 16, color: colors.muted }}>&#x1F50D;</span>
          <span>
            {query.slice(0, charsVisible)}
            {showCursor && (
              <span
                style={{
                  borderRight: `2px solid ${colors.mid}`,
                  marginLeft: 1,
                }}
              >
                &nbsp;
              </span>
            )}
          </span>
        </div>
        <div style={{ opacity: showResult }}>
          <MockCard style={{ padding: 16, boxShadow: "0 4px 20px rgba(0,0,0,0.15)" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: colors.dark }}>
                  DNB Bank ASA
                </div>
                <div style={{ fontSize: 12, color: colors.muted, marginTop: 2 }}>
                  Org.nr 984 851 006 · Oslo
                </div>
              </div>
              <RiskBadge level="low" label="Lav risiko" />
            </div>
            <FadeIn delay={55} duration={12}>
              <div
                style={{
                  display: "flex",
                  gap: 20,
                  marginTop: 12,
                  paddingTop: 10,
                  borderTop: `1px solid ${colors.stone}`,
                }}
              >
                {[
                  { l: "Omsetning", v: "24,3 mrd" },
                  { l: "Ansatte", v: "9 220" },
                  { l: "Risiko", v: "3/20" },
                ].map((m) => (
                  <div key={m.l} style={{ textAlign: "center", flex: 1 }}>
                    <div style={{ fontSize: 11, color: colors.muted }}>{m.l}</div>
                    <div
                      style={{
                        fontSize: 17,
                        fontWeight: 700,
                        color: colors.dark,
                        marginTop: 2,
                      }}
                    >
                      {m.v}
                    </div>
                  </div>
                ))}
              </div>
            </FadeIn>
          </MockCard>
        </div>
      </div>
    </AppBg>
  );
};

/* ── Clip 2: Dashboard ──────────────────────────────────────── */

export const Clip2Dashboard: React.FC = () => (
  <AppBg src="dashboard.png">
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 12,
        width: "100%",
        maxWidth: 340,
      }}
    >
      <FadeIn delay={5} duration={12}>
        <MockMetric label="Portefølje" value="kr 42M" color={colors.dark} />
      </FadeIn>
      <FadeIn delay={15} duration={12}>
        <MockMetric label="Fornyelser" value="12" color={colors.warning} />
      </FadeIn>
      <FadeIn delay={25} duration={12}>
        <MockMetric label="Pipeline" value="8" color={colors.mid} />
      </FadeIn>
      <FadeIn delay={35} duration={12}>
        <MockMetric label="Risikoscore" value="4.2" color={colors.success} />
      </FadeIn>
    </div>
  </AppBg>
);

/* ── Clip 3: Portfolio ──────────────────────────────────────── */

export const Clip3Portfolio: React.FC = () => {
  const frame = useCurrentFrame();
  const rows = [
    { name: "DNB Bank ASA", premium: "kr 1,2M", risk: "Lav" },
    { name: "Equinor ASA", premium: "kr 3,8M", risk: "Moderat" },
    { name: "Gjensidige ASA", premium: "kr 890k", risk: "Lav" },
  ];

  return (
    <AppBg src="portfolio.png">
      <MockCard style={{ width: "100%", maxWidth: 380, padding: 16, boxShadow: "0 4px 20px rgba(0,0,0,0.15)" }}>
        <div
          style={{
            fontSize: 14,
            fontWeight: 700,
            color: colors.dark,
            marginBottom: 10,
            paddingBottom: 8,
            borderBottom: `1px solid ${colors.stone}`,
          }}
        >
          Min portefølje
        </div>
        {rows.map((row, i) => {
          const show = interpolate(
            frame,
            [10 + i * 12, 22 + i * 12],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          const riskColor =
            row.risk === "Lav" ? colors.success : colors.warning;
          return (
            <div
              key={row.name}
              style={{
                opacity: show,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "8px 0",
                borderBottom:
                  i < rows.length - 1
                    ? `1px solid ${colors.stone}`
                    : undefined,
              }}
            >
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: colors.dark }}>
                  {row.name}
                </div>
                <div style={{ fontSize: 11, color: colors.muted }}>
                  {row.premium}
                </div>
              </div>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: riskColor,
                  padding: "2px 8px",
                  borderRadius: 10,
                  background: riskColor + "18",
                }}
              >
                {row.risk}
              </span>
            </div>
          );
        })}
      </MockCard>
    </AppBg>
  );
};

/* ── Clip 4: Insurance ──────────────────────────────────────── */

export const Clip4Insurance: React.FC = () => {
  const frame = useCurrentFrame();
  const policies = [
    {
      type: "Ansvarsforsikring",
      insurer: "If",
      expires: "15.08.2026",
      premium: "kr 245 000",
    },
    {
      type: "Eiendomsforsikring",
      insurer: "Gjensidige",
      expires: "01.11.2026",
      premium: "kr 180 000",
    },
  ];

  return (
    <AppBg src="renewals.png">
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 10,
          width: "100%",
          maxWidth: 380,
        }}
      >
        {policies.map((p, i) => {
          const show = interpolate(
            frame,
            [8 + i * 15, 22 + i * 15],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          return (
            <div key={p.type} style={{ opacity: show }}>
              <MockCard style={{ padding: 14, boxShadow: "0 4px 20px rgba(0,0,0,0.15)" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: colors.dark }}>
                      {p.type}
                    </div>
                    <div style={{ fontSize: 12, color: colors.muted, marginTop: 2 }}>
                      {p.insurer}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 15, fontWeight: 700, color: colors.dark }}>
                      {p.premium}
                    </div>
                    <div style={{ fontSize: 11, color: colors.warning, marginTop: 2 }}>
                      Utløper {p.expires}
                    </div>
                  </div>
                </div>
              </MockCard>
            </div>
          );
        })}
      </div>
    </AppBg>
  );
};

/* ── Clip 5: IDD ────────────────────────────────────────────── */

export const Clip5IDD: React.FC = () => {
  const frame = useCurrentFrame();
  const steps = [
    { label: "Behov", done: true },
    { label: "Anbefaling", done: true },
    { label: "Tilbud", done: false },
    { label: "Signering", done: false },
  ];

  return (
    <AppBg src="idd.png">
      <MockCard style={{ width: "100%", maxWidth: 360, padding: 16, boxShadow: "0 4px 20px rgba(0,0,0,0.15)" }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: colors.dark, marginBottom: 16 }}>
          IDD Arbeidsflyt
        </div>
        <div style={{ display: "flex", alignItems: "center" }}>
          {steps.map((s, i) => {
            const show = interpolate(
              frame,
              [8 + i * 10, 18 + i * 10],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            return (
              <React.Fragment key={s.label}>
                <div style={{ opacity: show, textAlign: "center", flex: 1 }}>
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: "50%",
                      background: s.done ? colors.success : colors.stone,
                      color: s.done ? colors.white : colors.muted,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      margin: "0 auto 6px",
                      fontSize: 13,
                      fontWeight: 700,
                    }}
                  >
                    {s.done ? "\u2713" : "\u25CB"}
                  </div>
                  <div style={{ fontSize: 10, color: colors.muted }}>
                    {s.label}
                  </div>
                </div>
                {i < steps.length - 1 && (
                  <div
                    style={{
                      flex: 0.4,
                      height: 2,
                      background: s.done ? colors.success : colors.stone,
                      marginBottom: 18,
                      opacity: show,
                    }}
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>
        <FadeIn delay={55} duration={12}>
          <div
            style={{
              marginTop: 16,
              padding: "8px 12px",
              background: colors.light + "40",
              borderRadius: 6,
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 12,
              color: colors.mid,
            }}
          >
            &#x1F512; Delt med klient via sikker portal
          </div>
        </FadeIn>
      </MockCard>
    </AppBg>
  );
};

/* ── Clip 6: AI Chat ────────────────────────────────────────── */

export const Clip6AI: React.FC = () => {
  const frame = useCurrentFrame();
  const messages = [
    { role: "user" as const, text: "Hva er DNBs risikoprofil?" },
    {
      role: "ai" as const,
      text: "DNB har lav risikoscore (3/20). Stabil omsetning på 24,3 mrd, positiv egenkapitalutvikling og ingen PEP-treff.",
    },
  ];

  return (
    <AppBg src="knowledge.png">
      <MockCard style={{ width: "100%", maxWidth: 380, padding: 16, boxShadow: "0 4px 20px rgba(0,0,0,0.15)" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {messages.map((msg, i) => {
            const show = interpolate(
              frame,
              [8 + i * 25, 22 + i * 25],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            const isUser = msg.role === "user";
            return (
              <div
                key={i}
                style={{
                  opacity: show,
                  alignSelf: isUser ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                  padding: "8px 14px",
                  borderRadius: isUser
                    ? "12px 12px 3px 12px"
                    : "12px 12px 12px 3px",
                  background: isUser ? colors.dark : colors.beige,
                  color: isUser ? colors.white : colors.dark,
                  fontSize: 13,
                  lineHeight: 1.5,
                }}
              >
                {msg.text}
              </div>
            );
          })}
        </div>
        <div
          style={{
            opacity: interpolate(frame, [60, 70], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            display: "flex",
            gap: 4,
            marginTop: 10,
            paddingLeft: 6,
          }}
        >
          {[0, 1, 2].map((dot) => (
            <div
              key={dot}
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: colors.muted,
                opacity: ((frame + dot * 5) % 20) < 10 ? 1 : 0.3,
              }}
            />
          ))}
        </div>
      </MockCard>
    </AppBg>
  );
};

/** Clip dimensions — compact, designed for modal embed */
export const CLIP_CONFIG = {
  width: 560,
  height: 320,
  fps: 30,
  durationInFrames: 120,
} as const;
