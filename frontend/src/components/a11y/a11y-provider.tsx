"use client";

import * as React from "react";

type FontScale = "default" | "large" | "xlarge";

interface A11yState {
  fontScale: FontScale;
  reducedMotion: boolean;
  highContrast: boolean;
}

interface A11yContextValue extends A11yState {
  setFontScale: (v: FontScale) => void;
  setReducedMotion: (v: boolean) => void;
  setHighContrast: (v: boolean) => void;
}

const A11yContext = React.createContext<A11yContextValue | null>(null);

const STORAGE_KEY = "a11y-prefs";

function loadInitial(): A11yState {
  if (typeof window === "undefined") {
    return { fontScale: "default", reducedMotion: false, highContrast: false };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { fontScale: "default", reducedMotion: false, highContrast: false };
    const parsed = JSON.parse(raw) as Partial<A11yState>;
    return {
      fontScale: parsed.fontScale ?? "default",
      reducedMotion: parsed.reducedMotion ?? false,
      highContrast: parsed.highContrast ?? false,
    };
  } catch {
    return { fontScale: "default", reducedMotion: false, highContrast: false };
  }
}

export function A11yProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<A11yState>(() => loadInitial());

  // Sync to <html> attributes
  React.useEffect(() => {
    const root = document.documentElement;
    if (state.fontScale === "default") root.removeAttribute("data-font-scale");
    else root.setAttribute("data-font-scale", state.fontScale);

    if (state.reducedMotion) root.setAttribute("data-reduced-motion", "true");
    else root.removeAttribute("data-reduced-motion");

    if (state.highContrast) root.setAttribute("data-high-contrast", "true");
    else root.removeAttribute("data-high-contrast");
  }, [state]);

  // Persist
  React.useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // localStorage disabled — ignore
    }
  }, [state]);

  const value: A11yContextValue = {
    ...state,
    setFontScale: (fontScale) => setState((s) => ({ ...s, fontScale })),
    setReducedMotion: (reducedMotion) => setState((s) => ({ ...s, reducedMotion })),
    setHighContrast: (highContrast) => setState((s) => ({ ...s, highContrast })),
  };

  return <A11yContext.Provider value={value}>{children}</A11yContext.Provider>;
}

export function useA11y() {
  const ctx = React.useContext(A11yContext);
  if (!ctx) {
    throw new Error("useA11y must be used inside an A11yProvider");
  }
  return ctx;
}
