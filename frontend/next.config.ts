import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Proxy /api/* to the FastAPI backend so the browser never needs to know
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
