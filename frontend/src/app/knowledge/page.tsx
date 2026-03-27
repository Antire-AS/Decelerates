"use client";

import { useState, useRef, useEffect } from "react";
import useSWR from "swr";
import { knowledgeChat, getKnowledgeStats } from "@/lib/api";
import { BookOpen, FileText, Video } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  source_snippets?: Record<string, string>;
}

function readableSource(src: string): string {
  if (src.startsWith("regulation::")) return src.replace("regulation::", "Regulering: ");
  if (src.startsWith("doc_")) return `Dokument ${src.replace("doc_", "")}`;
  if (src.startsWith("video_")) return `Video ${src.replace("video_", "")}`;
  return src;
}

export default function KnowledgePage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showStats, setShowStats] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: stats } = useSWR(
    showStats ? "knowledge-stats" : null,
    getKnowledgeStats,
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || isLoading) return;
    setQuestion("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setIsLoading(true);
    try {
      const res = await knowledgeChat(q);
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: res.answer,
        sources: res.sources,
        source_snippets: res.source_snippets,
      }]);
    } catch (err) {
      setError(`Kunne ikke hente svar: ${err instanceof Error ? err.message : "Ukjent feil"}`);
    } finally {
      setIsLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit(e as unknown as React.FormEvent);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#2C3E50]">Kunnskapsbase</h1>
          <p className="text-sm text-[#8A7F74] mt-1">Still spørsmål til AI-assistenten om forsikring, kunder og risiko</p>
        </div>
        <button onClick={() => setShowStats((s) => !s)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-[#D4C9B8] text-[#8A7F74] hover:bg-[#EDE8E3]">
          <BookOpen className="w-3.5 h-3.5" />
          {showStats ? "Skjul statistikk" : "Vis indeks-statistikk"}
        </button>
      </div>

      {/* Stats panel */}
      {showStats && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Totalt chunks", value: stats?.total_chunks, icon: <BookOpen className="w-4 h-4" /> },
            { label: "Dokumentchunks", value: stats?.doc_chunks,   icon: <FileText className="w-4 h-4" /> },
            { label: "Videochunks",    value: stats?.video_chunks,  icon: <Video className="w-4 h-4" /> },
          ].map(({ label, value, icon }) => (
            <div key={label} className="broker-card text-center">
              <div className="flex justify-center text-[#4A6FA5] mb-1">{icon}</div>
              <p className="text-xl font-bold text-[#2C3E50]">{value ?? "–"}</p>
              <p className="text-xs text-[#8A7F74]">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Chat window */}
      <div className="broker-card flex flex-col" style={{ minHeight: "60vh" }}>
        <div className="flex-1 space-y-4 overflow-y-auto mb-4" style={{ maxHeight: "55vh" }}>
          {messages.length === 0 && !isLoading && (
            <div className="text-center py-12 text-[#8A7F74]">
              <p className="text-sm font-medium text-[#2C3E50] mb-2">Hei! Jeg er din forsikringsassistent.</p>
              <p className="text-sm">Spør meg om forsikringstyper, risiko, kunderegulering, GDPR eller hvilken dekning et selskap trenger.</p>
              <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-2">
                {[
                  "Hva er ansvarsforsikring?",
                  "Hvilken forsikring trenger et byggefirma?",
                  "Hva er en SLA-avtale?",
                  "Forklar egenkapitalandel enkelt",
                ].map((s) => (
                  <button key={s} onClick={() => setQuestion(s)}
                    className="px-3 py-2 text-xs text-left rounded-lg border border-[#EDE8E3] text-[#2C3E50] hover:bg-[#F9F7F4]">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className="max-w-[82%]">
                <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-[#2C3E50] text-white rounded-br-sm"
                    : "bg-[#F4F1ED] text-[#2C3E50] rounded-bl-sm"
                }`}>
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>

                {/* Source citations */}
                {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {msg.sources.map((src) => (
                      <span key={src} title={msg.source_snippets?.[src]}
                        className="text-xs px-2 py-0.5 rounded-full bg-[#EDE8E3] text-[#8A7F74] cursor-default"
                        style={{ maxWidth: "180px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {readableSource(src)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-[#F4F1ED] px-4 py-3 rounded-2xl rounded-bl-sm">
                <div className="flex gap-1 items-center h-4">
                  {[0, 1, 2].map((i) => (
                    <span key={i} className="w-1.5 h-1.5 bg-[#8A7F74] rounded-full animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {error && <div className="broker-card bg-red-50 border-red-200 text-red-700 text-sm">{error}</div>}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={handleSubmit} className="flex gap-2 pt-4 border-t border-[#EDE8E3]">
          <textarea value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={handleKeyDown}
            placeholder="Still et spørsmål... (Enter for å sende, Shift+Enter for ny linje)"
            rows={2} disabled={isLoading}
            className="flex-1 px-3 py-2 text-sm border border-[#EDE8E3] rounded-lg text-[#2C3E50] placeholder-[#C8BEB4] focus:outline-none focus:border-[#2C3E50] resize-none disabled:opacity-50" />
          <button type="submit" disabled={isLoading || !question.trim()}
            className="px-4 py-2 rounded-lg bg-[#2C3E50] text-white text-sm font-medium hover:bg-[#3d5166] disabled:opacity-50 self-end">
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
