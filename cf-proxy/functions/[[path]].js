/**
 * Cloudflare Pages Function — reverse proxy for Broker Accelerator (Streamlit UI).
 *
 * HTTP: proxies with redirect rewriting + cookie domain stripping so Easy Auth
 *       session cookies are scoped to pages.dev (not the Azure origin).
 * WebSocket: uses fetch() so we can forward the session Cookie to Azure Easy Auth.
 *   (new WebSocket() can't set headers — the auth cookie would be missing and Azure
 *    would reject the /_stcore/stream upgrade with a 302 redirect, giving a blank app.)
 */

const UI_ORIGIN = "https://ca-ui.whitepebble-3ac25616.norwayeast.azurecontainerapps.io";
const UI_WS     = "wss://ca-ui.whitepebble-3ac25616.norwayeast.azurecontainerapps.io";
const UI_HOST   = "ca-ui.whitepebble-3ac25616.norwayeast.azurecontainerapps.io";
const PROXY_URL = "https://broker-accelerator.pages.dev";

export async function onRequest({ request }) {
  const upgrade = request.headers.get("Upgrade");
  if (upgrade && upgrade.toLowerCase() === "websocket") {
    return proxyWebSocket(request);
  }
  return proxyHttp(request);
}

// ── HTTP proxy with auth redirect rewriting + cookie domain stripping ─────────

async function proxyHttp(request) {
  const url    = new URL(request.url);
  const target = UI_ORIGIN + url.pathname + url.search;

  const headers = new Headers(request.headers);
  headers.set("Host", UI_HOST);
  headers.set("X-Forwarded-Host", "broker-accelerator.pages.dev");
  headers.set("X-Forwarded-Proto", "https");

  const response = await fetch(target, {
    method:   request.method,
    headers,
    body:     request.body,
    redirect: "manual",
  });

  if (response.status >= 300 && response.status < 400) {
    const location   = response.headers.get("Location") || "";
    const newHeaders = rewriteCookies(response.headers);
    newHeaders.set("Location", rewriteUrl(location));
    return new Response(null, { status: response.status, headers: newHeaders });
  }

  return new Response(response.body, {
    status:  response.status,
    headers: rewriteCookies(response.headers),
  });
}

/**
 * Strip the Domain= attribute from every Set-Cookie header so the browser
 * scopes each cookie to broker-accelerator.pages.dev instead of the Azure origin.
 * Without this, Easy Auth session cookies are stored for the wrong domain and
 * every proxied request looks unauthenticated to Azure.
 */
function rewriteCookies(responseHeaders) {
  const newHeaders = new Headers(responseHeaders);
  const cookies    = responseHeaders.getSetCookie?.() ?? [];
  if (cookies.length === 0) return newHeaders;

  newHeaders.delete("Set-Cookie");
  for (const cookie of cookies) {
    const cleaned = cookie
      .split(";")
      .map(p => p.trim())
      .filter(p => !p.toLowerCase().startsWith("domain="))
      .join("; ");
    newHeaders.append("Set-Cookie", cleaned);
  }
  return newHeaders;
}

function rewriteUrl(location) {
  if (!location) return location;
  if (location.startsWith(UI_ORIGIN)) {
    return PROXY_URL + location.slice(UI_ORIGIN.length);
  }
  if (location.includes("redirect_uri=")) {
    const enc = encodeURIComponent(UI_ORIGIN);
    if (location.includes(enc)) {
      return location.replaceAll(enc, encodeURIComponent(PROXY_URL));
    }
  }
  return location;
}

// ── WebSocket proxy — uses fetch() to forward auth cookies to Azure ───────────

async function proxyWebSocket(request) {
  const url    = new URL(request.url);
  const target = UI_ORIGIN + url.pathname + url.search;

  const headers = new Headers();
  headers.set("Host",              UI_HOST);
  headers.set("Upgrade",           "websocket");
  headers.set("Connection",        "Upgrade");
  headers.set("X-Forwarded-Host",  "broker-accelerator.pages.dev");
  headers.set("X-Forwarded-Proto", "https");

  const cookie = request.headers.get("Cookie");
  if (cookie) headers.set("Cookie", cookie);

  for (const [k, v] of request.headers) {
    if (k.toLowerCase().startsWith("sec-websocket")) headers.set(k, v);
  }

  const resp   = await fetch(target, { headers, method: "GET" });
  const origin = resp.webSocket;

  if (!origin) {
    return new Response(
      `WebSocket upstream failed: ${resp.status}`,
      { status: 502 }
    );
  }

  origin.accept();

  const [client, worker] = Object.values(new WebSocketPair());
  worker.accept();

  origin.addEventListener("message", (ev) => {
    try { worker.send(ev.data); } catch (_) {}
  });
  worker.addEventListener("message", (ev) => {
    try { origin.send(ev.data); } catch (_) {}
  });
  origin.addEventListener("close", (ev) => {
    try { worker.close(ev.code, ev.reason); } catch (_) {}
  });
  worker.addEventListener("close", (ev) => {
    try { origin.close(ev.code, ev.reason); } catch (_) {}
  });
  origin.addEventListener("error", () => {
    try { worker.close(1011, "origin error"); } catch (_) {}
  });

  return new Response(null, { status: 101, webSocket: client });
}
