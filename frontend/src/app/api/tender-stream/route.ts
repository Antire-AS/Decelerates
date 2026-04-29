import { NextRequest } from "next/server";

// Force dynamic — this is a streaming proxy, never cache
export const dynamic = "force-dynamic";

/**
 * Server-side proxy for the SSE tender-stream endpoint.
 *
 * The browser calls /api/tender-stream instead of /bapi/knowledge/tender-stream
 * because the Next.js dev-server HTTP proxy buffers SSE responses, causing all
 * events to arrive at once at the end. This Route Handler calls the backend
 * directly (server-to-server via API_BASE_URL) and passes the ReadableStream
 * body straight through — no buffering.
 */
export async function POST(req: NextRequest) {
  const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000";
  const auth = req.headers.get("Authorization") ?? "";

  const upstream = await fetch(`${apiBase}/knowledge/tender-stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(auth ? { Authorization: auth } : {}),
    },
    body: req.body,
    // Required for Node.js fetch to stream the request body
    // @ts-expect-error — duplex not in TS fetch types yet
    duplex: "half",
  });

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
