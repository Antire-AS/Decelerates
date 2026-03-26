import { withAuth } from "next-auth/middleware";
import { NextResponse } from "next/server";

export default withAuth(
  function middleware() {
    return NextResponse.next();
  },
  {
    callbacks: {
      authorized({ token }) {
        // If Azure AD is not configured, skip auth entirely (dev / AUTH_DISABLED mode)
        if (!process.env.AZURE_AD_CLIENT_ID) return true;
        return !!token;
      },
    },
    pages: { signIn: "/login" },
  },
);

// Protect all routes except auth endpoints, static assets, and the login page
export const config = {
  matcher: [
    "/((?!api/auth|_next/static|_next/image|favicon\\.ico|login).*)",
  ],
};
