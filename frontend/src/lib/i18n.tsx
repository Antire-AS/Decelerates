"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import translations from "@/../translations.json";

type Lang = "no" | "en";
type Translations = Record<string, { no?: string; en?: string }>;

const _t = translations as Translations;

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

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("no");

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
