"use client";

import { useState, useRef, useEffect } from "react";
import { Bot, Send, Trash2, MessageSquare } from "lucide-react";
import { knowledgeChat, type TenderListItem } from "@/lib/api";
import { useT } from "@/lib/i18n";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const STARTER_QUESTIONS = [
  "Hva bør jeg spørre forsikringsselskapene om?",
  "Hvilke produkttyper mangler i anbudsporteføljen?",
  "Hva er viktig i en anbudsforespørsel?",
  "Kan du oppsummere anbudsstatusen?",
];

const STATUS_NO: Record<string, string> = {
  draft: "Utkast",
  sent: "Sendt",
  closed: "Lukket",
  analysed: "Analysert",
};

function buildTenderContext(tenders: TenderListItem[]): string {
  if (!tenders.length) return "Ingen anbud er registrert ennå.";
  const lines = tenders.map((t) => {
    const parts = [
      `Tittel: ${t.title}`,
      `Orgnr: ${t.orgnr}`,
      `Status: ${STATUS_NO[t.status] ?? t.status}`,
      `Produkttyper: ${t.product_types.join(", ")}`,
      t.deadline ? `Frist: ${t.deadline}` : null,
      `Sendt til ${t.recipient_count} forsikringsselskaper`,
      `${t.offer_count} tilbud mottatt`,
    ].filter(Boolean);
    return `- ${parts.join(" | ")}`;
  });
  return `Megleren har ${tenders.length} anbud i systemet:\n${lines.join("\n")}`;
}

export default function TenderChatPanel({ tenders }: { tenders: TenderListItem[] }) {
  const T = useT();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const ctx = buildTenderContext(tenders);
      const res = await knowledgeChat(q, undefined, controller.signal, ctx);
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer }]);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setMessages((prev) => [...prev, { role: "assistant", content: `_(${T("Avbrutt")})_` }]);
      } else {
        setError(T("Kunne ikke hente svar"));
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  function handleClear() {
    setMessages([]);
    setError(null);
  }

  return (
    <div className="broker-card flex flex-col" style={{ height: "calc(100vh - 130px)" }}>
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-border mb-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
            <Bot className="w-4 h-4 text-primary-foreground" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{T("Anbudsassistent")}</h3>
            <p className="text-xs text-muted-foreground">{T("Spør om forsikring og anbud")}</p>
          </div>
        </div>
        {messages.length > 0 && !loading && (
          <button
            onClick={handleClear}
            title={T("Tøm samtale")}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-red-500 hover:bg-red-50"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Message thread */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1 min-h-0">
        {messages.length === 0 && !loading && (
          <div className="py-4">
            <div className="flex items-center justify-center mb-3">
              <MessageSquare className="w-8 h-8 text-muted-foreground" />
            </div>
            <p className="text-xs text-center text-muted-foreground mb-4">
              {T("Still spørsmål om dine anbud eller forsikring generelt")}
            </p>
            <div className="space-y-2">
              {STARTER_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => setInput(T(q))}
                  className="w-full text-left text-xs px-3 py-2 rounded-lg border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors"
                >
                  {T(q)}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex gap-2 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            {m.role === "assistant" && (
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary flex items-center justify-center mt-0.5">
                <Bot className="w-3.5 h-3.5 text-primary-foreground" />
              </div>
            )}
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed ${
                m.role === "user"
                  ? "bg-primary text-primary-foreground rounded-br-sm"
                  : "bg-muted text-foreground rounded-bl-sm"
              }`}
            >
              <p className="whitespace-pre-wrap break-words">{m.content}</p>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-2 justify-start">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary flex items-center justify-center">
              <Bot className="w-3.5 h-3.5 text-primary-foreground" />
            </div>
            <div className="bg-muted rounded-xl px-3 py-2">
              <div className="flex gap-1 items-center h-4">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {error && (
          <p className="text-xs text-red-600 text-center">{error}</p>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2 items-end pt-3 border-t border-border mt-3 flex-shrink-0">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={T("Still et spørsmål… (Enter for å sende)")}
          rows={2}
          disabled={loading}
          className="flex-1 text-xs border border-border rounded-lg px-3 py-2 resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground placeholder:text-muted-foreground bg-background disabled:opacity-50"
        />
        {loading ? (
          <button
            onClick={() => abortRef.current?.abort()}
            className="flex-shrink-0 px-3 py-2 rounded-lg border border-border text-foreground text-xs"
          >
            {T("Stopp")}
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="flex-shrink-0 px-3 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
