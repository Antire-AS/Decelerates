/**
 * NextAuth configuration — Microsoft Entra ID (Azure AD) provider.
 *
 * Required env vars (frontend/.env.local):
 *   NEXTAUTH_URL=http://localhost:3000
 *   NEXTAUTH_SECRET=<random string, e.g. openssl rand -base64 32>
 *   AZURE_AD_CLIENT_ID=<App Registration client ID>
 *   AZURE_AD_CLIENT_SECRET=<App Registration client secret>
 *   AZURE_AD_TENANT_ID=<Azure tenant ID>
 *
 * Backend env vars (for JWT validation):
 *   AZURE_TENANT_ID=<same tenant ID>
 *   AUTH_AUDIENCE=<same client ID — backend validates id_token audience>
 *
 * If AZURE_AD_CLIENT_ID is not set, auth is skipped (dev mode with AUTH_DISABLED=true on backend).
 */
import type { JWT } from "next-auth/jwt";
import type { NextAuthOptions } from "next-auth";
import AzureADProvider from "next-auth/providers/azure-ad";

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
    const refreshed = await resp.json() as Record<string, unknown>;
    if (!resp.ok) throw new Error(String(refreshed.error_description ?? refreshed.error));
    return {
      ...token,
      idToken:      (refreshed.id_token      as string)  ?? token.idToken,
      refreshToken: (refreshed.refresh_token as string)  ?? token.refreshToken,
      expiresAt:    Math.floor(Date.now() / 1000) + (refreshed.expires_in as number),
    };
  } catch {
    // Signal to the session callback that re-login is needed
    return { ...token, error: "RefreshIdTokenError" };
  }
}

export const authOptions: NextAuthOptions = {
  providers: [
    AzureADProvider({
      clientId:     process.env.AZURE_AD_CLIENT_ID     ?? "",
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET ?? "",
      tenantId:     process.env.AZURE_AD_TENANT_ID     ?? "common",
    }),
  ],

  callbacks: {
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
