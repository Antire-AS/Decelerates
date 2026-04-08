import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // NOTE: a previous version set outputFileTracingRoot here to suppress the
  // "multiple lockfiles" warning from a stray root-level package-lock.json.
  // That setting changed the standalone build output structure: server.js
  // moved from /app/.next/standalone/server.js to a nested path, which broke
  // `docker/Dockerfile.frontend`'s `CMD ["node", "server.js"]` and made every
  // production deploy crashloop (caught after the fact: prod was serving from
  // an Unhealthy revision via Azure rolling fallback). Don't re-add this
  // without also updating the Dockerfile to match the new standalone path.
  // The right fix for the underlying lockfile warning is to delete the
  // orphan root package-lock.json (it's not tracked and `frontend/` is the
  // only real npm workspace).
  // /org/:orgnr → /search/:orgnr  (matches the migration plan URL spec)
  async redirects() {
    return [
      {
        source: "/org/:orgnr",
        destination: "/search/:orgnr",
        permanent: false,
      },
    ];
  },
  // Proxy /bapi/* to the FastAPI backend so the browser never needs to know
  // the backend URL in production (avoids CORS and token forwarding complexity).
  async rewrites() {
    const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000";
    return {
      // afterFiles: Next.js checks its own route handlers first (e.g. /api/auth/...
      // for NextAuth), then falls through to these rewrites for unmatched paths.
      beforeFiles: [],
      afterFiles: [
        {
          source: "/bapi/:path*",
          destination: `${apiBase}/:path*`,
        },
      ],
      fallback: [],
    };
  },
};

export default nextConfig;
