"use client";

import { useState } from "react";
import { Scale, X } from "lucide-react";
import TenderChatPanel from "@/components/tenders/TenderChatPanel";

export default function GlobalChatButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Floating trigger button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 flex items-center justify-center transition-all hover:scale-105"
          title="AI-assistent"
        >
          <Scale className="w-5 h-5" />
        </button>
      )}

      {/* Drawer overlay */}
      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[1px]"
            onClick={() => setOpen(false)}
          />
          <div className="fixed bottom-0 right-0 z-50 h-full w-96 max-w-[95vw] flex flex-col shadow-2xl">
            <div className="flex items-center justify-between px-4 py-3 bg-primary text-primary-foreground">
              <div className="flex items-center gap-2">
                <Scale className="w-4 h-4" />
                <span className="font-semibold text-sm">AI-assistent</span>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="text-primary-foreground/70 hover:text-primary-foreground"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 overflow-hidden bg-background">
              <TenderChatPanel tenders={[]} />
            </div>
          </div>
        </>
      )}
    </>
  );
}
