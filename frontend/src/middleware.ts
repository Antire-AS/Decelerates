// Auth disabled — all routes are publicly accessible.
// To re-enable Azure AD login, uncomment the block below and remove the bypass export.
//
// import { withAuth } from "next-auth/middleware";
// import { NextResponse } from "next/server";
//
// export default withAuth(
//   function middleware() {
//     return NextResponse.next();
//   },
//   {
//     callbacks: {
//       authorized({ token }) {
//         if (!process.env.AZURE_AD_CLIENT_ID) return true;
//         return !!token;
//       },
//     },
//     pages: { signIn: "/login" },
//   },
// );

import { NextResponse } from "next/server";

// Bypass: allow all routes without authentication
export default function middleware() {
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!api/auth|_next/static|_next/image|favicon\\.ico|login).*)",
  ],
};
