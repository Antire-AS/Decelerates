"use client";

import { useCallback, useEffect, useState } from "react";
import { Player } from "@remotion/player";
import { X, Play, Pause, RotateCcw } from "lucide-react";
import { DemoVideo, DEMO_VIDEO_CONFIG } from "./DemoComposition";

export default function DemoVideoModal() {
  const [open, setOpen] = useState(false);

  const close = useCallback(() => setOpen(false), []);

  // Expose a global so AppShell / OnboardingTour can open it
  useEffect(() => {
    const openDemo = () => setOpen(true);
    (window as unknown as Record<string, unknown>).__openDemoVideo = openDemo;
    return () => {
      delete (window as unknown as Record<string, unknown>).__openDemoVideo;
    };
  }, []);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-6">
      <div className="relative w-full max-w-5xl">
        {/* Close button */}
        <button
          onClick={close}
          className="absolute -top-10 right-0 text-white/60 hover:text-white flex items-center gap-1.5 text-sm"
        >
          Lukk
          <X className="w-4 h-4" />
        </button>

        {/* Player */}
        <div className="rounded-xl overflow-hidden shadow-2xl bg-[#2C3E50]">
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
          40 sek demo &middot; Broker Accelerator veiledning
        </p>
      </div>
    </div>
  );
}
