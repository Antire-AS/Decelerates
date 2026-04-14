import React from "react";
import { AbsoluteFill, interpolate, Series, useCurrentFrame } from "remotion";
import { colors, fonts, VIDEO } from "./theme";
import {
  BrandMark,
  BrandLogo,
  FadeIn,
  MockCard,
  MockMetric,
  MockSearchBar,
  RiskBadge,
  SceneLayout,
} from "./Primitives";

export const SCENE_FRAMES = VIDEO.fps * VIDEO.sceneDuration;

/* ── Intro ──────────────────────────────────────────────────── */

export const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const logoScale = interpolate(frame, [0, 30], [0.6, 1], { extrapolateRight: "clamp" });
  const logoOpacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
  const titleOpacity = interpolate(frame, [25, 45], [0, 1], { extrapolateRight: "clamp" });
  const titleY = interpolate(frame, [25, 45], [30, 0], { extrapolateRight: "clamp" });
  const subtitleOpacity = interpolate(frame, [50, 70], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [110, 135], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ background: colors.dark, fontFamily: fonts.body, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", opacity: fadeOut }}>
      <div style={{ opacity: logoOpacity, transform: `scale(${logoScale})`, marginBottom: 48 }}>
        <BrandMark boxSize={140} borderRadius={32} />
      </div>
      <div style={{ opacity: titleOpacity, transform: `translateY(${titleY}px)` }}>
        <BrandLogo size="lg" variant="light" />
      </div>
      <p style={{ opacity: subtitleOpacity, color: colors.light, fontSize: 28, marginTop: 16 }}>
        Din komplette plattform for forsikringsmegling
      </p>
    </AbsoluteFill>
  );
};

/* ── Scene 1: Search ────────────────────────────────────────── */

export const Scene1Search: React.FC = () => {
  const frame = useCurrentFrame();
  const showResult = interpolate(frame, [75, 80], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <SceneLayout step={1} totalSteps={6} icon="&#x1F50D;" title="Søk opp et selskap" body="Skriv inn et firmanavn eller organisasjonsnummer. Data hentes automatisk fra BRREG, og risikoscore beregnes i sanntid.">
      <div style={{ display: "flex", flexDirection: "column", gap: 24, width: "100%" }}>
        <MockSearchBar query="DNB Bank ASA" delay={20} />
        <div style={{ opacity: showResult }}>
          <MockCard>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 22, fontWeight: 700, color: colors.dark }}>DNB Bank ASA</div>
                <div style={{ fontSize: 14, color: colors.muted, marginTop: 4 }}>Org.nr 984 851 006 &middot; Oslo</div>
              </div>
              <RiskBadge level="low" label="Lav risiko" />
            </div>
            <FadeIn delay={85} duration={15}>
              <div style={{ display: "flex", gap: 32, marginTop: 20, paddingTop: 16, borderTop: `1px solid ${colors.stone}` }}>
                {[{ label: "Omsetning", value: "24,3 mrd" }, { label: "Ansatte", value: "9 220" }, { label: "Risikoscore", value: "3/20" }].map((m) => (
                  <div key={m.label} style={{ textAlign: "center", flex: 1 }}>
                    <div style={{ fontSize: 13, color: colors.muted }}>{m.label}</div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: colors.dark, marginTop: 4 }}>{m.value}</div>
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

/* ── Scene 2: Dashboard ─────────────────────────────────────── */

export const Scene2Dashboard: React.FC = () => (
  <SceneLayout step={2} totalSteps={6} icon="&#x1F4CA;" title="Dashbordet ditt" body="Se dine viktigste KPI-er: porteføljepremie, fornyelser de neste 90 dagene, og kommende oppgaver.">
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, width: "100%", maxWidth: 420 }}>
      <FadeIn delay={30} duration={15}><MockMetric label="Portefølje" value="kr 42M" color={colors.dark} /></FadeIn>
      <FadeIn delay={40} duration={15}><MockMetric label="Fornyelser" value="12" color={colors.warning} /></FadeIn>
      <FadeIn delay={50} duration={15}><MockMetric label="Pipeline" value="8" color={colors.mid} /></FadeIn>
      <FadeIn delay={60} duration={15}><MockMetric label="Risikoscore" value="4.2" color={colors.success} /></FadeIn>
    </div>
  </SceneLayout>
);

