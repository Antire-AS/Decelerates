"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import useSWR from "swr";
import { useSession } from "next-auth/react";
import { mutate as globalMutate } from "swr";
import Link from "next/link";
import {
  streamTenderChat,
  listTenderSessions,
  getTenderSession,
  getHomeSummary,
  getTenders,
  knowledgeQuickUpload,
  uploadTenderOffer,
  uploadInsuranceDocument,
  type TenderChatSession,
  type HomeSummary,
  type TenderListItem,
} from "@/lib/api";
import { stripMarkdown, relativeTime } from "@/lib/chat-utils";
import {
  Scale, Send, StopCircle, Plus, ArrowLeft, Bell,
  FileText, Clock, RotateCcw, ChevronRight, X,
  Upload, Link2, BookOpen, Folder, Copy, ThumbsUp, ThumbsDown, Share2, MoreHorizontal,
} from "lucide-react";
import { toast } from "sonner";
import { useT } from "@/lib/i18n";

// ── Greeting helper ──────────────────────────────────────────────────────────
function greeting(name?: string | null): string {
  const hour = new Date().getHours();
  const time = hour < 12 ? "God morgen" : hour < 18 ? "God dag" : "God kveld";
  return name ? `${time}, ${name.split(" ")[0]}` : time;
}

// ── Suggested starters ───────────────────────────────────────────────────────
const STARTERS = [
  "Hva bør jeg prioritere i dag?",
  "Gi meg en oppsummering av alle anbud",
  "Hva forfaller snart?",
  "Hva er status i pipeline?",
];

