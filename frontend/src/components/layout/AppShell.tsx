"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { useI18n } from "@/lib/i18n";
import {
  LayoutDashboard,
  Search,
  BarChart2,
  TrendingUp,
  RotateCcw,
  FileText,
  FolderOpen,
  Video,
  BookOpen,
  Settings,
  Globe,
  Scale,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/dashboard",  label: "Hjem",          icon: LayoutDashboard },
  { href: "/search",     label: "Selskapsøk",    icon: Search },
  { href: "/portfolio",  label: "Portefølje",    icon: BarChart2 },
  { href: "/finans",     label: "Finans",        icon: TrendingUp },
  { href: "/renewals",   label: "Fornyelser",    icon: RotateCcw },
  { href: "/sla",        label: "Avtaler",       icon: FileText },
  { href: "/documents",  label: "Dokumenter",    icon: FolderOpen },
  { href: "/videos",     label: "Videoer",       icon: Video },
  { href: "/knowledge",  label: "Kunnskapsbase", icon: BookOpen },
  { href: "/admin",      label: "Admin",         icon: Settings },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { lang, setLang } = useI18n();

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="w-56 flex-shrink-0 bg-[#F5F0EB] border-r border-[#D4C9B8] flex flex-col">
        {/* Logo */}
        <div className="px-4 py-5 border-b border-[#D4C9B8]">
          <div className="flex items-center gap-2">
            <Scale className="w-6 h-6 text-[#4A6FA5]" />
            <div>
              <p className="text-sm font-bold text-[#2C3E50] leading-tight">Broker</p>
              <p className="text-xs text-[#8A7F74] leading-tight">Accelerator</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "nav-item",
                pathname.startsWith(href) && "nav-item-active",
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{label}</span>
            </Link>
          ))}
        </nav>

        {/* Language toggle */}
        <div className="px-3 py-3 border-t border-[#D4C9B8]">
          <button
            onClick={() => setLang(lang === "no" ? "en" : "no")}
            className="nav-item w-full"
          >
            <Globe className="w-4 h-4 flex-shrink-0" />
            <span>{lang === "no" ? "🇳🇴 Norsk" : "🇬🇧 English"}</span>
          </button>
        </div>
      </aside>

      {/* ── Main content ────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto bg-[#F5F0EB]">
        <div className="max-w-7xl mx-auto px-6 py-6">
          {children}
        </div>
      </main>
    </div>
  );
}
