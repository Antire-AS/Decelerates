"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  AlertCircle,
  AtSign,
  Calendar,
  FileWarning,
  ShieldCheck,
  Trophy,
  Inbox,
} from "lucide-react";
import {
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  type NotificationOut,
} from "@/lib/api";

/**
 * Bell-icon dropdown — plan §🟢 #17.
 *
 * Polls /notifications?unread_only=true every 60s. When the user opens the
 * dropdown we switch to a one-shot fetch of the recent 20 (regardless of
 * read state) so the panel shows context, not just unread.
 *
 * Click → navigate to `link` and mark read in one round-trip.
 */
const POLL_INTERVAL_MS = 60_000;
const PANEL_LIMIT = 20;

const KIND_ICON: Record<string, React.ElementType> = {
  renewal:          Calendar,
  activity_overdue: AlertCircle,
  mention:          AtSign,
  claim_new:        FileWarning,
  deal_won:         Trophy,
  coverage_gap:     ShieldCheck,
  digest:           Inbox,
};

export function NotificationBell() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationOut[]>([]);
  const [unread, setUnread] = useState(0);
  const [loadingPanel, setLoadingPanel] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Background poll for unread count. Cheap query — only fetches unread rows.
  useEffect(() => {
    let cancelled = false;
    async function fetchCount() {
      try {
        const r = await getNotifications({ unread_only: true, limit: 1 });
        if (!cancelled) setUnread(r.unread_count);
      } catch {
        // Silent — bell badge is best-effort.
      }
    }
    fetchCount();
    const timer = setInterval(fetchCount, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  // Click-outside to close.
  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  // Fetch the recent panel contents whenever the dropdown opens.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoadingPanel(true);
    (async () => {
      try {
        const r = await getNotifications({ limit: PANEL_LIMIT });
        if (!cancelled) {
          setItems(r.items);
          setUnread(r.unread_count);
        }
      } catch {
        // Silent — empty panel is the fallback.
      } finally {
        if (!cancelled) setLoadingPanel(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  async function handleClickItem(n: NotificationOut) {
    setOpen(false);
    if (!n.read) {
      // Optimistically flip — the API call below reconciles in the background.
      setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, read: true } : x)));
      setUnread((prev) => Math.max(0, prev - 1));
      try {
        await markNotificationRead(n.id);
      } catch {
        // Silent — worst case the next poll will repair the count.
      }
    }
    if (n.link) router.push(n.link);
  }

  async function handleMarkAllRead() {
    try {
      const r = await markAllNotificationsRead();
      setUnread(0);
      setItems((prev) => prev.map((x) => ({ ...x, read: true })));
      // Brief touch on r so the linter doesn't complain about the ignored value.
      void r.updated;
    } catch {
      // Silent.
    }
  }

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Notifications"
        className="relative p-2 rounded-lg hover:bg-[#EDE8E3] transition-colors text-[#2C3E50]"
      >
        <Bell className="w-4 h-4" />
        {unread > 0 && (
          <span className="absolute top-0.5 right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-semibold flex items-center justify-center">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-80 sm:w-96 bg-white border border-[#EDE8E3] rounded-lg shadow-xl z-50 overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-[#EDE8E3]">
            <p className="text-sm font-semibold text-[#2C3E50]">Varsler</p>
            {unread > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs text-[#4A6FA5] hover:text-[#3d5e8e]"
              >
                Marker alle som lest
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {loadingPanel && (
              <p className="p-4 text-xs text-[#8A7F74] text-center">Laster…</p>
            )}
            {!loadingPanel && items.length === 0 && (
              <p className="p-6 text-xs text-[#8A7F74] text-center">Ingen varsler ennå.</p>
            )}
            {items.map((n) => {
              const Icon = KIND_ICON[n.kind] ?? Bell;
              return (
                <button
                  key={n.id}
                  onClick={() => handleClickItem(n)}
                  className={`w-full text-left px-3 py-2.5 border-b border-[#EDE8E3] last:border-0 hover:bg-[#F9F7F4] transition-colors flex items-start gap-2.5
                              ${n.read ? "" : "bg-blue-50/40"}`}
                >
                  <Icon className={`w-4 h-4 flex-shrink-0 mt-0.5 ${n.read ? "text-[#C4BDB4]" : "text-[#4A6FA5]"}`} />
                  <div className="min-w-0 flex-1">
                    <p className={`text-xs font-semibold truncate ${n.read ? "text-[#8A7F74]" : "text-[#2C3E50]"}`}>
                      {n.title}
                    </p>
                    {n.message && (
                      <p className="text-[10px] text-[#8A7F74] truncate">{n.message}</p>
                    )}
                    <p className="text-[10px] text-[#C4BDB4] mt-0.5">
                      {new Date(n.created_at).toLocaleString("nb-NO", {
                        day: "2-digit",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                  {!n.read && (
                    <span className="w-1.5 h-1.5 rounded-full bg-[#4A6FA5] flex-shrink-0 mt-1.5" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
