"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { cn } from "@/lib/cn";
import { useI18n } from "@/lib/i18n";
import {
  LayoutDashboard,
  Search,
  BarChart2,
  RotateCcw,
  FileText,
  BookOpen,
  Settings,
  Globe,
  Scale,
  LogOut,
  User,
  HelpCircle,
  Building2,
  Crosshair,
  Menu,
  X,
} from "lucide-react";
import OnboardingTour from "./OnboardingTour";

// IA cleanup (2026-04):
//   - /documents and /videos are now sub-tabs of /knowledge
//   - /finans is now /portfolio/analytics
//   - /recommendations now lives inside the company profile CRM tab
// The standalone routes still exist as redirects so old bookmarks work.
const NAV_ITEMS = [
  { href: "/dashboard",   label: "Hjem",                 icon: LayoutDashboard },
  { href: "/search",      label: "Selskapsøk",           icon: Search },
  { href: "/portfolio",   label: "Portefølje",           icon: BarChart2 },
  { href: "/prospecting", label: "Prospektering",        icon: Crosshair },
  { href: "/renewals",    label: "Fornyelser",           icon: RotateCcw },
  { href: "/idd",         label: "IDD / Behov",          icon: Scale },
  { href: "/insurers",    label: "Forsikringsselskaper", icon: Building2 },
  { href: "/sla",         label: "Avtaler",              icon: FileText },
  { href: "/knowledge",   label: "Kunnskapsbase",        icon: BookOpen },
  { href: "/admin",       label: "Admin",                icon: Settings },
];

function SidebarContent({
  pathname,
  lang,
  setLang,
  session,
  onNavClick,
}: {
  pathname: string;
  lang: "no" | "en";
  setLang: (l: "no" | "en") => void;
  session: ReturnType<typeof useSession>["data"];
  onNavClick?: () => void;
}) {
  return (
    <>
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
            onClick={onNavClick}
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

      {/* Language toggle + user */}
      <div className="px-3 py-3 border-t border-[#D4C9B8] space-y-1">
        <button
          onClick={() => (window as { __openOnboarding?: () => void }).__openOnboarding?.()}
          className="nav-item w-full"
        >
          <HelpCircle className="w-4 h-4 flex-shrink-0" />
          <span>Veiledning</span>
        </button>
        <button
          onClick={() => setLang(lang === "no" ? "en" : "no")}
          className="nav-item w-full"
        >
          <Globe className="w-4 h-4 flex-shrink-0" />
          <span>{lang === "no" ? "🇳🇴 Norsk" : "🇬🇧 English"}</span>
        </button>

        {session?.user && (
          <>
            <div className="nav-item pointer-events-none opacity-70">
              <User className="w-4 h-4 flex-shrink-0" />
              <span className="truncate text-xs">{session.user.email ?? session.user.name}</span>
            </div>
            <button
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="nav-item w-full text-red-500 hover:text-red-600"
            >
              <LogOut className="w-4 h-4 flex-shrink-0" />
              <span>Logg ut</span>
            </button>
          </>
        )}
      </div>
    </>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Public routes (client portal) — render without the broker shell
  if (pathname.startsWith("/portal")) {
    return <>{children}</>;
  }

  const { lang, setLang } = useI18n();
  const { data: session } = useSession();

  const sidebarProps = { pathname, lang, setLang, session };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Desktop sidebar (md+) ─────────────────────────────────────── */}
      <aside className="hidden md:flex w-56 flex-shrink-0 bg-[#F5F0EB] border-r border-[#D4C9B8] flex-col">
        <SidebarContent {...sidebarProps} />
      </aside>

      {/* ── Mobile drawer overlay ──────────────────────────────────────── */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ── Mobile drawer panel ───────────────────────────────────────── */}
      <aside className={cn(
        "fixed inset-y-0 left-0 z-50 w-64 flex flex-col bg-[#F5F0EB] border-r border-[#D4C9B8] transition-transform duration-200 md:hidden",
        mobileOpen ? "translate-x-0" : "-translate-x-full",
      )}>
        <SidebarContent {...sidebarProps} onNavClick={() => setMobileOpen(false)} />
      </aside>

      <OnboardingTour />

      {/* ── Main content ────────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Mobile top bar */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 bg-[#F5F0EB] border-b border-[#D4C9B8] flex-shrink-0">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-1.5 rounded-lg text-[#2C3E50] hover:bg-[#EDE8E3]"
            aria-label="Åpne meny"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <Scale className="w-4 h-4 text-[#4A6FA5]" />
            <span className="text-sm font-bold text-[#2C3E50]">Broker Accelerator</span>
          </div>
          {mobileOpen && (
            <button
              onClick={() => setMobileOpen(false)}
              className="ml-auto p-1.5 rounded-lg text-[#2C3E50] hover:bg-[#EDE8E3]"
              aria-label="Lukk meny"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </header>

        <main className="flex-1 overflow-y-auto bg-[#F5F0EB]">
          <div className="max-w-7xl mx-auto px-4 md:px-6 py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
