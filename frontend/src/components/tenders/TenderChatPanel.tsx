"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { mutate as globalMutate } from "swr";
import {
  tenderChat,
  listTenderSessions,
  getTenderSession,
  deleteTenderSession,
  type TenderListItem,
  type TenderChatSession,
} from "@/lib/api";
import { Send, Trash2, StopCircle, MessageSquare, Plus, ChevronDown, ChevronUp } from "lucide-react";
import { useT } from "@/lib/i18n";
import { ThinkingIndicator, stripMarkdown } from "@/lib/chat-utils";

const STATUS_NO: Record<string, string> = {
  draft: "Utkast",
  sent: "Sendt",
  closed: "Lukket",
  analysed: "Analysert",
};

function buildTenderContext(tenders: TenderListItem[]): string {
  if (!tenders.length) return "Megleren har ingen anbud ennå.";
  const lines = tenders.map(
    (t) =>
      `- Tittel: ${t.title} | Orgnr: ${t.orgnr ?? "–"} | Status: ${STATUS_NO[t.status] ?? t.status} | Produkttyper: ${t.product_types.join(", ")} | Frist: ${t.deadline ?? "ikke satt"} | Sendt til ${t.recipient_count} selskaper | ${t.offer_count} tilbud mottatt`,
  );
  return `Megleren har ${tenders.length} anbud:\n${lines.join("\n")}`;
}

const STARTERS = [
  "Kan du oppsummere alle anbudene mine?",
  "Hvilke anbud har gått ut på fristen?",
  "Hva bør jeg følge opp nå?",
  "Hva er viktig i en anbudsforespørsel?",
];

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("nb-NO", { day: "numeric", month: "short" });
}

export default function TenderChatPanel({
  tenders,
  initialSessionId,
}: {
  tenders: TenderListItem[];
  initialSessionId?: number;
}) {
  const T = useT();
  const router = useRouter();
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [sessionId, setSessionId] = useState<number | null>(initialSessionId ?? null);
  const [sessions, setSessions] = useState<TenderChatSession[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadSessions = useCallback(() => {
    listTenderSessions()
      .then(setSessions)
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (initialSessionId && initialSessionId !== sessionId) {
      loadSession(initialSessionId);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function loadSession(id: number) {
    try {
      const detail = await getTenderSession(id);
      setSessionId(id);
      setMessages(
        detail.messages.map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
        })),
      );
      setShowHistory(false);
      router.replace(`/tenders?session=${id}`, { scroll: false });
    } catch {
      // ignore
    }
  }

  function newChat() {
    setSessionId(null);
    setMessages([]);
    setInput("");
    setShowHistory(false);
    router.replace("/tenders", { scroll: false });
  }

  async function send(question: string) {
    if (!question.trim() || loading) return;
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);
    abortRef.current = new AbortController();
    try {
      const res = await tenderChat(
        question,
        buildTenderContext(tenders),
        sessionId ?? undefined,
        abortRef.current.signal,
      );
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer }]);
      if (!sessionId) {
        setSessionId(res.session_id);
        setSessions((prev) => [
          { id: res.session_id, title: res.session_title, created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
          ...prev,
        ]);
        router.replace(`/tenders?session=${res.session_id}`, { scroll: false });
      } else {
        setSessions((prev) => {
          const updated = prev.map((s) =>
            s.id === sessionId ? { ...s, updated_at: new Date().toISOString() } : s,
          );
          return [
            ...updated.filter((s) => s.id === sessionId),
            ...updated.filter((s) => s.id !== sessionId),
          ];
        });
      }
      globalMutate("tender-sessions-nav");
    } catch (e: unknown) {
      if ((e as Error)?.name !== "AbortError") {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: T("Beklager, kunne ikke hente svar.") },
        ]);
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  async function deleteSession(id: number, e: React.MouseEvent) {
    e.stopPropagation();
    await deleteTenderSession(id).catch(() => {});
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (sessionId === id) newChat();
  }

  return (
    <div className="broker-card flex flex-col" style={{ height: "calc(100vh - 130px)" }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-primary" />
          <span className="font-semibold text-sm text-foreground truncate max-w-[150px]">
            {sessionId
              ? (sessions.find((s) => s.id === sessionId)?.title ?? T("Anbudsassistent"))
              : T("Anbudsassistent")}
          </span>
        </div>
        <button
          onClick={newChat}
          className="p-1.5 rounded hover:bg-accent text-muted-foreground hover:text-primary"
          title={T("Ny samtale")}
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground text-center py-2">
              {T("Spør om dine anbud eller anbudsprosess")}
            </p>
            {STARTERS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="w-full text-left text-xs px-3 py-2 rounded-lg border border-border hover:border-primary hover:text-primary text-muted-foreground transition-colors"
              >
                {T(s)}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] text-xs px-3 py-2 rounded-xl leading-relaxed whitespace-pre-wrap ${
                m.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-accent text-foreground"
              }`}
            >
              {stripMarkdown(m.content)}
            </div>
          </div>
        ))}
        {loading && <ThinkingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-3 pb-2 pt-1">
        <div className="flex gap-2 items-end">
          <textarea
            className="input-sm flex-1 resize-none text-xs"
            rows={2}
            placeholder={T("Spør om et anbud...")}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
          />
          {loading ? (
            <button
              onClick={() => { abortRef.current?.abort(); setLoading(false); }}
              className="p-2 bg-red-500 text-white rounded-lg hover:bg-red-600 flex-shrink-0"
            >
              <StopCircle className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={() => send(input)}
              disabled={!input.trim()}
              className="p-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/80 disabled:opacity-50 flex-shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Session history */}
      {sessions.length > 0 && (
        <div className="border-t border-border">
          <button
            onClick={() => setShowHistory((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-2 text-xs text-muted-foreground hover:text-foreground"
          >
            <span>{T("Tidligere samtaler")} ({sessions.length})</span>
            {showHistory ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
          </button>
          {showHistory && (
            <div className="max-h-40 overflow-y-auto px-2 pb-2 space-y-0.5">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  onClick={() => loadSession(s.id)}
                  className={`flex items-center justify-between px-2 py-1.5 rounded cursor-pointer group text-xs ${
                    s.id === sessionId
                      ? "bg-accent text-foreground"
                      : "hover:bg-accent/50 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <span className="truncate flex-1">{s.title}</span>
                  <div className="flex items-center gap-1.5 flex-shrink-0 ml-1">
                    <span className="text-[10px] opacity-60">{formatDate(s.updated_at)}</span>
                    <button
                      onClick={(e) => deleteSession(s.id, e)}
                      className="opacity-0 group-hover:opacity-100 hover:text-red-500"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
