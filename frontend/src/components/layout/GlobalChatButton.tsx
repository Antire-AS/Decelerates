"use client";

import { useState, useRef, useEffect } from "react";
import { Sparkles, Send, X, Loader2 } from "lucide-react";
import { knowledgeChat, type KnowledgeChatOut } from "@/lib/api";
import { useT } from "@/lib/i18n";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const STARTERS = [
  "Hva skjer i dag?",
  "Hvilke avtaler forfaller snart?",
  "Vis åpne skader",
  "Hvem bør jeg følge opp?",
];

export default function GlobalChatButton() {
  const T = useT();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, open]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || pending) return;
    setError(null);
    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setInput("");
    setPending(true);
    try {
      const res: KnowledgeChatOut = await knowledgeChat(trimmed);
      setMessages((m) => [...m, { role: "assistant", content: res.answer ?? T("Ingen svar.") }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 flex items-center justify-center transition-all hover:scale-105"
          title={T("AI-assistent")}
          aria-label={T("Åpne AI-assistent")}
        >
          <Sparkles className="w-5 h-5" />
        </button>
      )}

      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[1px]"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div className="fixed bottom-0 right-0 z-50 h-full w-96 max-w-[95vw] flex flex-col shadow-2xl bg-background">
            <div className="flex items-center justify-between px-4 py-3 bg-primary text-primary-foreground">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                <span className="font-semibold text-sm">{T("AI-assistent")}</span>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="text-primary-foreground/70 hover:text-primary-foreground"
                aria-label={T("Lukk")}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
              {messages.length === 0 && (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    {T("Spør om porteføljen din, åpne skader, kommende fornyelser, eller noe annet.")}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {STARTERS.map((q) => (
                      <button
                        key={q}
                        onClick={() => send(q)}
                        className="text-xs px-2.5 py-1 rounded-full border border-border bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
                      >
                        {T(q)}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
                >
                  <div
                    className={
                      m.role === "user"
                        ? "max-w-[85%] bg-primary text-primary-foreground text-sm px-3 py-2 rounded-lg rounded-br-sm"
                        : "max-w-[85%] bg-muted text-foreground text-sm px-3 py-2 rounded-lg rounded-bl-sm whitespace-pre-wrap"
                    }
                  >
                    {m.content}
                  </div>
                </div>
              ))}
              {pending && (
                <div className="flex justify-start">
                  <div className="bg-muted text-muted-foreground text-sm px-3 py-2 rounded-lg rounded-bl-sm flex items-center gap-1.5">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    {T("Tenker…")}
                  </div>
                </div>
              )}
              {error && (
                <p className="text-xs text-red-600">{error}</p>
              )}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                send(input);
              }}
              className="border-t border-border p-3 flex gap-2"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={T("Spør AI-assistenten…")}
                disabled={pending}
                className="flex-1 text-sm px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!input.trim() || pending}
                className="px-3 py-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                aria-label={T("Send")}
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </>
      )}
    </>
  );
}
