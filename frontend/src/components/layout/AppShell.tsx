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
  PlayCircle,
  Building2,
  Crosshair,
  Menu,
  Trello,
  X,
} from "lucide-react";
import OnboardingTour from "./OnboardingTour";
import { NotificationBell } from "./NotificationBell";

// IA cleanup (2026-04):
//   - /documents and /videos are now sub-tabs of /knowledge
//   - /finans is now /portfolio/analytics
//   - /recommendations now lives inside the company profile CRM tab
// The standalone routes still exist as redirects so old bookmarks work.
const NAV_ITEMS = [
  { href: "/dashboard",   label: "Hjem",                 icon: LayoutDashboard },
  { href: "/search",      label: "Selskapsøk",           icon: Search },
  { href: "/pipeline",    label: "Pipeline",             icon: Trello },
  { href: "/portfolio",   label: "Portefølje",           icon: BarChart2 },
  { href: "/prospecting", label: "Prospektering",        icon: Crosshair },
  { href: "/renewals",    label: "Fornyelser",           icon: RotateCcw },
  { href: "/tenders",     label: "Anbud",                icon: FileText },
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
      <div className="px-4 py-5 border-b border-brand-stone">
        <div className="flex items-center gap-2">
          <Scale className="w-6 h-6 text-brand-mid" />
          <div>
            <p className="text-sm font-bold text-brand-dark leading-tight">Broker</p>
            <p className="text-xs text-brand-muted leading-tight">Accelerator</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const isActive = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavClick}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "nav-item",
                isActive && "nav-item-active",
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Language toggle + user */}
      <div className="px-3 py-3 border-t border-brand-stone space-y-1">
        <button
          onClick={() => (window as { __openOnboarding?: () => void }).__openOnboarding?.()}
          className="nav-item w-full"
        >
          <HelpCircle className="w-4 h-4 flex-shrink-0" />
          <span>Veiledning</span>
        </button>
        <button
          onClick={() => (window as { __openDemoVideo?: () => void }).__openDemoVideo?.()}
          className="nav-item w-full"
        >
          <PlayCircle className="w-4 h-4 flex-shrink-0" />
          <span>Demo-video</span>
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
  // Hooks MUST be called unconditionally before any early return, otherwise
  // navigating between /portal and the broker shell triggers a Rules-of-Hooks
  // crash because React sees a different hook count on re-render.
  const { lang, setLang } = useI18n();
  const { data: session } = useSession();

  // Public routes (client portal) — render without the broker shell
  if (pathname.startsWith("/portal")) {
    return <>{children}</>;
  }

  const sidebarProps = { pathname, lang, setLang, session };

  return (
    <div className="flex h-screen overflow-hidden">
      <a href="#main-content" className="skip-to-content">
        Hopp til hovedinnhold
      </a>
      {/* ── Desktop sidebar (md+) ─────────────────────────────────────── */}
      <aside className="hidden md:flex w-56 flex-shrink-0 bg-brand-beige border-r border-brand-stone flex-col">
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
        "fixed inset-y-0 left-0 z-50 w-64 flex flex-col bg-brand-beige border-r border-brand-stone transition-transform duration-200 md:hidden",
        mobileOpen ? "translate-x-0" : "-translate-x-full",
      )}>
        <SidebarContent {...sidebarProps} onNavClick={() => setMobileOpen(false)} />
      </aside>

      <OnboardingTour />

      {/* ── Main content ────────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Mobile top bar — bell sits next to the menu button. */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 bg-brand-beige border-b border-brand-stone flex-shrink-0">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-1.5 rounded-lg text-brand-dark hover:bg-[#EDE8E3]"
            aria-label="Åpne meny"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <Scale className="w-4 h-4 text-brand-mid" />
            <span className="text-sm font-bold text-brand-dark">Broker Accelerator</span>
          </div>
          <div className="ml-auto flex items-center gap-1">
            <NotificationBell />
            {mobileOpen && (
              <button
                onClick={() => setMobileOpen(false)}
                className="p-1.5 rounded-lg text-brand-dark hover:bg-[#EDE8E3]"
                aria-label="Lukk meny"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        </header>

        {/* Desktop top bar — minimal, right-aligned bell only (sidebar owns everything else). */}
        <header className="hidden md:flex items-center justify-end px-6 py-2 bg-brand-beige border-b border-brand-stone flex-shrink-0">
          <NotificationBell />
        </header>

        <main id="main-content" tabIndex={-1} className="flex-1 overflow-y-auto bg-brand-beige focus:outline-none">
          <div className="max-w-7xl mx-auto px-4 md:px-6 py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
