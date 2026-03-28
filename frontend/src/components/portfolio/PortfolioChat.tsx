"use client";

import Link from "next/link";
import { Loader2, MessageSquare } from "lucide-react";

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
  return (
    <div className="space-y-3 pt-2 border-t border-[#EDE8E3]">
      <p className="text-xs font-semibold text-[#2C3E50] flex items-center gap-1.5">
        <MessageSquare className="w-3.5 h-3.5" /> Portefølje-chat
      </p>
      <div className="flex gap-2">
        <input
          type="text"
          value={chatQuestion}
          onChange={(e) => setChatQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSubmit()}
          placeholder="F.eks. «Hvilke selskaper har lavest egenkapitalandel?»"
          className="flex-1 px-3 py-2 text-sm border border-[#EDE8E3] rounded-lg text-[#2C3E50] placeholder-[#C8BEB4] focus:outline-none focus:border-[#2C3E50]"
        />
        <button
          onClick={onSubmit}
          disabled={chatLoading || !chatQuestion.trim()}
          className="px-4 py-2 rounded-lg bg-[#4A6FA5] text-white text-sm font-medium hover:bg-[#3d5e8e] disabled:opacity-50 flex items-center gap-1">
          {chatLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <MessageSquare className="w-4 h-4" />}
          Spør
        </button>
      </div>
      {chatErr && <p className="text-xs text-red-600">{chatErr}</p>}
      {chatAnswer && (
        <div className="bg-[#F9F7F4] rounded-lg p-3 space-y-2">
          <p className="text-xs text-[#2C3E50] whitespace-pre-wrap">{chatAnswer}</p>
          {chatSources.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1">
              {chatSources.map((s) => (
                <Link key={s} href={`/search/${s}`}
                  className="text-xs px-2 py-0.5 rounded-full bg-[#EDE8E3] text-[#4A6FA5] hover:underline">{s}</Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
