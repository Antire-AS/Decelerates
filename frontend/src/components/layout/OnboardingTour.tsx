"use client";

import { useEffect, useState } from "react";
import { Player } from "@remotion/player";
import { X, ArrowRight, ArrowLeft, CheckCircle, Maximize2 } from "lucide-react";
import {
  Clip1Search,
  Clip2Dashboard,
  Clip3Portfolio,
  Clip4Insurance,
  Clip5IDD,
  Clip6AI,
  CLIP_CONFIG,
} from "../video/StepClips";
import {
  DemoVideo,
  DEMO_VIDEO_CONFIG,
} from "../video/DemoComposition";

const STEPS = [
  {
    title: "Søk opp et selskap",
    body: "Skriv inn et firmanavn eller organisasjonsnummer. Data hentes automatisk fra BRREG, regnskapsregisteret og risikoscore beregnes.",
    clip: Clip1Search,
  },
  {
    title: "Dashbordet ditt",
    body: "Dashbordet viser dine viktigste KPI-er: porteføljerisiko, fornyelser de neste 90 dagene, og kommende oppgaver.",
    clip: Clip2Dashboard,
  },
  {
    title: "Bygg en portefølje",
    body: "Gå til Portefølje, opprett en ny portefølje og legg til selskaper. Du får konsentrasjonsanalyse, kart og fornyelsesvarsel.",
    clip: Clip3Portfolio,
  },
  {
    title: "Administrer forsikringsavtaler",
    body: "Under CRM-fanen kan du registrere poliser med provisjonssats, skader, kontaktpersoner og aktiviteter. Fornyelser-siden gir deg en pipeline.",
    clip: Clip4Insurance,
  },
  {
    title: "IDD og klientdeling",
    body: "Bruk IDD / Behov i menyen for å lage behovsanalyser (forsikringsformidlingsloven § 7). Del en skrivebeskyttet portal med klienten.",
    clip: Clip5IDD,
  },
  {
    title: "AI-assistenten og kunnskapsbase",
    body: "Bruk Chat-fanen på et selskap for å stille spørsmål om økonomi og risiko. Kunnskapsbasen lar deg chatte med opplastede dokumenter og videoer.",
    clip: Clip6AI,
  },
];

const STORAGE_KEY = "ba_onboarding_seen";

export default function OnboardingTour() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [fullVideo, setFullVideo] = useState(false);

  useEffect(() => {
    if (typeof localStorage !== "undefined" && !localStorage.getItem(STORAGE_KEY)) {
      setOpen(true);
    }
  }, []);

  function close() {
    setOpen(false);
    setFullVideo(false);
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(STORAGE_KEY, "1");
    }
  }

  useEffect(() => {
    const reopen = () => {
      setStep(0);
      setFullVideo(false);
      setOpen(true);
    };
    (window as unknown as Record<string, unknown>).__openOnboarding = reopen;
    return () => {
      delete (window as unknown as Record<string, unknown>).__openOnboarding;
    };
  }, []);

  useEffect(() => {
    const openFull = () => {
      setStep(0);
      setFullVideo(true);
      setOpen(true);
    };
    (window as unknown as Record<string, unknown>).__openDemoVideo = openFull;
    return () => {
      delete (window as unknown as Record<string, unknown>).__openDemoVideo;
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!open) return null;

  /* ── Full video mode ─────────────────────────────────────── */
  if (fullVideo) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-6">
        <div className="relative w-full max-w-5xl">
          <div className="flex items-center justify-between mb-3">
            <button
              onClick={() => setFullVideo(false)}
              className="text-white/60 hover:text-white text-sm flex items-center gap-1.5"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Tilbake til steg-for-steg
            </button>
            <button onClick={close} className="text-white/60 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="rounded-xl overflow-hidden shadow-2xl bg-primary">
            <Player
              component={DemoVideo}
              durationInFrames={DEMO_VIDEO_CONFIG.durationInFrames}
              compositionWidth={DEMO_VIDEO_CONFIG.width}
              compositionHeight={DEMO_VIDEO_CONFIG.height}
              fps={DEMO_VIDEO_CONFIG.fps}
              style={{ width: "100%", aspectRatio: "16/9" }}
              controls
              autoPlay
              loop
            />
          </div>
          <p className="text-center text-white/40 text-xs mt-3">
            Komplett demo · 40 sekunder
          </p>
        </div>
      </div>
    );
  }

  /* ── Step-by-step mode with inline clips ─────────────────── */
  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;
  const ClipComponent = current.clip;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
        {/* Header */}
        <div className="bg-primary px-6 py-3 flex items-center justify-between">
          <p className="text-xs font-medium text-white/60 uppercase tracking-wide">
            Veiledning · Steg {step + 1} av {STEPS.length}
          </p>
          <button onClick={close} className="text-white/50 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Progress bar */}
        <div className="h-1 bg-muted">
          <div
            className="h-full bg-primary transition-all duration-300"
            style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
          />
        </div>

        {/* Inline video clip — compact, purpose-built for this size */}
        <div className="relative">
          <Player
            key={step}
            component={ClipComponent}
            durationInFrames={CLIP_CONFIG.durationInFrames}
            compositionWidth={CLIP_CONFIG.width}
            compositionHeight={CLIP_CONFIG.height}
            fps={CLIP_CONFIG.fps}
            style={{ width: "100%" }}
            autoPlay
            loop
          />
          <button
            onClick={() => setFullVideo(true)}
            className="absolute bottom-2 right-2 p-1.5 rounded-md bg-black/20 text-white/60 hover:text-white hover:bg-black/40 transition-colors"
            title="Se hele videoen"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Text content */}
        <div className="px-6 py-4">
          <h2 className="text-lg font-bold text-foreground mb-1.5">{current.title}</h2>
          <p className="text-sm text-muted-foreground leading-relaxed">{current.body}</p>
        </div>

        {/* Footer */}
        <div className="px-6 pb-5 flex items-center justify-between gap-3">
          <button
            onClick={() => setStep((s) => s - 1)}
            disabled={step === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground disabled:opacity-0"
          >
            <ArrowLeft className="w-4 h-4" />
            Forrige
          </button>

          <div className="flex gap-1.5">
            {STEPS.map((_, i) => (
              <button key={i} onClick={() => setStep(i)}
                className={`w-2 h-2 rounded-full transition-colors ${
                  i === step ? "bg-primary" : "bg-muted hover:bg-brand-warning"
                }`} />
            ))}
          </div>

          {isLast ? (
            <button
              onClick={close}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/80"
            >
              <CheckCircle className="w-4 h-4" />
              Fullfør
            </button>
          ) : (
            <button
              onClick={() => setStep((s) => s + 1)}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/80"
            >
              Neste
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
