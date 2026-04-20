"use client";

import { useState } from "react";
import {
  Search, Settings, Sparkles, BarChart3, FolderOpen, Video,
} from "lucide-react";
import DocumentsPanel from "@/components/knowledge/DocumentsPanel";
import VideosPanel from "@/components/knowledge/VideosPanel";

import ChatTab     from "./_tabs/ChatTab";
import SearchTab   from "./_tabs/SearchTab";
import AnalyseTab  from "./_tabs/AnalyseTab";
import ManageTab   from "./_tabs/ManageTab";
import { useT } from "@/lib/i18n";

type Tab = "chat" | "search" | "analyse" | "documents" | "videos" | "manage";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "chat",      label: "Chat",         icon: <Sparkles className="w-3.5 h-3.5" /> },
  { id: "search",    label: "Søk",          icon: <Search className="w-3.5 h-3.5" /> },
  { id: "analyse",   label: "Analyse",      icon: <BarChart3 className="w-3.5 h-3.5" /> },
  { id: "documents", label: "Dokumenter",   icon: <FolderOpen className="w-3.5 h-3.5" /> },
  { id: "videos",    label: "Videoer",      icon: <Video className="w-3.5 h-3.5" /> },
  { id: "manage",    label: "Administrer",  icon: <Settings className="w-3.5 h-3.5" /> },
];

export default function KnowledgePage() {
  const T = useT();
  // Read ?tab= so that /documents and /videos redirects can deep-link directly
  // to the right sub-tab. Falls back to "chat" for the bare /knowledge URL.
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    if (typeof window === "undefined") return "chat";
    const t = new URLSearchParams(window.location.search).get("tab");
    return (["chat","search","analyse","documents","videos","manage"] as const).includes(t as Tab) ? (t as Tab) : "chat";
  });

  const TAB_CLS = (t: Tab) =>
    `flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-colors cursor-pointer ${
      activeTab === t
        ? "bg-primary text-primary-foreground"
        : "text-muted-foreground hover:bg-muted"
    }`;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{T("Kunnskapsbase")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          AI-assistent, semantisk søk og indeksadministrasjon
        </p>
      </div>

      <div className="flex gap-2 flex-wrap">
        {TABS.map(({ id, label, icon }) => (
          <button key={id} onClick={() => setActiveTab(id)} className={TAB_CLS(id)}>
            {icon}
            {label}
          </button>
        ))}
      </div>

      {activeTab === "chat"      && <ChatTab />}
      {activeTab === "search"    && <SearchTab />}
      {activeTab === "analyse"   && <AnalyseTab />}
      {activeTab === "documents" && <DocumentsPanel />}
      {activeTab === "videos"    && <VideosPanel />}
      {activeTab === "manage"    && <ManageTab />}
    </div>
  );
}
