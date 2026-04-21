# Real-auth e2e setup (Phase 2 of application-hardening)

## What this is

`frontend/e2e/auth-flow.spec.ts` exercises the real Azure AD / Google OAuth
round-trip end-to-end. It's deliberately dormant — every other e2e spec runs
against staging with `AUTH_DISABLED=1`, so the first broker to hit prod's
`/login` is currently the canary for whether auth works at all.

This runbook activates it.

## One-time provisioning (IT)

1. **Create the bot account** in Entra ID.
    - Username: `e2e-bot@<tenant>`
    - Password: 20+ chars, store in the org password manager
    - Disable MFA (Playwright cannot clear MFA prompts)
    - Mark the account as **non-interactive** + **service account**
2. **Group membership**: add the bot to the `broker-firm-access` group so
    `api.auth.get_current_user` auto-provisions it with `firm_id=1`.
3. **Re-check the group filter in `api/auth.py`** — if the broker-firm-access
    group was renamed, update both the account membership and the app config.
4. **Store secrets** in GitHub Actions:
    - Settings → Secrets and variables → Actions
    - `E2E_AUTH_BOT_EMAIL` = full email address
    - `E2E_AUTH_BOT_PASSWORD` = the password from step 1

## Running the suite

Once the above are in place:

```
gh workflow run e2e.yml -f target=auth-test
```

The `auth-test` target:
- Points Playwright at `https://meglerai.no` (prod, where `AUTH_DISABLED` is unset).
- Sets `PLAYWRIGHT_AUTH_TEST=1` so `auth-flow.spec.ts` stops skipping.
- Injects the bot credentials from the two secrets above.

The suite runs 3 tests:
1. Unauthenticated `/dashboard` hit redirects to `/login`.
2. Microsoft OAuth round-trip lands on `/dashboard` with a session cookie.
3. Authenticated `/bapi/whoami` returns the bot's email.

A failing run signals a real auth regression — the FE or BE stopped
round-tripping tokens correctly, or Entra ID changed its sign-in DOM
(selectors may need refreshing; see `auth-flow.spec.ts` for the fragile
selector list).

## Why this matters

Azure AD / NextAuth / backend JWT validation is a three-hop chain. A
refactor that breaks any one link is invisible to every other e2e spec
(they all bypass auth). This spec is the single end-to-end assertion that
the full login flow still works — without it, a broken refresh-token
handler could ship to prod and only surface as "nobody can log in
tomorrow morning."

## Why this is dormant by default

Until the bot account exists, the spec has no way to authenticate. The
workflow input is behind `target=auth-test`, not part of the default
post-deploy run, so a missing bot account never breaks CI. Once
activated, consider adding it to the post-deploy schedule (or a weekly
cron) depending on how often you want the real-auth canary to run.
