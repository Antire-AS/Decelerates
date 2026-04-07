"use client";

import { useEffect, useState } from "react";
import { X, ArrowRight, ArrowLeft, CheckCircle } from "lucide-react";

const STEPS = [
  {
    icon: "🔍",
    title: "Søk opp et selskap",
    body: "Gå til Selskapsøk og skriv inn et firmanavn eller organisasjonsnummer. Data hentes automatisk fra BRREG, regnskapsregisteret og risikoscore beregnes.",
  },
  {
    icon: "📊",
    title: "Se risikoprofilen",
    body: "Under Oversikt ser du risikoscore, nøkkeltall og styremedlemmer. Under Økonomi finner du historiske regnskapstall, equity ratio-trend og AI-generert finanskommentar.",
  },
  {
    icon: "📁",
    title: "Bygg en portefølje",
    body: "Gå til Portefølje, opprett en ny portefølje og legg til selskaper. Du får konsentrasjonsanalyse, kart over alle kunder og fornyelsesvarsel.",
  },
  {
    icon: "📋",
    title: "Administrer forsikringsavtaler",
    body: "Under CRM-fanen på hvert selskap kan du registrere poliser med provisjonssats, skader, kontaktpersoner og aktiviteter. Fornyelser-siden gir deg en pipeline.",
  },
  {
    icon: "📄",
    title: "IDD og klientdeling",
    body: "Bruk IDD / Behov i menyen for å lage behovsanalyser (forsikringsformidlingsloven § 7). Del en skrivebeskyttet portal med klienten via Del med klient i CRM-fanen.",
  },
  {
    icon: "💬",
    title: "AI-assistenten og kunnskapsbase",
    body: "Bruk Chat-fanen på et selskap for å stille spørsmål om økonomi og risiko. Kunnskapsbase-siden lar deg chatte med opplastede dokumenter og videoer.",
  },
];

const STORAGE_KEY = "ba_onboarding_seen";

export default function OnboardingTour() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (typeof localStorage !== "undefined" && !localStorage.getItem(STORAGE_KEY)) {
      setOpen(true);
    }
  }, []);

  function close() {
    setOpen(false);
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(STORAGE_KEY, "1");
    }
  }

  // Expose reopen via a global so AppShell can call it. Must be a stable
  // reference (not a fresh closure) so old window.__openOnboarding handles
  // captured by other components keep working even after re-renders.
  useEffect(() => {
    const reopen = () => {
      setStep(0);
      setOpen(true);
    };
    (window as unknown as Record<string, unknown>).__openOnboarding = reopen;
    return () => {
      delete (window as unknown as Record<string, unknown>).__openOnboarding;
    };
  }, []);

  if (!open) return null;

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
        {/* Header */}
        <div className="bg-[#2C3E50] px-6 py-4 flex items-center justify-between">
          <p className="text-xs font-medium text-white/60 uppercase tracking-wide">
            Veiledning · Steg {step + 1} av {STEPS.length}
          </p>
          <button onClick={close} className="text-white/50 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Progress bar */}
        <div className="h-1 bg-[#EDE8E3]">
          <div
            className="h-full bg-[#4A6FA5] transition-all duration-300"
            style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
          />
        </div>

        {/* Content */}
        <div className="px-6 py-6">
          <div className="text-4xl mb-4">{current.icon}</div>
          <h2 className="text-lg font-bold text-[#2C3E50] mb-2">{current.title}</h2>
          <p className="text-sm text-[#8A7F74] leading-relaxed">{current.body}</p>
        </div>

        {/* Footer */}
        <div className="px-6 pb-6 flex items-center justify-between gap-3">
          <button
            onClick={() => setStep((s) => s - 1)}
            disabled={step === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-[#8A7F74] hover:text-[#2C3E50] disabled:opacity-0"
          >
            <ArrowLeft className="w-4 h-4" />
            Forrige
          </button>

          <div className="flex gap-1.5">
            {STEPS.map((_, i) => (
              <button key={i} onClick={() => setStep(i)}
                className={`w-2 h-2 rounded-full transition-colors ${
                  i === step ? "bg-[#4A6FA5]" : "bg-[#EDE8E3] hover:bg-[#C8A951]"
                }`} />
            ))}
          </div>

          {isLast ? (
            <button
              onClick={close}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-[#2C3E50] text-white text-sm rounded-lg hover:bg-[#1a252f]"
            >
              <CheckCircle className="w-4 h-4" />
              Fullfør
            </button>
          ) : (
            <button
              onClick={() => setStep((s) => s + 1)}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-[#2C3E50] text-white text-sm rounded-lg hover:bg-[#1a252f]"
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
