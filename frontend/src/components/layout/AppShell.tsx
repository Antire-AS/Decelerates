"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import useSWR from "swr";
import { listTenderSessions, deleteTenderSession, type TenderChatSession } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useI18n, useT } from "@/lib/i18n";
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
  KanbanSquare,
  X,
  MessageSquare,
  Plus,
  Trash2,
} from "lucide-react";
import OnboardingTour from "./OnboardingTour";
import GlobalChatButton from "./GlobalChatButton";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { NotificationBell } from "./NotificationBell";
import { ThemeToggle } from "@/components/theme-toggle";
import { A11yPanel } from "@/components/a11y/a11y-panel";
import { CommandPalette } from "@/components/command-palette";
import { LocaleSwitcher } from "@/components/locale-switcher";

// IA cleanup (2026-04):
//   - /documents and /videos are now sub-tabs of /knowledge
//   - /finans is now /portfolio/analytics
//   - /recommendations now lives inside the company profile CRM tab
// The standalone routes still exist as redirects so old bookmarks work.
//
// Sidebar grouping (2026-04-29 — from megler-bilder mockup 135259):
// ARBEID = day-to-day broker workflow, SALG = pipeline + prospecting,
// COMPLIANCE = regulatory + insurer relationships, SYSTEM = reference + admin.
type NavSection = "ARBEID" | "SALG" | "COMPLIANCE" | "SYSTEM";
const NAV_ITEMS: { href: string; label: string; icon: React.ComponentType<{className?: string}>; section: NavSection }[] = [
  { href: "/dashboard",   label: "Hjem",                 icon: LayoutDashboard, section: "ARBEID" },
  { href: "/search",      label: "Selskapsøk",           icon: Search,          section: "ARBEID" },
  { href: "/pipeline",    label: "Pipeline",             icon: KanbanSquare,    section: "ARBEID" },
  { href: "/portfolio",   label: "Portefølje",           icon: BarChart2,       section: "ARBEID" },
  { href: "/prospecting", label: "Prospektering",        icon: Crosshair,       section: "SALG" },
  { href: "/renewals",    label: "Fornyelser",           icon: RotateCcw,       section: "SALG" },
  { href: "/tenders",     label: "Anbud",                icon: FileText,        section: "SALG" },
  { href: "/idd",         label: "IDD / Behov",          icon: Scale,           section: "COMPLIANCE" },
  { href: "/insurers",    label: "Forsikringsselskaper", icon: Building2,       section: "COMPLIANCE" },
  { href: "/sla",         label: "Avtaler",              icon: FileText,        section: "COMPLIANCE" },
  { href: "/knowledge",   label: "Kunnskapsbase",        icon: BookOpen,        section: "SYSTEM" },
  { href: "/admin",       label: "Admin",                icon: Settings,        section: "SYSTEM" },
];

const SECTION_ORDER: NavSection[] = ["ARBEID", "SALG", "COMPLIANCE", "SYSTEM"];