// ── Main component ───────────────────────────────────────────────────────────
export default function JarvisHome() {
  const T = useT();
  const { data: session } = useSession();
  const userName = (session?.user as { name?: string })?.name ?? null;

  const { data: summary } = useSWR<HomeSummary>("home-summary", getHomeSummary, {
    refreshInterval: 60_000,
  });
  const { data: sessions } = useSWR<TenderChatSession[]>(
    "tender-sessions-nav",
    listTenderSessions,
  );
  const { data: tenders } = useSWR<TenderListItem[]>("tenders", getTenders);

  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string; thinking?: string; thinkingSeconds?: number; isStreaming?: boolean }[]>([]);
  const sendStartRef = useRef<number>(0);

  const [sessionId, setSessionId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [routingFile, setRoutingFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const chatActive = messages.length > 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);


  useEffect(() => {
    if (!chatActive) inputRef.current?.focus();
  }, [chatActive]);

  const loadSession = useCallback(async (id: number) => {
    try {
      const detail = await getTenderSession(id);
      setSessionId(id);
      setMessages(
        detail.messages.map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
        })),
      );
    } catch { /* ignore */ }
  }, []);

  function editMessage(index: number) {
    const msg = messages[index];
    if (!msg || msg.role !== "user") return;
    setMessages((prev) => prev.slice(0, index));
    setInput(msg.content);
    setSessionId(null);
    inputRef.current?.focus();
  }

  const send = useCallback(async (question: string) => {
    if (!question.trim() || loading) return;
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    if (inputRef.current) { inputRef.current.style.height = "36px"; inputRef.current.style.overflowY = "hidden"; }
    setLoading(true);
    sendStartRef.current = Date.now();
    abortRef.current = new AbortController();

    // Insert empty assistant message immediately — fills in as stream arrives
    let msgIdx = -1;
    setMessages((prev) => {
      const next = [...prev, { role: "assistant" as const, content: "", thinking: "", isStreaming: true, thinkingSeconds: 0 }];
      msgIdx = next.length - 1;
      return next;
    });

    try {
      for await (const ev of streamTenderChat(question, sessionId ?? undefined, undefined, abortRef.current.signal)) {
        if (ev.type === "thinking") {
          setMessages((prev) => prev.map((m, i) =>
            i === msgIdx ? { ...m, thinking: (m.thinking ?? "") + ev.text } : m
          ));
        } else if (ev.type === "answer") {
          setMessages((prev) => prev.map((m, i) =>
            i === msgIdx ? { ...m, content: m.content + ev.text } : m
          ));
        } else if (ev.type === "done") {
          const elapsed = Math.round((Date.now() - sendStartRef.current) / 1000);
          setMessages((prev) => prev.map((m, i) =>
            i === msgIdx ? { ...m, isStreaming: false, thinkingSeconds: elapsed } : m
          ));
          if (!sessionId) {
            setSessionId(ev.session_id);
            globalMutate("tender-sessions-nav");
          }
        }
      }
    } catch (e: unknown) {
      if ((e as Error)?.name !== "AbortError") {
        setMessages((prev) => prev.map((m, i) =>
          i === msgIdx ? { ...m, content: T("Beklager, kunne ikke hente svar."), isStreaming: false } : m
        ));
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }, [loading, sessionId, T]);

  function newChat() {
    setMessages([]);
    setSessionId(null);
    setInput("");
    setAttachedFile(null);
    setRoutingFile(null);
  }

  function handleAttach(file: File) {
    setAttachedFile(file);
    setRoutingFile(file);
  }

  function handleRouteDone(summary: string) {
    setAttachedFile(null);
    setRoutingFile(null);
    send(`Jeg lastet opp filen "${summary.split('"')[1] ?? "filen"}". ${summary}`);
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      {/* ── Chat-tilstand ───────────────────────────────────────────────────── */}
      {chatActive ? (
        <div className="flex flex-col overflow-x-hidden" style={{ height: "calc(100vh - 130px)" }}>
          <div className="max-w-3xl mx-auto w-full flex items-center justify-between mb-3">
            <button
              onClick={newChat}
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="w-4 h-4" />
              {T("Hjem")}
            </button>
            <button
              onClick={newChat}
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary"
            >
              <Plus className="w-4 h-4" />
              {T("Ny samtale")}
            </button>
          </div>

          {/* Scroll-beholder strekker seg til høyre skjermkant */}
          <div className="flex-1 overflow-y-auto chat-scroll -mr-4 md:-mr-6">
            <div className="max-w-3xl mx-auto space-y-4 pb-4 min-h-[40vh] flex flex-col justify-end">
            {messages.map((m, i) => (
              <div key={i} className={`group flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                {m.role === "user" ? (
                  <div className="flex items-end gap-2 max-w-[80%]">
                    <button
                      onClick={() => editMessage(i)}
                      className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-foreground mb-1 flex-shrink-0 transition-opacity"
                      title="Rediger spørsmål"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <div className="text-sm px-4 py-3 rounded-2xl leading-relaxed whitespace-pre-wrap bg-primary text-primary-foreground">
                      {stripMarkdown(m.content)}
                    </div>
                  </div>
                ) : (
                  <div className="max-w-[85%] space-y-2">
                    {m.thinking && (
                      <ThinkingBlock
                        thinking={m.thinking}
                        seconds={m.thinkingSeconds ?? 0}
                        isStreaming={!!m.isStreaming}
                      />
                    )}
                    {m.content && (
                    <div className="text-sm leading-relaxed whitespace-pre-wrap text-foreground py-1">
                      {stripMarkdown(m.content)}
                      {m.isStreaming && (
                        <span className="inline-block w-[2px] h-[0.9em] bg-foreground/50 ml-[1px] align-middle animate-pulse" />
                      )}
                    </div>
                    )}
                    {!m.isStreaming && (
                      <MessageActions
                        content={m.content}
                        onRetry={() => {
                          const prev = messages[i - 1];
                          if (prev?.role === "user") {
                            setMessages((ms) => ms.slice(0, i - 1));
                            send(prev.content);
                          }
                        }}
                        onNewChat={() => {
                          const prev = messages[i - 1];
                          newChat();
                          if (prev?.role === "user") setTimeout(() => send(prev.content), 50);
                        }}
                        onFeedback={(feedback) => {
                          const prev = messages[i - 1];
                          if (prev?.role === "user") {
                            send(`${prev.content}\n\n[Tilbakemelding på forrige svar: ${feedback}. Vennligst gi et forbedret svar.]`);
                          }
                        }}
                      />
                    )}
                  </div>
                )}
              </div>
            ))}
            {loading && !messages.some(m => m.isStreaming && m.thinking) && (
              <div className="flex items-center gap-2 px-1 py-2">
                <Scale className="w-4 h-4 text-brand-mid animate-thinking flex-shrink-0" />
                <span className="text-sm text-foreground/70 italic">Tenker...</span>
              </div>
            )}
            <div ref={bottomRef} />
            </div>
          </div>

          <div className="max-w-3xl mx-auto w-full">
            <ChatInput
              value={input}
              onChange={setInput}
              onSend={send}
              onStop={() => { abortRef.current?.abort(); setLoading(false); }}
              loading={loading}
              inputRef={inputRef}
              attachedFile={attachedFile}
              onAttach={handleAttach}
              onRemoveAttachment={() => setAttachedFile(null)}
              fileInputRef={fileInputRef}
            />
          </div>
        </div>

      ) : (

      /* ── Home-tilstand ───────────────────────────────────────────────────── */
        <div className="max-w-3xl mx-auto space-y-8">

          {/* Header */}
          <div className="text-center pt-4 pb-1">
            <div className="flex justify-center mb-3">
              <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center shadow-lg">
                <Scale className="w-6 h-6 text-primary-foreground" />
              </div>
            </div>
            <h1 className="text-2xl font-bold text-foreground mb-1">
              {greeting(userName)}
            </h1>
            <p className="text-muted-foreground text-sm">Hva kan jeg hjelpe deg med i dag?</p>
          </div>

          {/* Chat input — narrower, centered */}
          <div className="max-w-xs mx-auto">
            <ChatInput
              value={input}
              onChange={setInput}
              onSend={send}
              onStop={() => { abortRef.current?.abort(); setLoading(false); }}
              loading={loading}
              inputRef={inputRef}
              attachedFile={attachedFile}
              onAttach={handleAttach}
              onRemoveAttachment={() => setAttachedFile(null)}
              fileInputRef={fileInputRef}
            />
          </div>

          {/* Three sections grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

            {/* Seksjon 1: Dette har skjedd */}
            {summary && (summary.new_tender_offers > 0 || summary.unread_notifications > 0 || summary.critical_renewals.length > 0) && (
              <div className="broker-card">
                <h2 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                  <Bell className="w-4 h-4 text-primary" />
                  {T("Dette har skjedd")}
                </h2>
                <ul className="space-y-2">
                  {summary.unread_notifications > 0 && (
                    <li>
                      <Link href="/dashboard" className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground group">
                        <Bell className="w-3.5 h-3.5 text-brand-warning flex-shrink-0" />
                        <span><span className="font-medium text-foreground">{summary.unread_notifications}</span> uleste varsler</span>
                        <ChevronRight className="w-3 h-3 ml-auto opacity-0 group-hover:opacity-100" />
                      </Link>
                    </li>
                  )}
                  {summary.new_tender_offers > 0 && (
                    <li>
                      <Link href="/tenders" className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground group">
                        <FileText className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                        <span><span className="font-medium text-foreground">{summary.new_tender_offers}</span> nye tilbud mottatt på anbud</span>
                        <ChevronRight className="w-3 h-3 ml-auto opacity-0 group-hover:opacity-100" />
                      </Link>
                    </li>
                  )}
                  {summary.critical_renewals.map((r) => (
                    <li key={r.orgnr}>
                      <Link href="/renewals" className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground group">
                        <Clock className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />
                        <span className="truncate">
                          <span className="font-medium text-foreground">{r.client}</span>
                          {" "}fornyes om <span className="text-red-500 font-medium">{r.days}d</span>
                        </span>
                        <ChevronRight className="w-3 h-3 ml-auto flex-shrink-0 opacity-0 group-hover:opacity-100" />
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Seksjon 2: Jobbet med sist */}
            {sessions && sessions.length > 0 && (
              <div className="broker-card">
                <h2 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                  <RotateCcw className="w-4 h-4 text-primary" />
                  {T("Dette jobbet du med sist")}
                </h2>
                <ul className="space-y-1">
                  {sessions.slice(0, 4).map((s) => (
                    <li key={s.id}>
                      <button
                        onClick={() => loadSession(s.id)}
                        className="w-full flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground group px-2 py-1.5 rounded-lg hover:bg-accent transition-colors text-left"
                      >
                        <Scale className="w-3.5 h-3.5 flex-shrink-0 text-brand-mid" />
                        <span className="truncate flex-1">{s.title}</span>
                        <span className="text-[10px] flex-shrink-0 opacity-60">{relativeTime(s.updated_at)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Seksjon 3: Hva vil du jobbe med? */}
          <div>
            <h2 className="text-sm font-semibold text-muted-foreground mb-3 text-center">
              {T("Hva ønsker du å jobbe med nå?")}
            </h2>
            <div className="flex flex-wrap gap-2 justify-center">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-sm px-4 py-2 rounded-full border border-border text-muted-foreground hover:border-primary hover:text-primary hover:bg-accent transition-colors"
                >
                  {T(s)}
                </button>
              ))}
            </div>
          </div>

        </div>
      )}

      {/* File routing modal */}
      {routingFile && (
        <FileRoutingModal
          file={routingFile}
          tenders={tenders ?? []}
          onClose={() => { setRoutingFile(null); setAttachedFile(null); }}
          onDone={handleRouteDone}
        />
      )}
    </>
  );
}

// ── Message action bar (under assistant responses) ───────────────────────────
function MessageActions({
  content,
  onRetry,
  onNewChat,
  onFeedback,
}: {
  content: string;
  onRetry: () => void;
  onNewChat: () => void;
  onFeedback?: (text: string) => void;
}) {
  const [copied, setCopied] = useState(false);
  const [liked, setLiked] = useState<"up" | "down" | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ bottom: 0, left: 0 });
  const menuBtnRef = useRef<HTMLButtonElement>(null);

  function copy() {
    navigator.clipboard.writeText(stripMarkdown(content));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function submitFeedback() {
    if (!feedbackText.trim()) return;
    onFeedback?.(feedbackText.trim());
    setFeedbackText("");
    setFeedbackOpen(false);
  }

  const btn = "p-1.5 rounded-lg text-muted-foreground/60 hover:text-foreground hover:bg-accent transition-colors";

  return (
    <div className="space-y-2">
      {/* Feedback input */}
      {feedbackOpen && (
        <div className="flex items-center gap-2 mt-1">
          <input
            autoFocus
            className="input-sm flex-1 text-xs"
            placeholder="Hva var feil med svaret?"
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitFeedback();
              if (e.key === "Escape") { setFeedbackOpen(false); setLiked(null); }
            }}
          />
          <button
            onClick={submitFeedback}
            disabled={!feedbackText.trim()}
            className="px-2.5 py-1 bg-primary text-primary-foreground text-xs rounded-lg hover:bg-primary/80 disabled:opacity-40"
          >
            Send
          </button>
          <button
            onClick={() => { setFeedbackOpen(false); setLiked(null); }}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity relative">
      <button onClick={copy} className={btn} title="Kopier">
        {copied
          ? <svg className="w-3.5 h-3.5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
          : <Copy className="w-3.5 h-3.5" />
        }
      </button>
      <button
        onClick={() => setLiked(liked === "up" ? null : "up")}
        className={`${btn} ${liked === "up" ? "text-primary" : ""}`}
        title="Bra svar"
      >
        <ThumbsUp className="w-3.5 h-3.5" />
      </button>
      <button
        onClick={() => {
          const next = liked === "down" ? null : "down";
          setLiked(next);
          setFeedbackOpen(next === "down");
        }}
        className={`${btn} ${liked === "down" ? "text-red-500" : ""}`}
        title="Dårlig svar"
      >
        <ThumbsDown className="w-3.5 h-3.5" />
      </button>
      <button onClick={onRetry} className={btn} title="Prøv på nytt">
        <RotateCcw className="w-3.5 h-3.5" />
      </button>
      <div className="relative">
        <button
          ref={menuBtnRef}
          onClick={() => {
            if (menuBtnRef.current) {
              const r = menuBtnRef.current.getBoundingClientRect();
              setMenuPos({ bottom: window.innerHeight - r.top + 8, left: r.left });
            }
            setMenuOpen((v) => !v);
          }}
          className={btn}
          title="Mer"
        >
          <MoreHorizontal className="w-3.5 h-3.5" />
        </button>
        {menuOpen && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
            <div
              className="fixed z-50 bg-popover border border-border rounded-xl shadow-lg py-1 w-48"
              style={{ bottom: menuPos.bottom, left: menuPos.left }}
            >
              <button
                onClick={() => { setMenuOpen(false); onNewChat(); }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-accent"
              >
                <Share2 className="w-3.5 h-3.5 text-muted-foreground" />
                Fortsett i ny chat
              </button>
            </div>
          </>
        )}
      </div>
      </div>
    </div>
  );
}

// ── DeepSeek-style collapsible thinking block ────────────────────────────────
function ThinkingBlock({ thinking, seconds, isStreaming }: { thinking: string; seconds: number; isStreaming?: boolean }) {
  const [open, setOpen] = useState(true);

  return (
    <div className="mb-1">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <Scale className={`w-3.5 h-3.5 text-brand-mid ${isStreaming ? "animate-thinking" : ""}`} />
        <span className="font-medium">
          {isStreaming
            ? "Tenker..."
            : `Tenkte i ${seconds} sekund${seconds !== 1 ? "er" : ""}`}
        </span>
        <svg
          className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="mt-2 pl-4 border-l-2 border-border/60">
          <p className="text-xs text-muted-foreground/80 leading-relaxed whitespace-pre-wrap">
            {stripMarkdown(thinking)}
            {isStreaming && (
              <span className="inline-block w-[2px] h-[0.9em] bg-muted-foreground/50 ml-[1px] align-middle animate-pulse" />
            )}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Deep thinking indicator (DeepSeek-style rotating process phrases) ────────

// ── Attach menu (+ button) ───────────────────────────────────────────────────
function AttachMenu({
  fileInputRef,
}: {
  fileInputRef?: React.RefObject<HTMLInputElement | null>;
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ bottom: 0, left: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);

  function handleOpen() {
    if (btnRef.current) {
      const r = btnRef.current.getBoundingClientRect();
      setPos({ bottom: window.innerHeight - r.top + 8, left: r.left });
    }
    setOpen((v) => !v);
  }

  const items = [
    {
      icon: <Upload className="w-4 h-4" />,
      label: "Last opp fil fra PC",
      sub: "PDF, Word, Excel, bilde",
      action: () => { fileInputRef?.current?.click(); setOpen(false); },
    },
    {
      icon: <BookOpen className="w-4 h-4" />,
      label: "Fra kunnskapsbasen",
      sub: "Søk i indekserte dokumenter",
      action: () => { window.location.href = "/knowledge"; setOpen(false); },
    },
    {
      icon: <FileText className="w-4 h-4" />,
      label: "Anbud og tilbud",
      sub: "Naviger til anbudssiden",
      action: () => { window.location.href = "/tenders"; setOpen(false); },
    },
    {
      icon: <Link2 className="w-4 h-4" />,
      label: "Forsikringsdokumenter",
      sub: "Eksisterende poliser og avtaler",
      action: () => { window.location.href = "/knowledge"; setOpen(false); },
    },
  ];

  return (
    <div className="relative flex-shrink-0 mb-1">
      <button
        ref={btnRef}
        type="button"
        onClick={handleOpen}
        className="w-7 h-7 rounded-full border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-primary transition-colors"
        title="Legg til"
      >
        <Plus className="w-4 h-4" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div
            className="fixed z-50 bg-popover border border-border rounded-2xl shadow-xl w-64 py-2 overflow-hidden"
            style={{ bottom: pos.bottom, left: pos.left }}
          >
            {items.map((item) => (
              <button
                key={item.label}
                onClick={item.action}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-accent transition-colors text-left"
              >
                <span className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center text-foreground flex-shrink-0">
                  {item.icon}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground">{item.label}</p>
                  <p className="text-xs text-muted-foreground truncate">{item.sub}</p>
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ── Chat input sub-component ─────────────────────────────────────────────────
function ChatInput({
  value,
  onChange,
  onSend,
  onStop,
  loading,
  inputRef,
  attachedFile,
  onAttach,
  onRemoveAttachment,
  fileInputRef,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: (q: string) => void;
  onStop: () => void;
  loading: boolean;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  attachedFile?: File | null;
  onAttach?: (f: File) => void;
  onRemoveAttachment?: () => void;
  fileInputRef?: React.RefObject<HTMLInputElement | null>;
}) {
  const T = useT();

  function autoResize(el: HTMLTextAreaElement) {
    el.style.height = "auto";
    const maxH = 200;
    el.style.height = Math.min(el.scrollHeight, maxH) + "px";
    el.style.overflowY = el.scrollHeight > maxH ? "auto" : "hidden";
  }

  return (
    <div className="shadow-md rounded-2xl border border-border bg-card">
      {/* File chip */}
      {attachedFile && (
        <div className="flex items-center gap-1.5 mx-3 mt-2 px-2 py-1 bg-accent rounded-lg w-fit max-w-full">
          <FileText className="w-3.5 h-3.5 text-primary flex-shrink-0" />
          <span className="text-xs text-foreground truncate max-w-[200px]">{attachedFile.name}</span>
          {onRemoveAttachment && (
            <button onClick={onRemoveAttachment} className="text-muted-foreground hover:text-foreground ml-0.5">
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      )}

      <div className="flex items-end gap-1 px-2 py-2">
        {/* + inside the box */}
        <AttachMenu fileInputRef={fileInputRef} />
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx,.csv"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f && onAttach) onAttach(f);
            e.target.value = "";
          }}
        />
        <textarea
          ref={inputRef}
          className={`flex-1 resize-none bg-transparent focus:outline-none text-foreground placeholder:text-muted-foreground ${
            "flex-1 bg-transparent focus:outline-none text-foreground placeholder:text-muted-foreground text-sm py-1.5 px-1 resize-none overflow-hidden"
          }`}
          rows={1}
          style={{ minHeight: "36px" }}
          placeholder={T("Spør Jarvis om hva som helst...")}
          value={value}
          onChange={(e) => { onChange(e.target.value); autoResize(e.target); }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend(value);
            }
          }}
        />
        {loading ? (
          <button onClick={onStop} className="p-1.5 bg-red-500 text-white rounded-xl hover:bg-red-600 flex-shrink-0">
            <StopCircle className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={() => onSend(value)}
            disabled={!value.trim() && !attachedFile}
            className="p-1.5 bg-primary text-primary-foreground rounded-xl hover:bg-primary/80 disabled:opacity-40 flex-shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}

// ── File routing modal ────────────────────────────────────────────────────────
function FileRoutingModal({
  file,
  tenders,
  onClose,
  onDone,
}: {
  file: File;
  tenders: TenderListItem[];
  onClose: () => void;
  onDone: (summary: string) => void;
}) {
  const T = useT();
  const [uploading, setUploading] = useState(false);
  const [selectedTender, setSelectedTender] = useState<number | "">("");
  const [insurerName, setInsurerName] = useState("");

  async function handleRoute(dest: "knowledge" | "tender-offer" | "insurance-doc") {
    setUploading(true);
    try {
      if (dest === "knowledge") {
        await knowledgeQuickUpload(file);
        onDone(`Fil lastet opp til kunnskapsbasen: "${file.name}"`);
      } else if (dest === "tender-offer" && selectedTender) {
        await uploadTenderOffer(Number(selectedTender), file, insurerName || file.name);
        const t = tenders.find((x) => x.id === Number(selectedTender));
        onDone(`Forsikringstilbud "${file.name}" lastet opp til anbudet "${t?.title ?? selectedTender}"`);
      } else if (dest === "insurance-doc") {
        await uploadInsuranceDocument(file);
        onDone(`Forsikringsdokument "${file.name}" lagret`);
      }
    } catch {
      toast.error(T("Opplasting feilet"));
    } finally {
      setUploading(false);
      onClose();
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/30 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-sm">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <div>
            <p className="font-semibold text-sm text-foreground">Hvor skal filen lagres?</p>
            <p className="text-xs text-muted-foreground truncate mt-0.5">{file.name}</p>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-4 space-y-2">
          {/* Knowledge base */}
          <button
            onClick={() => handleRoute("knowledge")}
            disabled={uploading}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-border hover:border-primary hover:bg-accent transition-colors text-left"
          >
            <BookOpen className="w-5 h-5 text-primary flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-foreground">Kunnskapsbasen</p>
              <p className="text-xs text-muted-foreground">Indekseres og kan søkes av AI-assistenten</p>
            </div>
          </button>

          {/* Tender offer */}
          {tenders.length > 0 && (
            <div className="border border-border rounded-xl p-3 space-y-2">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-primary flex-shrink-0" />
                <p className="text-sm font-medium text-foreground">Forsikringstilbud på anbud</p>
              </div>
              <select
                value={selectedTender}
                onChange={(e) => setSelectedTender(e.target.value === "" ? "" : Number(e.target.value))}
                className="input-sm w-full text-xs"
              >
                <option value="">Velg anbud...</option>
                {tenders.filter((t) => t.status === "sent" || t.status === "closed").map((t) => (
                  <option key={t.id} value={t.id}>{t.title}</option>
                ))}
              </select>
              {selectedTender !== "" && (
                <input
                  className="input-sm w-full text-xs"
                  placeholder="Forsikringsselskap (valgfritt)"
                  value={insurerName}
                  onChange={(e) => setInsurerName(e.target.value)}
                />
              )}
              {selectedTender !== "" && (
                <button
                  onClick={() => handleRoute("tender-offer")}
                  disabled={uploading}
                  className="w-full px-3 py-1.5 bg-primary text-primary-foreground text-xs rounded-lg hover:bg-primary/80 disabled:opacity-50"
                >
                  {uploading ? "Laster opp..." : "Last opp tilbud"}
                </button>
              )}
            </div>
          )}

          {/* Insurance document */}
          <button
            onClick={() => handleRoute("insurance-doc")}
            disabled={uploading}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-border hover:border-primary hover:bg-accent transition-colors text-left"
          >
            <Folder className="w-5 h-5 text-primary flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-foreground">Forsikringsdokumenter</p>
              <p className="text-xs text-muted-foreground">Lagres som polise eller kontrakt</p>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}
