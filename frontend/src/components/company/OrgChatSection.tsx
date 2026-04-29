"use client";

import { useState, useRef, useEffect } from "react";
import useSWR from "swr";
import { chatWithOrg, getChatHistory, clearChatHistory, getKnowledgeStats, type KnowledgeStatsOut } from "@/lib/api";
import { Loader2, Send, Bot, User, Trash2, Wrench, Sparkles } from "lucide-react";
import { useT } from "@/lib/i18n";
import ChatMarkdown from "@/components/common/ChatMarkdown";

interface ToolCall { tool: string; args: string; result: string }

interface Message {
  role: "user" | "assistant";
  text: string;
  toolCalls?: ToolCall[];
}

export default function OrgChatSection({ orgnr, orgName }: { orgnr: string; orgName?: string }) {
  const T = useT();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [agentMode, setAgentMode] = useState(false);
  const { data: kbStats } = useSWR<KnowledgeStatsOut>("knowledge-stats", getKnowledgeStats);
  const sessionId = useRef<string | undefined>(undefined);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Hydrate prior per-user conversation for this company so memory persists
  // across sessions. Session history (company_notes) stays session-scoped as
  // before — these two layers complement each other.
  useEffect(() => {
    (async () => {
      try {
        const history = await getChatHistory(orgnr);
        if (history.messages.length > 0) {
          setMessages(
            history.messages.map((m) => ({ role: m.role, text: m.content })),
          );
        }
      } catch {
        /* non-fatal */
      }
    })();
  }, [orgnr]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const question = input.trim();
    if (!question || loading) return;
    setInput("");
    setErr(null);
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setLoading(true);
    try {
      const res = await chatWithOrg(orgnr, question, sessionId.current, agentMode ? "agent" : "rag");
      if (res.session_id) sessionId.current = res.session_id;
      setMessages((prev) => [...prev, { role: "assistant", text: res.answer, toolCalls: res.tool_calls }]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  async function clearChat() {
    try {
      await clearChatHistory(orgnr);
    } catch {
      /* still clear local view on failure */
    }
    setMessages([]);
    sessionId.current = undefined;
    setErr(null);
  }

  return (
    <div className="broker-card flex flex-col gap-3" style={{ minHeight: "420px" }}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
            <Bot className="w-4 h-4" />
            {T("AI-chat om")} {orgName ?? orgnr}
            {kbStats && kbStats.total_chunks > 0 && (
              <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                <Sparkles className="w-2.5 h-2.5" />
                {T("RAG")} · {kbStats.total_chunks} {T("kilder indeksert")}
              </span>
            )}
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {T("Stilt spørsmål basert på årsrapporter, tilbud og regnskapsdata")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAgentMode((m) => !m)}
            className={`flex items-center gap-1 px-2.5 py-1 text-xs rounded-full transition-colors ${
              agentMode
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted"
            }`}
          >
            {agentMode ? <Sparkles className="w-3 h-3" /> : <Wrench className="w-3 h-3" />}
            {agentMode ? T("Agent") : T("RAG")}
          </button>
          {messages.length > 0 && (
            <button
              onClick={clearChat}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-red-500"
            >
              <Trash2 className="w-3.5 h-3.5" />
              {T("Tøm")}
            </button>
          )}
        </div>
      </div>

      {/* Message thread */}
      <div className="flex-1 overflow-y-auto space-y-3 min-h-[28rem] max-h-[60vh] pr-1">
        {messages.length === 0 ? (
          <div className="text-center py-8">
            <Bot className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">
              {T("Still et spørsmål om")} {orgName ?? orgnr} {T("for å komme i gang")}
            </p>
            <div className="flex flex-wrap justify-center gap-2 mt-3">
              {[
                T("Hva er selskapets største risikoer?"),
                T("Oppsummer finansiell utvikling siste 3 år"),
                T("Hvilke forsikringer anbefales?"),
              ].map((s) => (
                <button
                  key={s}
                  onClick={() => { setInput(s); }}
                  className="text-xs px-2.5 py-1 rounded-full border border-border text-muted-foreground hover:border-primary hover:text-primary"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={`flex gap-2 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              {m.role === "assistant" && (
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary flex items-center justify-center mt-0.5">
                  <Bot className="w-3.5 h-3.5 text-white" />
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-xl px-3 py-2 text-sm ${
                  m.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-background text-foreground"
                }`}
              >
                {m.role === "assistant" ? (
                  <ChatMarkdown text={m.text} />
                ) : (
                  <p className="whitespace-pre-wrap break-words">{m.text}</p>
                )}
                {m.toolCalls && m.toolCalls.length > 0 && (
                  <div className="mt-2 border-t border-border pt-2 space-y-1">
                    {m.toolCalls.map((tc, j) => (
                      <div key={j} className="flex items-start gap-1.5 text-[10px] text-muted-foreground">
                        <Wrench className="w-3 h-3 flex-shrink-0 mt-0.5 text-primary" />
                        <div>
                          <span className="font-semibold text-foreground">{tc.tool}</span>
                          <span className="block text-muted-foreground">{tc.result.slice(0, 200)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {m.role === "user" && (
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-muted flex items-center justify-center mt-0.5">
                  <User className="w-3.5 h-3.5 text-muted-foreground" />
                </div>
              )}
            </div>
          ))
        )}
        {loading && (
          <div className="flex gap-2 justify-start">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary flex items-center justify-center">
              <Bot className="w-3.5 h-3.5 text-white" />
            </div>
            <div className="bg-background rounded-xl px-3 py-2">
              <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
            </div>
          </div>
        )}
        {err && (
          <p className="text-xs text-red-600 text-center">{err}</p>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2 items-end border-t border-border pt-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={T("Still et spørsmål… (Enter for å sende)")}
          rows={2}
          className="flex-1 text-sm border border-border rounded-lg px-3 py-2 resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground placeholder:text-muted-foreground"
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="flex-shrink-0 px-3 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