/* ── Scene 3: Portfolio ─────────────────────────────────────── */

export const Scene3Portfolio: React.FC = () => {
  const frame = useCurrentFrame();
  const rows = [
    { name: "DNB Bank ASA", premium: "kr 1,2M", risk: "Lav" },
    { name: "Equinor ASA", premium: "kr 3,8M", risk: "Moderat" },
    { name: "Gjensidige ASA", premium: "kr 890k", risk: "Lav" },
  ];

  return (
    <SceneLayout step={3} totalSteps={6} icon="&#x1F4C1;" title="Bygg en portefølje" body="Opprett porteføljer, legg til selskaper og få konsentrasjonsanalyse, kart og fornyelsesvarsel.">
      <MockCard style={{ width: "100%", maxWidth: 480 }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: colors.dark, marginBottom: 16, paddingBottom: 12, borderBottom: `1px solid ${colors.stone}` }}>Min portefølje</div>
        {rows.map((row, i) => {
          const show = interpolate(frame, [30 + i * 15, 45 + i * 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const riskColor = row.risk === "Lav" ? colors.success : colors.warning;
          return (
            <div key={row.name} style={{ opacity: show, display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0", borderBottom: i < rows.length - 1 ? `1px solid ${colors.stone}` : undefined }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 600, color: colors.dark }}>{row.name}</div>
                <div style={{ fontSize: 13, color: colors.muted }}>{row.premium}</div>
              </div>
              <span style={{ fontSize: 13, fontWeight: 600, color: riskColor, padding: "3px 10px", borderRadius: 12, background: riskColor + "18" }}>{row.risk}</span>
            </div>
          );
        })}
      </MockCard>
    </SceneLayout>
  );
};

/* ── Scene 4: Insurance ─────────────────────────────────────── */

export const Scene4Insurance: React.FC = () => {
  const frame = useCurrentFrame();
  const policies = [
    { type: "Ansvarsforsikring", insurer: "If", expires: "15.08.2026", premium: "kr 245 000" },
    { type: "Eiendomsforsikring", insurer: "Gjensidige", expires: "01.11.2026", premium: "kr 180 000" },
  ];

  return (
    <SceneLayout step={4} totalSteps={6} icon="&#x1F4CB;" title="Administrer avtaler" body="Registrer poliser, provisjoner, skader og kontaktpersoner. Fornyelser-siden gir deg en oversiktlig pipeline.">
      <div style={{ display: "flex", flexDirection: "column", gap: 16, width: "100%", maxWidth: 480 }}>
        {policies.map((p, i) => {
          const show = interpolate(frame, [25 + i * 20, 45 + i * 20], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
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
                    <div style={{ fontSize: 13, color: colors.warning, marginTop: 4 }}>Utløper {p.expires}</div>
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

/* ── Scene 5: IDD ───────────────────────────────────────────── */

export const Scene5IDD: React.FC = () => {
  const frame = useCurrentFrame();
  const steps = [
    { label: "Behovsanalyse", done: true },
    { label: "Anbefalinger", done: true },
    { label: "Tilbud", done: false },
    { label: "Signering", done: false },
  ];

  return (
    <SceneLayout step={5} totalSteps={6} icon="&#x1F4C4;" title="IDD og klientdeling" body="Lag behovsanalyser etter forsikringsformidlingsloven. Del en skrivebeskyttet portal med klienten.">
      <MockCard style={{ width: "100%", maxWidth: 420 }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: colors.dark, marginBottom: 20 }}>IDD Arbeidsflyt</div>
        <div style={{ display: "flex", gap: 0, alignItems: "center" }}>
          {steps.map((s, i) => {
            const show = interpolate(frame, [30 + i * 12, 42 + i * 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <React.Fragment key={s.label}>
                <div style={{ opacity: show, textAlign: "center", flex: 1 }}>
                  <div style={{ width: 36, height: 36, borderRadius: "50%", background: s.done ? colors.success : colors.stone, color: s.done ? colors.white : colors.muted, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 8px", fontSize: 16, fontWeight: 700 }}>
                    {s.done ? "\u2713" : "\u25CB"}
                  </div>
                  <div style={{ fontSize: 12, color: colors.muted }}>{s.label}</div>
                </div>
                {i < steps.length - 1 && (
                  <div style={{ flex: 0.5, height: 2, background: s.done ? colors.success : colors.stone, marginBottom: 22, opacity: show }} />
                )}
              </React.Fragment>
            );
          })}
        </div>
        <FadeIn delay={80} duration={15}>
          <div style={{ marginTop: 24, padding: "12px 16px", background: colors.light + "40", borderRadius: 8, display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: colors.mid }}>
            <span style={{ fontSize: 18 }}>&#x1F517;</span>
            Delt med klient via sikker portal
          </div>
        </FadeIn>
      </MockCard>
    </SceneLayout>
  );
};

/* ── Scene 6: AI ────────────────────────────────────────────── */

export const Scene6AI: React.FC = () => {
  const frame = useCurrentFrame();
  const messages = [
    { role: "user" as const, text: "Hva er DNBs risikoprofil?" },
    { role: "ai" as const, text: "DNB Bank ASA har en lav risikoscore (3/20). Selskapet har stabil omsetning på 24,3 mrd, positiv egenkapitalutvikling og ingen PEP-treff." },
  ];

  return (
    <SceneLayout step={6} totalSteps={6} icon="&#x1F4AC;" title="AI-assistent" body="Still spørsmål om økonomi og risiko. Kunnskapsbasen lar deg chatte med opplastede dokumenter og videoer.">
      <MockCard style={{ width: "100%", maxWidth: 460 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {messages.map((msg, i) => {
            const show = interpolate(frame, [25 + i * 30, 45 + i * 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const isUser = msg.role === "user";
            return (
              <div key={i} style={{ opacity: show, alignSelf: isUser ? "flex-end" : "flex-start", maxWidth: "85%", padding: "12px 18px", borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px", background: isUser ? colors.dark : colors.beige, color: isUser ? colors.white : colors.dark, fontSize: 15, lineHeight: 1.5 }}>
                {msg.text}
              </div>
            );
          })}
        </div>
        <div style={{ opacity: interpolate(frame, [90, 100], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }), display: "flex", gap: 6, marginTop: 16, paddingLeft: 8 }}>
          {[0, 1, 2].map((dot) => (
            <div key={dot} style={{ width: 8, height: 8, borderRadius: "50%", background: colors.muted, opacity: ((frame + dot * 5) % 20) < 10 ? 1 : 0.3 }} />
          ))}
        </div>
      </MockCard>
    </SceneLayout>
  );
};

/* ── Outro ──────────────────────────────────────────────────── */

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 25], [0, 1], { extrapolateRight: "clamp" });
  const scaleY = interpolate(frame, [20, 50], [20, 0], { extrapolateRight: "clamp" });
  const ctaOpacity = interpolate(frame, [50, 70], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ background: colors.dark, fontFamily: fonts.body, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", opacity }}>
      <div style={{ marginBottom: 32 }}><BrandMark boxSize={100} borderRadius={20} /></div>
      <h1 style={{ color: colors.white, fontSize: 52, fontWeight: 700, margin: 0, transform: `translateY(${scaleY}px)` }}>Klar til å komme i gang?</h1>
      <div style={{ opacity: ctaOpacity, marginTop: 32, padding: "16px 48px", borderRadius: 12, background: colors.mid, color: colors.white, fontSize: 24, fontWeight: 600 }}>meglerai.no</div>
      <p style={{ opacity: ctaOpacity, color: colors.light, fontSize: 18, marginTop: 24 }}>Broker Accelerator &mdash; forsikringsmegling, akselerert.</p>
    </AbsoluteFill>
  );
};

/* ── Full composition ───────────────────────────────────────── */

export const DemoVideo: React.FC = () => (
  <Series>
    <Series.Sequence durationInFrames={SCENE_FRAMES}><Intro /></Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}><Scene1Search /></Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}><Scene2Dashboard /></Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}><Scene3Portfolio /></Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}><Scene4Insurance /></Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}><Scene5IDD /></Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}><Scene6AI /></Series.Sequence>
    <Series.Sequence durationInFrames={SCENE_FRAMES}><Outro /></Series.Sequence>
  </Series>
);

export const DEMO_VIDEO_CONFIG = {
  durationInFrames: SCENE_FRAMES * 8,
  fps: VIDEO.fps,
  width: VIDEO.width,
  height: VIDEO.height,
} as const;
