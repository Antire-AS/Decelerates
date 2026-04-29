/**
 * NextAuth configuration — Microsoft Entra ID + Google providers.
 *
 * Required env vars (frontend/.env.local):
 *   NEXTAUTH_URL=http://localhost:3000
 *   NEXTAUTH_SECRET=<random string>
 *   AZURE_AD_CLIENT_ID, AZURE_AD_CLIENT_SECRET, AZURE_AD_TENANT_ID
 *   GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
 *
 * Either or both providers can be enabled. If neither CLIENT_ID is set,
 * auth is skipped (dev mode with AUTH_DISABLED=true on backend).
 */
import type { JWT } from "next-auth/jwt";
import type { NextAuthOptions } from "next-auth";
import AzureADProvider from "next-auth/providers/azure-ad";
import GoogleProvider from "next-auth/providers/google";

/** Shape of the Azure AD v2.0 token endpoint response (success or error). */
interface AzureAdTokenResponse {
  id_token?: string;
  refresh_token?: string;
  expires_in?: number;
  error?: string;
  error_description?: string;
}

/** Call the Azure AD token endpoint with the stored refresh_token to get a fresh id_token. */
async function refreshIdToken(token: JWT): Promise<JWT> {
  try {
    const tenantId = process.env.AZURE_AD_TENANT_ID ?? "common";
    const resp = await fetch(
      `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          grant_type:    "refresh_token",
          client_id:     process.env.AZURE_AD_CLIENT_ID     ?? "",
          client_secret: process.env.AZURE_AD_CLIENT_SECRET ?? "",
          refresh_token: token.refreshToken as string,
          scope:         "openid profile email",
        }),
      },
    );
    const refreshed: AzureAdTokenResponse = await resp.json();
    if (!resp.ok) throw new Error(refreshed.error_description ?? refreshed.error ?? "unknown");
    return {
      ...token,
      idToken:      refreshed.id_token      ?? token.idToken,
      refreshToken: refreshed.refresh_token ?? token.refreshToken,
      expiresAt:    Math.floor(Date.now() / 1000) + (refreshed.expires_in ?? 3600),
    };
  } catch {
    // Signal to the session callback that re-login is needed
    return { ...token, error: "RefreshIdTokenError" };
  }
}

export const authOptions: NextAuthOptions = {
  providers: [
    ...(process.env.AZURE_AD_CLIENT_ID ? [
      AzureADProvider({
        clientId:     process.env.AZURE_AD_CLIENT_ID,
        clientSecret: process.env.AZURE_AD_CLIENT_SECRET ?? "",
        tenantId:     process.env.AZURE_AD_TENANT_ID     ?? "common",
      }),
    ] : []),
    ...(process.env.GOOGLE_CLIENT_ID ? [
      GoogleProvider({
        clientId:     process.env.GOOGLE_CLIENT_ID,
        clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
      }),
    ] : []),
  ],

  callbacks: {
    async signIn({ user }) {
      // Mirror of api/auth.py:_is_email_authorized — keeps rejection at the
      // OAuth callback so unauthorized users see "Access Denied" from NextAuth
      // instead of getting a session and seeing inline 403s on every API call.
      // Empty allowlist envs = fail-open (matches backend).
      const email = (user.email ?? "").trim().toLowerCase();
      if (!email) return false;
      const domains = (process.env.AUTH_ALLOWED_DOMAINS ?? "")
        .split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
      const emails = (process.env.AUTH_ALLOWED_EMAILS ?? "")
        .split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
      if (domains.length === 0 && emails.length === 0) return true;
      if (emails.includes(email)) return true;
      const at = email.lastIndexOf("@");
      if (at >= 0 && domains.includes(email.slice(at + 1))) return true;
      return false;
    },

    async jwt({ token, account }) {
      // First sign-in: persist tokens and expiry
      if (account) {
        return {
          ...token,
          idToken:      account.id_token,
          refreshToken: account.refresh_token,
          // expires_at is Unix seconds; subtract 60s buffer so we refresh before actual expiry
          expiresAt:    (account.expires_at ?? Math.floor(Date.now() / 1000) + 3600) - 60,
        };
      }

      // Token still valid — return as-is
      if (Date.now() < (token.expiresAt as number) * 1000) {
        return token;
      }

      // Token expired — refresh silently using the refresh_token
      return refreshIdToken(token);
    },

    async session({ session, token }) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (session as any).idToken  = token.idToken;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (session as any).userOid  = token.sub;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (session as any).error    = token.error;
      return session;
    },
  },

  pages: {
    signIn: "/login",
  },
};
