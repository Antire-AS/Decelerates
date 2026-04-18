"use client";

import { useState, useRef, useEffect } from "react";
import { chatWithOrg } from "@/lib/api";
import { Loader2, Send, Bot, User, Trash2, Wrench, Sparkles } from "lucide-react";

interface ToolCall { tool: string; args: string; result: string }

interface Message {
  role: "user" | "assistant";
  text: string;
  toolCalls?: ToolCall[];
}

export default function OrgChatSection({ orgnr, orgName }: { orgnr: string; orgName?: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [agentMode, setAgentMode] = useState(false);
  const sessionId = useRef<string | undefined>(undefined);
  const bottomRef = useRef<HTMLDivElement>(null);

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

  function clearChat() {
    setMessages([]);
    sessionId.current = undefined;
    setErr(null);
  }

  return (
    <div className="broker-card flex flex-col gap-3" style={{ minHeight: "420px" }}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[#2C3E50] flex items-center gap-1.5">
            <Bot className="w-4 h-4" />
            AI-chat om {orgName ?? orgnr}
          </h3>
          <p className="text-xs text-[#8A7F74] mt-0.5">
            Stilt spørsmål basert på årsrapporter, tilbud og regnskapsdata
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAgentMode((m) => !m)}
            className={`flex items-center gap-1 px-2.5 py-1 text-xs rounded-full transition-colors ${
              agentMode
                ? "bg-[#4A6FA5] text-white"
                : "bg-[#EDE8E3] text-[#8A7F74] hover:bg-[#DDD8D3]"
            }`}
          >
            {agentMode ? <Sparkles className="w-3 h-3" /> : <Wrench className="w-3 h-3" />}
            {agentMode ? "Agent" : "RAG"}
          </button>
          {messages.length > 0 && (
            <button
              onClick={clearChat}
              className="flex items-center gap-1 text-xs text-[#C4BDB4] hover:text-red-500"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Tøm
            </button>
          )}
        </div>
      </div>

      {/* Message thread */}
      <div className="flex-1 overflow-y-auto space-y-3 max-h-72 pr-1">
        {messages.length === 0 ? (
          <div className="text-center py-8">
            <Bot className="w-8 h-8 text-[#D4C9B8] mx-auto mb-2" />
            <p className="text-xs text-[#8A7F74]">
              Still et spørsmål om {orgName ?? orgnr} for å komme i gang
            </p>
            <div className="flex flex-wrap justify-center gap-2 mt-3">
              {[
                "Hva er selskapets største risikoer?",
                "Oppsummer finansiell utvikling siste 3 år",
                "Hvilke forsikringer anbefales?",
              ].map((s) => (
                <button
                  key={s}
                  onClick={() => { setInput(s); }}
                  className="text-xs px-2.5 py-1 rounded-full border border-[#D4C9B8] text-[#8A7F74] hover:border-[#4A6FA5] hover:text-[#4A6FA5]"
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
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-[#4A6FA5] flex items-center justify-center mt-0.5">
                  <Bot className="w-3.5 h-3.5 text-white" />
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-xl px-3 py-2 text-sm ${
                  m.role === "user"
                    ? "bg-[#2C3E50] text-white"
                    : "bg-[#F5F0EB] text-[#2C3E50]"
                }`}
              >
                <p className="whitespace-pre-wrap break-words">{m.text}</p>
                {m.toolCalls && m.toolCalls.length > 0 && (
                  <div className="mt-2 border-t border-[#E0DBD5] pt-2 space-y-1">
                    {m.toolCalls.map((tc, j) => (
                      <div key={j} className="flex items-start gap-1.5 text-[10px] text-[#8A7F74]">
                        <Wrench className="w-3 h-3 flex-shrink-0 mt-0.5 text-[#4A6FA5]" />
                        <div>
                          <span className="font-semibold text-[#2C3E50]">{tc.tool}</span>
                          <span className="block text-[#C4BDB4]">{tc.result.slice(0, 200)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {m.role === "user" && (
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-[#EDE8E3] flex items-center justify-center mt-0.5">
                  <User className="w-3.5 h-3.5 text-[#8A7F74]" />
                </div>
              )}
            </div>
          ))
        )}
        {loading && (
          <div className="flex gap-2 justify-start">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-[#4A6FA5] flex items-center justify-center">
              <Bot className="w-3.5 h-3.5 text-white" />
            </div>
            <div className="bg-[#F5F0EB] rounded-xl px-3 py-2">
              <Loader2 className="w-4 h-4 animate-spin text-[#8A7F74]" />
            </div>
          </div>
        )}
        {err && (
          <p className="text-xs text-red-600 text-center">{err}</p>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2 items-end border-t border-[#EDE8E3] pt-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Still et spørsmål… (Enter for å sende)"
          rows={2}
          className="flex-1 text-sm border border-[#D4C9B8] rounded-lg px-3 py-2 resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-[#4A6FA5] text-[#2C3E50] placeholder:text-[#C4BDB4]"
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="flex-shrink-0 px-3 py-2 rounded-lg bg-[#4A6FA5] text-white hover:bg-[#3d5e8e] disabled:opacity-50"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