function TenderSessionsNav({ onNavClick }: { onNavClick?: () => void }) {
  const [pinnedId, setPinnedId] = useState<number | null>(() => {
    if (typeof window === "undefined") return null;
    return Number(new URLSearchParams(window.location.search).get("session")) || null;
  });
  const [confirmId, setConfirmId] = useState<number | null>(null);

  const { data: rawSessions, mutate } = useSWR<TenderChatSession[]>(
    "tender-sessions-nav",
    listTenderSessions,
    { refreshInterval: 30000 },
  );

  const sessions = useMemo(() => {
    if (!rawSessions) return [];
    if (!pinnedId) return rawSessions;
    const pinned = rawSessions.find((s) => s.id === pinnedId);
    if (!pinned) return rawSessions;
    return [pinned, ...rawSessions.filter((s) => s.id !== pinnedId)];
  }, [rawSessions, pinnedId]);

  if (!sessions.length) return null;

  function handleClick(id: number) {
    setPinnedId(id);
  }

  function requestDelete(id: number, e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setConfirmId(id);
  }

  async function confirmDelete() {
    if (!confirmId) return;
    await deleteTenderSession(confirmId).catch(() => {});
    setConfirmId(null);
    mutate();
  }

  return (
    <>
    <div className="px-2 pb-2 border-t border-border pt-2">
      <div className="flex items-center justify-between px-2 mb-1">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground flex items-center gap-1">
          <MessageSquare className="w-3 h-3" /> Samtaler
        </span>
        <Link
          href="/tenders"
          onClick={onNavClick}
          className="text-muted-foreground hover:text-primary"
          title="Ny samtale"
        >
          <Plus className="w-3 h-3" />
        </Link>
      </div>
      <div className="max-h-36 overflow-y-auto space-y-0.5 sidebar-sessions-scroll">
        {sessions.map((s) => (
          <Link
            key={s.id}
            href={`/tenders?session=${s.id}`}
            onClick={() => { handleClick(s.id); onNavClick?.(); }}
            className={cn(
              "group flex items-center justify-between px-2 py-1.5 rounded text-xs transition-colors",
              s.id === pinnedId
                ? "bg-muted text-foreground font-medium"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <span className="truncate flex-1">{s.title}</span>
            <button
              onClick={(e) => requestDelete(s.id, e)}
              className="opacity-0 group-hover:opacity-100 hover:text-red-500 flex-shrink-0 ml-1"
              title="Slett samtale"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </Link>
        ))}
      </div>
    </div>

    <ConfirmDialog
      open={confirmId !== null}
      onOpenChange={(o: boolean) => { if (!o) setConfirmId(null); }}
      title="Slett denne samtalen?"
      description="Handlingen kan ikke angres."
      confirmLabel="Slett"
      destructive
      onConfirm={confirmDelete}
    />
    </>
  );
}

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
  const T = useT();
  return (
    <>
      {/* Logo */}
      <div className="px-4 py-5 border-b border-border">
        <div className="flex items-center gap-2">
          <Scale className="w-6 h-6 text-brand-mid" />
          <div>
            <p className="text-sm font-bold text-brand-dark leading-tight">Broker</p>
            <p className="text-xs text-brand-muted leading-tight">Accelerator</p>
          </div>
        </div>
      </div>

      {/* Nav — grouped by lifecycle section (ARBEID / SALG / COMPLIANCE / SYSTEM) */}
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {SECTION_ORDER.map((section) => {
          const items = NAV_ITEMS.filter((it) => it.section === section);
          if (items.length === 0) return null;
          return (
            <div key={section} className="mb-3 last:mb-0">
              <h3 className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {section}
              </h3>
              <div className="space-y-0.5">
                {items.map(({ href, label, icon: Icon }) => {
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
                      <span>{T(label)}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      {/* Tender chat sessions — shown only on /tenders routes */}
      <TenderSessionsNav onNavClick={onNavClick} />

      {/* Spacer pushes footer to bottom */}
      <div className="flex-1" />

      {/* Footer */}
      <div className="px-2 py-2 border-t border-border space-y-0.5">
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

  // Public routes — render without the broker shell.
  // /portal: token-based customer view (no NextAuth session)
  // /login:  pre-auth screen, must be centered without sidebar offset
  if (pathname.startsWith("/portal") || pathname === "/login") {
    return <>{children}</>;
  }

  const sidebarProps = { pathname, lang, setLang, session };

  return (
    <div className="flex h-screen overflow-hidden">
      <a href="#main-content" className="skip-to-content">
        Hopp til hovedinnhold
      </a>
      {/* Global ⌘K command palette — mounted once, listens for its own keybind. */}
      <CommandPalette />
      {/* ── Desktop sidebar (md+) ─────────────────────────────────────── */}
      <aside className="hidden md:flex w-56 flex-shrink-0 bg-background border-r border-border flex-col">
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
        "fixed inset-y-0 left-0 z-50 w-64 flex flex-col bg-background border-r border-border transition-transform duration-200 md:hidden",
        mobileOpen ? "translate-x-0" : "-translate-x-full",
      )}>
        <SidebarContent {...sidebarProps} onNavClick={() => setMobileOpen(false)} />
      </aside>

      <OnboardingTour />
      {!pathname.startsWith("/tenders") && <GlobalChatButton />}

      {/* ── Main content ────────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Mobile top bar — bell sits next to the menu button. */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 bg-background border-b border-border flex-shrink-0">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-1.5 rounded-lg text-foreground hover:bg-muted"
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
            <LocaleSwitcher />
            <A11yPanel />
            <ThemeToggle />
            {mobileOpen && (
              <button
                onClick={() => setMobileOpen(false)}
                className="p-1.5 rounded-lg text-foreground hover:bg-muted"
                aria-label="Lukk meny"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        </header>

        {/* Desktop top bar — minimal, right-aligned bell + theme toggle (sidebar owns everything else). */}
        <header className="hidden md:flex items-center justify-end gap-2 px-6 py-2 bg-background border-b border-border flex-shrink-0">
          <button
            onClick={() => {
              // Dispatch a synthetic ⌘K keydown — the CommandPalette's global
              // listener handles the open/close toggle itself.
              document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
            }}
            className="hidden md:inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent"
            aria-label="Åpne kommandopalett"
          >
            <Search className="h-3 w-3" />
            Søk…
            <kbd className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium">⌘K</kbd>
          </button>
          <NotificationBell />
          <LocaleSwitcher />
          <A11yPanel />
          <ThemeToggle />
        </header>

        <main id="main-content" tabIndex={-1} className="flex-1 overflow-y-auto bg-background focus:outline-none">
          <div className="max-w-7xl mx-auto px-4 md:px-6 py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
