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
import type { NextAuthOptions } from "next-auth";
import AzureADProvider from "next-auth/providers/azure-ad";

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
      // Persist the id_token on first sign-in — backend validates this against AUTH_AUDIENCE
      if (account?.id_token) token.idToken = account.id_token;
      return token;
    },
    async session({ session, token }) {
      // Expose idToken to client so apiFetch can include it as a Bearer token
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (session as any).idToken = token.idToken;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (session as any).userOid = token.sub;
      return session;
    },
  },

  pages: {
    signIn: "/login",
  },
};
