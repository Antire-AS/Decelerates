import React from "react";
import { SceneLayout } from "../components/SceneLayout";
import { MockMetric } from "../components/MockCard";
import { FadeIn } from "../components/FadeIn";
import { colors } from "../theme";

/** Scene 2: Dashboard overview with KPI cards */
export const Scene2Dashboard: React.FC = () => {
  return (
    <SceneLayout
      step={2}
      totalSteps={6}
      icon="&#x1F4CA;"
      title="Dashbordet ditt"
      body="Se dine viktigste KPI-er: portefoljepremie, fornyelser de neste 90 dagene, og kommende oppgaver."
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 20,
          width: "100%",
          maxWidth: 420,
        }}
      >
        <FadeIn delay={30} duration={15}>
          <MockMetric label="Portefolje" value="kr 42M" color={colors.dark} />
        </FadeIn>
        <FadeIn delay={40} duration={15}>
          <MockMetric label="Fornyelser" value="12" color={colors.warning} />
        </FadeIn>
        <FadeIn delay={50} duration={15}>
          <MockMetric label="Pipeline" value="8" color={colors.mid} />
        </FadeIn>
        <FadeIn delay={60} duration={15}>
          <MockMetric label="Risikoscore" value="4.2" color={colors.success} />
        </FadeIn>
      </div>
    </SceneLayout>
  );
};
