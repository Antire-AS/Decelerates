"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import translations from "@/../translations.json";

type Lang = "no" | "en";
type Translations = Record<string, { no?: string; en?: string }>;

const _t = translations as Translations;
const STORAGE_KEY = "app-lang";

interface I18nContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  T: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue>({
  lang: "no",
  setLang: () => undefined,
  T: (k) => k,
});

function loadInitial(): Lang {
  if (typeof window === "undefined") return "no";
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === "no" || raw === "en") return raw;
  } catch {
    /* ignored */
  }
  return "no";
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => loadInitial());

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignored */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const T = useCallback(
    (key: string): string => {
      const entry = _t[key];
      if (!entry) return key;
      return entry[lang] ?? entry.en ?? key;
    },
    [lang],
  );

  return (
    <I18nContext.Provider value={{ lang, setLang, T }}>
      {children}
    </I18nContext.Provider>
  );
}

export const useI18n = () => useContext(I18nContext);

/** Convenience — returns just the T function. */
export const useT = () => useContext(I18nContext).T;
