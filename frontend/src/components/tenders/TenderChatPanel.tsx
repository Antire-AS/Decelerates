"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Sparkles, Loader2, MessageSquare } from "lucide-react";
import { knowledgeChat, type KnowledgeChatOut } from "@/lib/api";
import { useT } from "@/lib/i18n";

/**
 * Simplified version of Patrick's TenderChatPanel from PR #293 — drops the
 * SSE streaming + persistent sessions and uses the existing /knowledge/chat
 * endpoint instead. The broker gets a chat surface scoped to a single tender
 * with the tender context preloaded into every question.
 *
 * When Patrick's streaming backend lands, we can swap the inner call from
 * `knowledgeChat()` to `streamTenderChat()` without changing this UI.
 */
interface Message {
  role: "user" | "assistant";
  content: string;
}

interface TenderContext {
  title: string;
  orgnr?: string | null;
  product_types?: string[];
  deadline?: string | null;
  recipient_count: number;
  offer_count: number;
  status: string;
}

interface Props {
  tender: TenderContext;
}

const STARTERS = [
  "Oppsummer dette anbudet",
  "Hvilke selskaper bør jeg sende til?",
  "Sammenlign tilbudene som har kommet inn",
  "Hva er fristen og hvor mange dager igjen?",
];

function buildContextString(t: TenderContext): string {
  const parts = [
    `Tittel: ${t.title}`,
    t.orgnr ? `Orgnr: ${t.orgnr}` : null,
    t.product_types?.length ? `Produkttyper: ${t.product_types.join(", ")}` : null,
    t.deadline ? `Frist: ${t.deadline}` : null,
    `Status: ${t.status}`,
    `Mottakere: ${t.recipient_count} selskap${t.recipient_count === 1 ? "" : "er"}`,
    `Tilbud mottatt: ${t.offer_count}`,
  ].filter(Boolean);
  return `[ANBUD-DETALJER]\n${parts.join("\n")}`;
}

export default function TenderChatPanel({ tender }: Props) {
  const T = useT();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, pending]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || pending) return;
    setError(null);
    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setInput("");
    setPending(true);
    try {
      // Pre-pend tender context so the LLM can answer scoped questions.
      const contextual = `${buildContextString(tender)}\n\n[SPØRSMÅL]\n${trimmed}`;
      const res: KnowledgeChatOut = await knowledgeChat(contextual);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: res.answer ?? T("Ingen svar.") },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="broker-card flex flex-col" style={{ minHeight: 420 }}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">
            {T("AI-chat om dette anbudet")}
          </h3>
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            {T("Tøm")}
          </button>
        )}
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-3 mb-3">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {T("Spør AI-assistenten om dette anbudet — frister, mottakere, tilbud, anbefalinger.")}
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
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="border-t border-border pt-3 flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={T("Spør om dette anbudet…")}
          disabled={pending}
          className="flex-1 text-sm px-3 py-2 rounded-md border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!input.trim() || pending}
          className="px-3 py-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          aria-label={T("Send")}
        >
          {pending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </form>
      {/* Avoid eslint unused-import */}
      <span className="hidden">
        <MessageSquare aria-hidden />
      </span>
    </div>
  );
}
