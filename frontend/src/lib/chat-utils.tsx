"use client";

import { useState, useEffect } from "react";
import { Scale } from "lucide-react";

export const THINKING_PHRASES = [
  "Tenker...",
  "Grubler...",
  "Analyserer...",
  "Vurderer...",
  "Undersøker...",
  "Resonnerer...",
  "Raffinerer...",
  "Formulerer...",
];

export function stripMarkdown(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/#{1,6}\s+/g, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/^\s*[-*+]\s+/gm, "• ")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function ThinkingIndicator() {
  const [idx, setIdx] = useState(0);
  const [key, setKey] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setIdx((i) => (i + 1) % THINKING_PHRASES.length);
      setKey((k) => k + 1);
    }, 2200);
    return () => clearInterval(timer);
  }, []);

  const phrase = THINKING_PHRASES[idx];

  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2 px-1 py-2">
        <Scale className="w-5 h-5 text-brand-mid animate-thinking flex-shrink-0" />
        <span className="text-sm text-foreground/70 italic font-medium">
          {phrase.split("").map((char, i) => (
            <span
              key={`${key}-${i}`}
              className="thinking-char"
              style={{ animationDelay: `${i * 45}ms` }}
            >
              {char}
            </span>
          ))}
        </span>
      </div>
    </div>
  );
}

export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (mins < 2) return "akkurat nå";
  if (mins < 60) return `${mins} min siden`;
  if (hours < 24) return `${hours}t siden`;
  if (days === 1) return "i går";
  return `${days} dager siden`;
}
