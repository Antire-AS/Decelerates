"use client";

import { useState, useRef, useEffect } from "react";
import { Trash2 } from "lucide-react";
import { knowledgeChat } from "@/lib/api";
import { type Message, readableSource, renderMarkdownWithTables } from "./_shared";

export default function ChatTab() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

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
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const res = await knowledgeChat(q, undefined, controller.signal);
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: res.answer,
        sources: res.sources,
        source_snippets: res.source_snippets,
      }]);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setMessages((prev) => [...prev, {
          role: "assistant",
          content: "_(Avbrutt)_",
        }]);
      } else {
        setError(`Kunne ikke hente svar: ${err instanceof Error ? err.message : "Ukjent feil"}`);
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit(e as unknown as React.FormEvent);
    }
  }

  return (
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
                {msg.role === "assistant"
                  ? renderMarkdownWithTables(msg.content)
                  : <p className="whitespace-pre-wrap">{msg.content}</p>}
              </div>
              {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                <details className="mt-1.5">
                  <summary className="text-xs text-[#8A7F74] cursor-pointer hover:text-[#2C3E50] inline-block">
                    Kilder ({msg.sources.length})
                  </summary>
                  <div className="mt-1.5 space-y-1">
                    {msg.sources.map((src) => {
                      const snippet = msg.source_snippets?.[src];
                      return (
                        <div key={src} className="text-xs border border-[#EDE8E3] rounded-lg p-2 bg-[#F9F7F4]">
                          <p className="font-medium text-[#2C3E50]">{readableSource(src)}</p>
                          {snippet && (
                            <p className="text-[10px] text-[#8A7F74] italic mt-0.5 line-clamp-3">{snippet}</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </details>
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

      <form onSubmit={handleSubmit} className="flex gap-2 pt-4 border-t border-[#EDE8E3] items-end">
        <textarea value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={handleKeyDown}
          placeholder="Still et spørsmål... (Enter for å sende, Shift+Enter for ny linje)"
          rows={2} disabled={isLoading}
          className="flex-1 px-3 py-2 text-sm border border-[#EDE8E3] rounded-lg text-[#2C3E50] placeholder-[#C8BEB4] focus:outline-none focus:border-[#2C3E50] resize-none disabled:opacity-50" />
        {messages.length > 0 && !isLoading && (
          <button type="button" onClick={() => { setMessages([]); setError(null); }}
            title="Tøm samtale"
            className="px-3 py-2 rounded-lg border border-[#EDE8E3] text-[#8A7F74] hover:bg-[#F4F1ED] text-sm flex items-center gap-1">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
        {isLoading ? (
          <button type="button" onClick={() => abortRef.current?.abort()}
            className="px-4 py-2 rounded-lg border border-[#EDE8E3] text-[#2C3E50] text-sm font-medium hover:bg-[#F4F1ED]">
            Stopp
          </button>
        ) : (
          <button type="submit" disabled={!question.trim()}
            className="px-4 py-2 rounded-lg bg-[#2C3E50] text-white text-sm font-medium hover:bg-[#3d5166] disabled:opacity-50">
            Send
          </button>
        )}
      </form>
    </div>
  );
}
