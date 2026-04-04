import { type NextRequest } from "next/server";

/**
 * Streaming proxy for GET /portfolio/{id}/ingest/stream (NDJSON).
 *
 * Why a Route Handler instead of the /bapi rewrite:
 * Next.js rewrites go through an internal proxy that may buffer the response
 * before forwarding. A Route Handler returns a raw ReadableStream, so chunks
 * from the FastAPI backend reach the browser the moment they are written —
 * no buffering, works identically in dev, Docker, and Azure Container Apps.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const includePdfs = request.nextUrl.searchParams.get("include_pdfs") === "true";

  const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000";
  const upstream = `${apiBase}/portfolio/${id}/ingest/stream${includePdfs ? "?include_pdfs=true" : ""}`;

  // Forward the auth token if present
  const authHeader = request.headers.get("authorization");

  const res = await fetch(upstream, {
    headers: {
      ...(authHeader ? { authorization: authHeader } : {}),
    },
    // Tell the runtime not to cache this response
    cache: "no-store",
  });

  if (!res.ok || !res.body) {
    return new Response(`Upstream error: ${res.status}`, { status: res.status });
  }

  return new Response(res.body, {
    status: 200,
    headers: {
      "Content-Type": "application/x-ndjson",
      // Disable any intermediate buffering (nginx, Azure Front Door, etc.)
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
