/**
 * Cloudflare Pages Function — catch-all proxy for Broker Accelerator (Streamlit UI).
 *
 * Handles both HTTP and WebSocket traffic (Streamlit uses WS for /_stcore/stream).
 *
 * URL after deploy: https://broker-accelerator.pages.dev
 */

const UI_ORIGIN = "https://ca-ui.whitepebble-3ac25616.norwayeast.azurecontainerapps.io";
const UI_WS     = "wss://ca-ui.whitepebble-3ac25616.norwayeast.azurecontainerapps.io";
const UI_HOST   = "ca-ui.whitepebble-3ac25616.norwayeast.azurecontainerapps.io";

export async function onRequest({ request }) {
  const upgrade = request.headers.get("Upgrade");
  if (upgrade && upgrade.toLowerCase() === "websocket") {
    return proxyWebSocket(request);
  }
  return proxyHttp(request);
}

async function proxyHttp(request) {
  const url    = new URL(request.url);
  const target = UI_ORIGIN + url.pathname + url.search;

  const headers = new Headers(request.headers);
  headers.set("Host", UI_HOST);

  const response = await fetch(target, {
    method:   request.method,
    headers,
    body:     request.body,
    redirect: "follow",
  });

  return new Response(response.body, {
    status:  response.status,
    headers: response.headers,
  });
}

function proxyWebSocket(request) {
  const url      = new URL(request.url);
  const targetWs = UI_WS + url.pathname + url.search;

  const [client, worker] = Object.values(new WebSocketPair());
  worker.accept();

  const origin = new WebSocket(targetWs);

  origin.addEventListener("message", (ev) => {
    try { worker.send(ev.data); } catch (_) {}
  });

  const queue = [];
  worker.addEventListener("message", (ev) => {
    if (origin.readyState === WebSocket.OPEN) {
      origin.send(ev.data);
    } else {
      queue.push(ev.data);
    }
  });

  origin.addEventListener("open", () => {
    for (const msg of queue) origin.send(msg);
    queue.length = 0;
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
