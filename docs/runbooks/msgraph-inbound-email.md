# Microsoft Graph Inbound Email — Setup Runbook

**Last verified:** 2026-04-23 (pending initial prod wire-up)

## What this does

An insurer replies to an anbudspakke invite from `anbud@meglerai.no`
with their offer PDF attached. Exchange Online receives the message in
the `anbud` shared mailbox's Inbox. Graph change-notification fires,
POSTs to our webhook, we fetch the message + attachment, match it back
to the tender via the subject-line ref token, and store the offer.

End-to-end latency ~5-20 s from insurer pressing Send to "new offer"
notification in the app.

## Why Graph, not ACS

ACS does not publish an `EmailReceived` Event Grid event — only delivery
reports and engagement tracking. Exchange Online + Graph change
notifications is the actual supported path for inbound email in the
Microsoft stack.

## One-time external setup (admin actions, one of them requires
Global Admin in the Antire tenant)

### 1. Add `meglerai.no` as a custom domain in the Antire M365 tenant

1. Microsoft 365 admin center → Settings → Domains → **Add domain**
2. Enter `meglerai.no`
3. Microsoft returns a TXT verification value like `MS=ms...`. Add it
   to Azure DNS:
   ```bash
   az network dns record-set txt add-record \
     --zone-name meglerai.no \
     --resource-group <dns-rg> \
     --record-set-name @ \
     --value "MS=msXXXXXXXX"
   ```
4. After ~5 min propagation, click **Verify** in the admin center.

### 2. Create the shared mailbox

1. Admin center → Teams & groups → Shared mailboxes → **Add a shared
   mailbox**
2. Name: `Anbud`
3. Email: `anbud@meglerai.no`
4. No member assignments needed at this step (the app accesses it via
   Graph app permissions — see step 3).

### 3. Register the Graph app

1. Azure Portal → Microsoft Entra ID → App registrations →
   **New registration**
2. Name: `meglerai-inbound-email`
3. After creation:
   - Copy **Application (client) ID** → will be `AZURE_AD_CLIENT_ID`
   - Copy **Directory (tenant) ID** → will be `AZURE_AD_TENANT_ID`
4. **Certificates & secrets** → **New client secret** → copy the value
   immediately (will be `AZURE_AD_CLIENT_SECRET`; not shown again)
5. **API permissions** → **Add a permission** → Microsoft Graph →
   **Application permissions** → search for and add:
   - `Mail.Read`
