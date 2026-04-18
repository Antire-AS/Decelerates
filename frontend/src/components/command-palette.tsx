"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Search as SearchIcon,
  Folder,
  BarChart3,
  RotateCcw,
  Kanban,
  BookOpen,
  FileSignature,
  ClipboardCheck,
  Building2,
  Lightbulb,
  UserPlus,
  ClipboardList,
  FileText,
  Video,
  Banknote,
  Shield,
  LogIn,
} from "lucide-react";

import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandGroup,
  CommandItem,
  CommandEmpty,
} from "@/components/ui/command";
import { searchCompanies } from "@/lib/api";

type RouteItem = { href: string; label: string; icon: React.ReactNode };

const ROUTES: RouteItem[] = [
  { href: "/dashboard",           label: "Dashboard",               icon: <LayoutDashboard className="h-4 w-4" /> },
  { href: "/search",              label: "Søk",                      icon: <SearchIcon className="h-4 w-4" /> },
  { href: "/portfolio",           label: "Porteføljer",              icon: <Folder className="h-4 w-4" /> },
  { href: "/portfolio/analytics", label: "Porteføljeanalyse",        icon: <BarChart3 className="h-4 w-4" /> },
  { href: "/renewals",            label: "Fornyelser",               icon: <RotateCcw className="h-4 w-4" /> },
  { href: "/pipeline",            label: "Pipeline",                 icon: <Kanban className="h-4 w-4" /> },
  { href: "/knowledge",           label: "Kunnskapsbase",            icon: <BookOpen className="h-4 w-4" /> },
  { href: "/sla",                 label: "Tjenesteavtaler",          icon: <FileSignature className="h-4 w-4" /> },
  { href: "/idd",                 label: "IDD Behovsanalyse",        icon: <ClipboardCheck className="h-4 w-4" /> },
  { href: "/insurers",            label: "Forsikringsselskaper",     icon: <Building2 className="h-4 w-4" /> },
  { href: "/recommendations",     label: "Anbefalinger",             icon: <Lightbulb className="h-4 w-4" /> },
  { href: "/prospecting",         label: "Prospektering",            icon: <UserPlus className="h-4 w-4" /> },
  { href: "/tenders",             label: "Anbud",                    icon: <ClipboardList className="h-4 w-4" /> },
  { href: "/documents",           label: "Dokumenter",               icon: <FileText className="h-4 w-4" /> },
  { href: "/videos",              label: "Videoer",                  icon: <Video className="h-4 w-4" /> },
  { href: "/finans",              label: "Finans",                   icon: <Banknote className="h-4 w-4" /> },
  { href: "/admin",               label: "Admin",                    icon: <Shield className="h-4 w-4" /> },
  { href: "/login",               label: "Logg inn",                 icon: <LogIn className="h-4 w-4" /> },
];

interface CompanyHit {
  orgnr: string;
  navn?: string;
}

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [hits, setHits] = React.useState<CompanyHit[]>([]);
  const [loading, setLoading] = React.useState(false);

  // Global ⌘K / Ctrl+K keybind
  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  // Debounced company search. We use `searchCompanies(name, size)` which hits
  // `/search?name=` — the existing BRREG-backed company search endpoint. The
  // AbortController is checked before each setState so stale requests cannot
  // overwrite the current query's results.
  React.useEffect(() => {
    if (!query || query.length < 2) {
      setHits([]);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const results = await searchCompanies(query, 8);
        if (!controller.signal.aborted) {
          setHits(
            results.map((c) => ({
              orgnr: c.orgnr,
              navn: c.navn,
            })),
          );
        }
      } catch {
        if (!controller.signal.aborted) setHits([]);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 200);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [query]);

  const go = React.useCallback(
    (href: string) => {
      setOpen(false);
      setQuery("");
      router.push(href);
    },
    [router],
  );

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder="Søk etter selskap eller side…"
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>
          {loading ? "Søker…" : "Ingen treff."}
        </CommandEmpty>

        {hits.length > 0 && (
          <CommandGroup heading="Selskaper">
            {hits.map((h) => (
              <CommandItem
                key={h.orgnr}
                value={`company-${h.orgnr}-${h.navn ?? ""}`}
                onSelect={() => go(`/search/${h.orgnr}`)}
              >
                <Building2 className="mr-2 h-4 w-4" />
                <span className="flex-1">{h.navn ?? h.orgnr}</span>
                <span className="text-xs text-muted-foreground">{h.orgnr}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        <CommandGroup heading="Sider">
          {ROUTES.map((r) => (
            <CommandItem
              key={r.href}
              value={`route-${r.href}-${r.label}`}
              onSelect={() => go(r.href)}
            >
              <span className="mr-2">{r.icon}</span>
              <span>{r.label}</span>
              <span className="ml-auto text-xs text-muted-foreground">{r.href}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
