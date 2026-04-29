# Anbudspakke email sender setup

**Purpose**: Switch the "from" address on anbudspakke emails (and every other ACS-sent mail) from the generic `donotreply@acs-broker-accelerator-prod.azurecomm.net` to a domain you control, e.g. `anbud@antire.no` or `anbud@antire.com`.

This is the runbook for that setup. Most of the work happens in the Azure portal + at your DNS provider — code-side is one env var.

---

## Current state (2026-04-23)

`.github/workflows/deploy.yml` line 143 hard-codes:

```yaml
"ACS_SENDER_ADDRESS=anbud@meglerai.no"
```

`meglerai.no` is **already verified** in the ACS Email resource (it's been serving there since before this sprint), so emails currently ship from that address. Everything below is for moving to a different domain.

---

## Decision: `.no` vs `.com`

**Pick `antire.no`** if antire.no is your primary Norwegian domain and you own the DNS zone. Norwegian clients trust `.no` more in the financial services context; the whole product UX is Norwegian.

**Pick `antire.com`** only if you don't own `.no` DNS, or you're planning an international push. `.com` from a Norwegian broker feels slightly off in context.

Both work identically in ACS — neither is cheaper or faster.

If you want the demo to feel professional, `anbud@antire.no` is the right call.

---

## Step 1 — Add the custom domain to ACS

Azure Portal:

1. Navigate to **Azure Communication Services** → your resource (probably `acs-broker-accelerator-prod`).
2. Under **Email** → **Domains**, click **Connect domain** → **Custom domain**.
3. Enter `antire.no` (or `antire.com`). Azure gives you a random verification TXT record, something like `TXT antire.no ms-domain-verification=<uuid>`.
4. Copy that TXT record value.

## Step 2 — Add DNS records at your registrar

Log into wherever antire.no DNS is managed (Domeneshop / GoDaddy / whoever) and add **three records**:

| Type | Host | Value | TTL |
|---|---|---|---|
| TXT | `@` (or `antire.no`) | the `ms-domain-verification=...` value from step 1 | 3600 |
| TXT | `@` | `v=spf1 include:spf.protection.outlook.com -all` | 3600 |
| CNAME | `selector1-azurecomm-prod-net._domainkey` | `selector1-azurecomm-prod-net._domainkey.azurecomm.net` | 3600 |
| CNAME | `selector2-azurecomm-prod-net._domainkey` | `selector2-azurecomm-prod-net._domainkey.azurecomm.net` | 3600 |

(Actually four records — SPF + domain verification + two DKIM CNAMEs. ACS shows you the exact values.)

Wait **15 min – 4 hours** for DNS propagation.

## Step 3 — Verify in the Portal

Back in Azure Portal → ACS → Email → Domains → `antire.no`:

- **Domain verification**: click **Verify** → should flip to green
- **SPF**: green
- **DKIM**: green (both selectors)

Until all three are green, ACS rejects sends from `anything@antire.no` with `InvalidSenderDomain`. You can still test with the old `meglerai.no` or `donotreply@...` sender in the meantime.

## Step 4 — Add the MailFrom address

Still in Portal → ACS → Email → Domains → `antire.no`:

- **MailFrom addresses** → **Add** → `anbud`
- Display name: `Broker Accelerator — Anbud` (or whatever shows nicely in insurers' inboxes)

This creates `anbud@antire.no` as a sendable address.

## Step 5 — Flip the config

Edit `.github/workflows/deploy.yml` line 143:

```yaml
"ACS_SENDER_ADDRESS=anbud@antire.no"
```

Commit → merge to main → prod deploy picks it up.

**Or** without a deploy: override the env var on the live Container App:

```bash
az containerapp update \
  --name ca-api \
  --resource-group rg-meglerai-prod \
  --set-env-vars "ACS_SENDER_ADDRESS=anbud@antire.no"
```

That takes effect within a minute (creates a new revision). Safer for a demo-imminent flip.

## Step 6 — Smoke test

```bash
curl -X POST https://meglerai.no/bapi/org/923609016/anbudspakke/email \
  -H "Content-Type: application/json" \
  -d '{"to": "your-own-email@example.com"}'
```

Check your inbox. "From" should read `Broker Accelerator — Anbud <anbud@antire.no>`. If it bounces or you get 503, check `az containerapp logs show` for ACS error text.

---

## Rollback

Still just `ACS_SENDER_ADDRESS=anbud@meglerai.no`. Either revert the deploy.yml change or `az containerapp update --set-env-vars "ACS_SENDER_ADDRESS=anbud@meglerai.no"`. Takes 60 seconds.

## Common gotchas

- **SPF record conflict**: if antire.no already has a TXT SPF record for Google Workspace / MS 365 / another provider, don't replace it — merge both into one record. ACS + M365 together: `v=spf1 include:spf.protection.outlook.com include:_spf.google.com -all`.
- **DKIM selectors**: ACS rotates the DKIM keypair every ~6 months but keeps the selectors stable. The CNAME targets point to Azure's rotating records, so you set them once.
- **DMARC**: optional but recommended. `TXT _dmarc.antire.no v=DMARC1; p=none; rua=mailto:dmarc@antire.no` to start in monitor-only mode, then tighten to `p=quarantine` after a month of clean reports.
- **Custom from-name per send**: `ACS_SENDER_ADDRESS` is the envelope sender. To vary the display name per email (e.g. `Tharusan Julian <anbud@antire.no>`), extend `NotificationConfig.sender` to accept `"Name <addr>"` format and surface it as a broker-firm setting. Out of scope for the demo.

## What I did NOT do

- I did not change `ACS_SENDER_ADDRESS` in `deploy.yml` — I can't verify the domain for you, and flipping the env var before the domain is verified in ACS breaks every outbound email.
- I did not make any Azure portal changes. Those steps are yours.

Once you've done steps 1–4 in the portal, tell me which domain you went with (`.no` or `.com`) and I'll make the deploy.yml change + rollout.
