"use client";

import { useState, useRef, useEffect } from "react";
import { Trash2 } from "lucide-react";
import { knowledgeChat } from "@/lib/api";
import { type Message, readableSource, renderMarkdownWithTables } from "./_shared";
import { useT } from "@/lib/i18n";

export default function ChatTab() {
  const T = useT();
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
          content: `_(${T("Avbrutt")})_`,
        }]);
      } else {
        setError(`${T("Kunne ikke hente svar")}: ${err instanceof Error ? err.message : T("Ukjent feil")}`);
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
    <div className="broker-card flex flex-col" style={{ minHeight: "70vh", maxHeight: "calc(100vh - 220px)" }}>
      <div className="flex-1 space-y-4 overflow-y-auto mb-4">
        {messages.length === 0 && !isLoading && (
          <div className="text-center py-12 text-muted-foreground">
            <p className="text-sm font-medium text-foreground mb-2">{T("Hei! Jeg er din forsikringsassistent.")}</p>
            <p className="text-sm">{T("Spør meg om forsikringstyper, risiko, kunderegulering, GDPR eller hvilken dekning et selskap trenger.")}</p>
            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-2">
              {[
                "Hva er ansvarsforsikring?",
                "Hvilken forsikring trenger et byggefirma?",
                "Hva er en SLA-avtale?",
                "Forklar egenkapitalandel enkelt",
              ].map((s) => (
                <button key={s} onClick={() => setQuestion(s)}
                  className="px-3 py-2 text-xs text-left rounded-lg border border-border text-foreground hover:bg-muted">
                  {T(s)}
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
                  ? "bg-primary text-primary-foreground rounded-br-sm"
                  : "bg-muted text-foreground rounded-bl-sm"
              }`}>
                {msg.role === "assistant"
                  ? renderMarkdownWithTables(msg.content)
                  : <p className="whitespace-pre-wrap">{msg.content}</p>}
              </div>
              {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                <details className="mt-1.5">
                  <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground inline-block">
                    {T("Kilder")} ({msg.sources.length})
                  </summary>
                  <div className="mt-1.5 space-y-1">
                    {msg.sources.map((src) => {
                      const snippet = msg.source_snippets?.[src];
                      return (
                        <div key={src} className="text-xs border border-border rounded-lg p-2 bg-muted">
                          <p className="font-medium text-foreground">{readableSource(src)}</p>
                          {snippet && (
                            <p className="text-[10px] text-muted-foreground italic mt-0.5 line-clamp-3">{snippet}</p>
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
            <div className="bg-muted px-4 py-3 rounded-2xl rounded-bl-sm">
              <div className="flex gap-1 items-center h-4">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          </div>
        )}

        {error && <div className="broker-card bg-red-50 border-red-200 text-red-700 text-sm">{error}</div>}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 pt-4 border-t border-border items-end">
        <textarea value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={handleKeyDown}
          placeholder={T("Still et spørsmål... (Enter for å sende, Shift+Enter for ny linje)")}
          rows={2} disabled={isLoading}
          className="flex-1 px-3 py-2 text-sm border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary resize-none disabled:opacity-50" />
        {messages.length > 0 && !isLoading && (
          <button type="button" onClick={() => { setMessages([]); setError(null); }}
            title={T("Tøm samtale")}
            className="px-3 py-2 rounded-lg border border-border text-muted-foreground hover:bg-muted text-sm flex items-center gap-1">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
        {isLoading ? (
          <button type="button" onClick={() => abortRef.current?.abort()}
            className="px-4 py-2 rounded-lg border border-border text-foreground text-sm font-medium hover:bg-muted">
            {T("Stopp")}
          </button>
        ) : (
          <button type="submit" disabled={!question.trim()}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
            {T("Send")}
          </button>
        )}
      </form>
    </div>
  );
}
