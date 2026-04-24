# SendGrid Inbound Parse — Setup Runbook

**Active from:** 2026-04-24

## What this does

- Auto-ingest: SendGrid receives mail on `anbud@meglerai.no`, parses it,
  and POSTs to our webhook. We match by the subject ref token and store
  PDF attachments as `TenderOffer` rows — exactly like the Graph path.
- Human visibility: after ingesting, we optionally forward a copy to
  any personal inbox (Gmail, Outlook, Antire mail, whatever) so you
  can read insurer replies in your normal client without logging into
  a separate mailbox.

Zero M365 involvement. Free tier is 100 inbound + 100 outbound mails
per day, which is plenty for pilot traffic. No Global Admin needed.

## One-time setup (30 min)

### 1. Sign up for SendGrid

1. https://signup.sendgrid.com/ — Free plan (no credit card required
   initially; you'll be asked for one only if you exceed 100/day).
2. After signup: verify the email SendGrid sent you.

### 2. Authenticate the sending domain

This lets SendGrid send the forwarded copies from `noreply@meglerai.no`
without landing in spam.

1. SendGrid dashboard → Settings → Sender Authentication →
   **Authenticate Your Domain**.
2. Domain: `meglerai.no`. DNS host: Azure DNS (just used for context —
   pick "Other host"; SendGrid doesn't integrate with Azure DNS).
3. SendGrid gives 3 CNAME records. Add them to Azure DNS:
   ```bash
   RG=$(az network dns zone list --query "[?name=='meglerai.no'].resourceGroup" -o tsv)
   az network dns record-set cnam create --zone-name meglerai.no --resource-group "$RG" --name em1234     # from SendGrid
   # ... repeat for each CNAME SendGrid gave you ...
   ```
4. Back in SendGrid: click **Verify**. Status should flip to Verified
   within ~5 min.

### 3. Configure Inbound Parse

1. SendGrid dashboard → Settings → Inbound Parse → **Add Host & URL**.
2. Receiving domain: `meglerai.no` (or subdomain like `anbud.meglerai.no`
   if you want to keep other mail on the domain).
3. Destination URL: `https://meglerai.no/bapi/webhooks/sendgrid/inbound?token=<generated>`
   — generate a random token (`openssl rand -hex 32`) and save it for
   step 5.
4. Check "Send Raw" — *unchecked*; we want parsed fields.
5. Save.

### 4. Point MX at SendGrid

```bash
RG=$(az network dns zone list --query "[?name=='meglerai.no'].resourceGroup" -o tsv)
az network dns record-set mx create --zone-name meglerai.no --resource-group "$RG" --name @
az network dns record-set mx add-record --zone-name meglerai.no --resource-group "$RG" --record-set-name @ \
  --exchange mx.sendgrid.net --preference 10
```

Verify: `dig +short MX meglerai.no` → `10 mx.sendgrid.net.` within 10
min.

### 5. Set prod env vars

```bash
az containerapp secret set --name ca-api --resource-group rg-broker-accelerator-prod --secrets \
  sendgrid-api-key="SG.xxxxxxxxxxxx" \
  sendgrid-inbound-token="<random-token-from-step-3>"

az containerapp update --name ca-api --resource-group rg-broker-accelerator-prod \
  --set-env-vars \
    SENDGRID_API_KEY=secretref:sendgrid-api-key \
    SENDGRID_INBOUND_TOKEN=secretref:sendgrid-inbound-token \
    SENDGRID_FORWARD_TO=tharu281001@gmail.com \
    SENDGRID_FORWARD_FROM=noreply@meglerai.no
```

`SENDGRID_FORWARD_TO` is optional — set only if you want the human
mirror to a personal inbox. `SENDGRID_FORWARD_FROM` must be on a
domain you authenticated in step 2.

## Smoke test

1. Pick a throwaway tender → Send invitations from the app → verify
   the outgoing subject has `[ref: TENDER-<id>-<rid>]`.
2. Reply from a personal inbox with a dummy PDF.
3. Within ~30 s:
   - `incoming_email_log` has a new row, `status=matched`, `offer_id`
     set (check at /admin → Innkommende e-post)
   - Notification in the app
   - Mail arrives in your `SENDGRID_FORWARD_TO` inbox with subject
     prefixed `[anbud-fwd] …` (if you configured forwarding)

## Rollback

Remove the MX record or delete the Inbound Parse host in SendGrid.
Webhook remains but no mail reaches it.

```bash
az network dns record-set mx delete --yes --zone-name meglerai.no --resource-group "$RG" --name @
```

## Costs

- SendGrid Free: 100 inbound + 100 outbound/day. Each forwarded copy
  costs 1 outbound unit.
- Exceeding free tier: $19.95/mo (Essentials, 50k outbound).
- Domain-auth CNAMEs in Azure DNS: free (Azure DNS is ~0.20 € per
  hosted zone per month; meglerai.no is already paid for).

## Related code

- `api/services/sendgrid_inbound_service.py` — normalisation + forward
- `api/routers/sendgrid_inbound.py` — webhook (`POST /webhooks/sendgrid/inbound`)
- `api/services/inbound_email_service.py:match_and_ingest` — shared
  path with Graph
- `tests/unit/test_sendgrid_inbound_service.py` — 12 unit tests
