// ── Shared API utility helpers ────────────────────────────────────────────────

/**
 * Resolve the FastAPI base URL.
 *
 * - On the server (Server Components, Route Handlers, server actions) we read
 *   `API_BASE_URL` directly so we don't bounce through the Next rewrite.
 * - In the browser we always go through `/bapi`, which next.config.ts rewrites
 *   to the real backend.
 *
 * Pass `clientBase: "absolute"` to also use `NEXT_PUBLIC_API_URL` in the browser
 * (used by Leaflet which needs absolute URLs for tile fetching, not the rewrite).
 */
export function apiBaseUrl(clientBase: "rewrite" | "absolute" = "rewrite"): string {
  if (typeof window === "undefined") {
    return process.env.API_BASE_URL ?? "http://localhost:8000";
  }
  if (clientBase === "absolute") {
    return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  }
  return "/bapi";
}

/**
 * Download a file from a URL by fetching it as a blob and triggering a
 * browser download via a temporary anchor element.
 */
export async function downloadFile(url: string, filename: string): Promise<void> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`PDF download failed: ${res.status}`);
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(objectUrl);
}
