# e2e-bot Entra ID account provisioning (Phase 2 activation)

## What this is

The Playwright e2e real-auth scaffolding shipped in PR #176 assumes a
service-account user `e2e-bot@<tenant>` exists in Entra ID and can log
in via username+password. The bot runs the full onboarding tour, then
exercises the auth-gated happy path for CRM / anbud / chat / portfolio.

No test runs against real SSO until this account exists. Until then,
Playwright e2e against prod stays gated on the staging hop (where
`AUTH_DISABLED=1` makes the bot account unnecessary).

## Prerequisites

- Entra admin rights in the Antire tenant (Global Admin or User
  Administrator role).
- `gh` CLI authenticated as a repo admin.

## One-time steps

### 1. Create the user in Entra ID

Azure portal → **Entra ID** → **Users** → **New user** → **Create new user**:

| Field | Value |
|---|---|
| User principal name | `e2e-bot@<your-tenant>.onmicrosoft.com` |
| Display name | `E2E Bot` |
| Auto-generate password | **Uncheck** — set one manually |
| Password | generate a 32-char random string; copy to a scratchpad |
| Account enabled | ✓ |

On the **Assignments** step: leave Default role (no admin role needed).
On **Review**: **Create**.

### 2. Grant it Broker Accelerator app access

The app registration for the broker frontend is `broker-frontend`.
Grant `e2e-bot` access so it can sign in via OIDC:

Azure portal → **Entra ID** → **Enterprise applications** → find
`broker-frontend` → **Users and groups** → **Add user/group** →
select `e2e-bot@...` → **Assign**.

### 3. Skip the first-login password change

By default new Entra users must reset their password on first login,
which would break the Playwright login flow. Disable that for this
user:

```bash
az ad user update --id e2e-bot@<your-tenant>.onmicrosoft.com \
  --force-change-password-next-sign-in false
```

### 4. Store credentials in GitHub secrets

```bash
gh secret set E2E_BOT_USERNAME --body "e2e-bot@<your-tenant>.onmicrosoft.com"
gh secret set E2E_BOT_PASSWORD  # paste the 32-char password when prompted
```

Never paste these into chat or commit them — the `--body` flag reads
from CLI arg but for the password use the interactive prompt so it
doesn't hit shell history.

### 5. Verify

```bash
gh secret list | grep E2E_BOT
```

Should show `E2E_BOT_USERNAME` and `E2E_BOT_PASSWORD` with timestamps.

### 6. Enable the real-auth path in CI

The e2e workflow at `.github/workflows/e2e.yml` currently runs only
against staging (which has `AUTH_DISABLED=1`). To flip it to real-auth
mode, add a prod-target job that reads the new secrets. File a PR
titled something like `ci(e2e): enable real-auth run against prod`
based on the existing staging job — parameterise the base URL + auth
mode. Reference PR #176 for the Playwright fixture that expects
`E2E_BOT_USERNAME` / `E2E_BOT_PASSWORD` to be set.

## Rollback

If the bot starts misbehaving or gets compromised:

```bash
az ad user delete --id e2e-bot@<your-tenant>.onmicrosoft.com
gh secret delete E2E_BOT_USERNAME
gh secret delete E2E_BOT_PASSWORD
```

CI falls back to staging-only e2e until the bot is recreated.

## Why not automate this

Creating a new Entra user + granting app access are Global Admin
permissions — this repo's GitHub OIDC identity deliberately does NOT
carry those roles. Automating this would require elevating the CI
service principal to User Administrator on the tenant, which is
unsafe for a feature gate that's run once per quarter (when the bot's
password is rotated).
