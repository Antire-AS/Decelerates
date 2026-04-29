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

export const config = {
  matcher: [
    "/((?!api/auth|_next/static|_next/image|favicon\\.ico|login|portal).*)",
  ],
};
