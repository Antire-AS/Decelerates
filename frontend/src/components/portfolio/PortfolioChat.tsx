"use client";

import Link from "next/link";
import { Loader2, MessageSquare } from "lucide-react";
import { useT } from "@/lib/i18n";

interface Props {
  chatQuestion: string;
  setChatQuestion: (q: string) => void;
  chatAnswer: string | null;
  chatSources: string[];
  chatLoading: boolean;
  chatErr: string | null;
  onSubmit: () => void;
}

export function PortfolioChat({
  chatQuestion,
  setChatQuestion,
  chatAnswer,
  chatSources,
  chatLoading,
  chatErr,
  onSubmit,
}: Props) {
  const T = useT();
  return (
    <div className="space-y-3 pt-2 border-t border-border">
      <p className="text-xs font-semibold text-foreground flex items-center gap-1.5">
        <MessageSquare className="w-3.5 h-3.5" /> {T("Portefølje-chat")}
      </p>
      <div className="flex gap-2">
        <input
          type="text"
          value={chatQuestion}
          onChange={(e) => setChatQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSubmit()}
          placeholder={T("F.eks. «Hvilke selskaper har lavest egenkapitalandel?»")}
          className="flex-1 px-3 py-2 text-sm border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
        />
        <button
          onClick={onSubmit}
          disabled={chatLoading || !chatQuestion.trim()}
          className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1">
          {chatLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <MessageSquare className="w-4 h-4" />}
          {T("Spør")}
        </button>
      </div>
      {chatErr && <p className="text-xs text-red-600">{chatErr}</p>}
      {chatAnswer && (
        <div className="bg-muted rounded-lg p-3 space-y-2">
          <p className="text-xs text-foreground whitespace-pre-wrap">{chatAnswer}</p>
          {chatSources.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1">
              {chatSources.map((s) => (
                <Link key={s} href={`/search/${s}`}
                  className="text-xs px-2 py-0.5 rounded-full bg-muted text-primary hover:underline">{s}</Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
