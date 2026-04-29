import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";

export default withAuth(
  function middleware() {
    return NextResponse.next();
  },
  {
    callbacks: {
      authorized({ token }) {
        // If neither OAuth provider is configured, treat all routes as open
        // (local dev without env vars). Otherwise require a session token.
        if (!process.env.AZURE_AD_CLIENT_ID && !process.env.GOOGLE_CLIENT_ID) {
          return true;
        }
        return !!token;
      },
    },
    pages: { signIn: "/login" },
  },
);

// Middleware exclusions:
//   api/auth       — NextAuth's own callback URLs (signin, callback, csrf, providers)
//   bapi           — server-side rewrite to FastAPI; backend enforces its own
//                    auth via api/auth.py:get_current_user + the email allowlist
//                    introduced in PR #280, so a second gate here is redundant
//                    and broke /portal pages whose useRiskConfig() call hits
//                    /bapi/risk/config without a NextAuth session
//   _next, favicon — Next.js infra assets
//   login          — pre-auth screen
//   portal         — token-based customer view (no NextAuth session)
export const config = {
  matcher: [
    "/((?!api/auth|bapi|_next/static|_next/image|favicon\\.ico|login|portal).*)",
  ],
};