6. Click **Grant admin consent for Antire** (requires Global Admin).
7. (Optional hardening) Restrict the app to only read the `anbud@meglerai.no`
   mailbox using [Application Access Policy](https://learn.microsoft.com/en-us/graph/auth-limit-mailbox-access).
   Without this, the app can read every mailbox in the tenant.

### 4. MX record for inbound email

```bash
az network dns record-set mx create --zone-name meglerai.no --resource-group <dns-rg> --name @
az network dns record-set mx add-record --zone-name meglerai.no --resource-group <dns-rg> --record-set-name @ \
  --exchange meglerai-no.mail.protection.outlook.com --preference 0
```

Wait 5-10 min for propagation. Verify with `dig +short MX meglerai.no`.

## Set env vars in prod

```bash
az containerapp update --name ca-api --resource-group rg-broker-accelerator-prod \
  --set-env-vars \
    AZURE_AD_TENANT_ID="<tenant-guid>" \
    AZURE_AD_CLIENT_ID="<app-guid>" \
    AZURE_AD_CLIENT_SECRET="<secret-value>" \
    MS_GRAPH_SERVICE_MAILBOX="anbud@meglerai.no" \
    MS_GRAPH_SUBSCRIPTION_CLIENT_STATE="$(openssl rand -hex 32)" \
    MS_GRAPH_INBOUND_NOTIFICATION_URL="https://meglerai.no/bapi/webhooks/msgraph/inbound"
```

**Important**: treat `AZURE_AD_CLIENT_SECRET` and
`MS_GRAPH_SUBSCRIPTION_CLIENT_STATE` as secrets — store as Container
Apps secrets (not plain env vars). This runbook simplifies for clarity.

## Create the initial subscription

Once env vars are in place and the container restarted:

```bash
# Requires an admin-role JWT for meglerai.no
curl -X POST "https://meglerai.no/bapi/admin/msgraph-inbound/create-subscription" \
  -H "Authorization: Bearer <admin-jwt>"
```

Expected response:
```json
{
  "id": "<subscription-guid>",
  "resource": "users/anbud@meglerai.no/mailFolders('Inbox')/messages",
  "expirationDateTime": "2026-04-26T...",
  "notificationUrl": "https://meglerai.no/bapi/webhooks/msgraph/inbound"
}
```

During subscription create, Graph calls our webhook with
`?validationToken=...` and expects the token echoed back. The route
handles this automatically. If the create returns an error about
validation, check that:

- `https://meglerai.no/bapi/webhooks/msgraph/inbound` is reachable
  externally (test with `curl`)
- The prod container has the new env vars

## Daily subscription renewal

`.github/workflows/msgraph-subscription-renew.yml` runs every day at
03:00 UTC and hits
`POST /admin/msgraph-inbound/renew-subscriptions`. Graph caps mail
subscriptions at ~70h, we set 60h expiry, so once-a-day renewal leaves
a comfortable margin.

## Smoke test

1. From any external email account, send a mail to `anbud@meglerai.no`
   with subject `Test [ref: TENDER-1-1]` and attach a PDF.
2. Within ~20s, check `incoming_email_log`:
   ```sql
   SELECT received_at, sender, subject, status, error_message,
          tender_id, recipient_id, offer_id, attachment_count
   FROM incoming_email_log
   ORDER BY received_at DESC
   LIMIT 5;
   ```
3. Expect one row. Status will be `orphaned` (unknown tender) if the
   test tender doesn't exist, `matched` if it does, `error` with
   `error_message` if something broke.

## Debugging

`incoming_email_log` statuses (same schema as ACS path):
- `matched` — happy path, offer stored
- `orphaned` — reached webhook but couldn't match (no ref, or tender
  gone)
- `error` — download / parse / ingest failed; `error_message` explains

Graph-side:
- `GET /admin/msgraph-inbound/subscriptions` — list active subscriptions
  and their expiry
- Azure Portal → Monitor → Application Insights (api-broker-accelerator)
  → Logs: `traces | where message contains "msgraph_inbound"`

Common issues:
- **403 on token fetch** → admin consent not granted on the Graph app
- **"validation timed out"** during create-subscription → webhook not
  reachable, or took >10s to echo the token back (check Container Apps
  scale-to-zero — warm the app first)
- **`clientState mismatch`** in incoming_email_log → `MS_GRAPH_SUBSCRIPTION_CLIENT_STATE`
  env var differs from what the subscription was created with. Recreate
  the subscription.

## Rollback

```bash
# List + delete subscriptions
curl https://meglerai.no/bapi/admin/msgraph-inbound/subscriptions -H "Authorization: Bearer <jwt>"
# Then manually DELETE /subscriptions/{id} via Graph Explorer or az rest
```

To disable inbound entirely at the DNS level: remove the MX record. Mail
to `anbud@meglerai.no` will bounce at the sending server.

## Related code

- `api/services/msgraph_inbound_service.py` — Graph token, fetch,
  subscription CRUD
- `api/routers/msgraph_inbound.py` — webhook + admin endpoints
- `api/services/inbound_email_service.py` — shared match/ingest path
- `alembic/versions/c0d1e2f3g4h5_add_incoming_email_log.py` — audit
  table (shipped with the ACS v5 attempt; still used here)
- `tests/unit/test_msgraph_inbound_service.py` — unit tests
- `.github/workflows/msgraph-subscription-renew.yml` — daily cron
