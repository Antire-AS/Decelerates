# MS Graph Inbound Email — Activation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn on the Graph-based inbound email pipeline so an insurer
replying to an anbudspakke invite with a PDF attached lands as a
`TenderOffer` in the app with no broker action.

**Architecture:** Exchange Online shared mailbox `anbud@meglerai.no`
under the Antire M365 tenant → Graph change-notification subscription
on the Inbox → `POST /webhooks/msgraph/inbound` on the prod API →
Graph fetch message + attachments → `inbound_email_service.match_and_ingest`
→ `TenderOffer` row + notification to firm users.

The webhook code, admin endpoints, and daily renewal cron already shipped
in PR #234 (merged to main 2026-04-23) and are **dormant on prod** —
they short-circuit with `graph_not_configured` until the env vars land.
This plan is the activation sequence, not a greenfield build.

**Tech Stack:** Microsoft 365 (Exchange Online), Azure AD app registration,
Microsoft Graph v1.0 (change notifications + Mail.Read), Azure DNS,
Azure Container Apps env vars, FastAPI + MSAL client_credentials,
GitHub Actions cron.

---

## Phase 1 — Gather from Antire IT (blocks everything else)

The three items below require Global Admin on the Antire M365 tenant.
Tharusan's account (`tharusan.julian@antire.com`) does not have it
(`Authorization_RequestDenied` confirmed on 2026-04-23 when attempting
to add a domain). Email the checklist in the runbook preamble to IT.

### Task 1: Custom domain

**Owner:** Antire IT (Global Admin).

- [ ] **Step 1: IT adds `meglerai.no` as a custom domain**

  Microsoft 365 admin center → Settings → Domains → Add domain →
  `meglerai.no`.

- [ ] **Step 2: IT sends you the TXT verification value**

  Looks like `MS=msXXXXXXXX`. Will go into Azure DNS in Task 4.

- [ ] **Step 3: You add the TXT record**

  ```bash
  az network dns record-set txt add-record \
    --zone-name meglerai.no \
    --resource-group $(az network dns zone list --query "[?name=='meglerai.no'].resourceGroup" -o tsv) \
    --record-set-name @ \
    --value "MS=msXXXXXXXX"
  ```

- [ ] **Step 4: Verify propagation**

  Run: `dig +short TXT meglerai.no | grep MS=`
  Expected: returns the MS= value within 5 min.

- [ ] **Step 5: IT clicks Verify in M365 admin center**

  Domain state should flip to Verified.

### Task 2: Shared mailbox

**Owner:** Antire IT (Exchange Admin).

- [ ] **Step 1: Create shared mailbox**

  Admin center → Teams & groups → Shared mailboxes → Add a shared
  mailbox → Name: `Anbud`, Email: `anbud@meglerai.no`.

- [ ] **Step 2: Confirm with IT that no member assignment is needed**

  The app reads via Graph app permissions, not user delegation.

- [ ] **Step 3: Verify the mailbox resolves**

  Send a test email from your personal account to `anbud@meglerai.no`.
  (It'll arrive but nowhere to read it yet — we'll verify in Phase 3.)

### Task 3: Graph app registration

**Owner:** Antire IT (Global Admin for consent; anyone with App
Developer role can do the registration itself).

- [ ] **Step 1: Register app**

  Azure Portal → Microsoft Entra ID → App registrations → New registration.
  Name: `meglerai-inbound-email`. Supported account types:
  "Accounts in this organizational directory only".

- [ ] **Step 2: Grant `Mail.Read` application permission**

  App registration → API permissions → Add a permission → Microsoft Graph
  → **Application permissions** → search `Mail.Read` → Add.

- [ ] **Step 3: Grant admin consent**

  "Grant admin consent for Antire" button. Requires Global Admin.
  Status column must read **Granted**.

- [ ] **Step 4: (Recommended) Restrict the app to one mailbox**

  Without this, the app can read every mailbox in the tenant. Apply an
  [Application Access Policy](https://learn.microsoft.com/en-us/graph/auth-limit-mailbox-access)
  limiting access to `anbud@meglerai.no`. Commands in the runbook's
  "Hardening" section.

- [ ] **Step 5: Create client secret**

  App registration → Certificates & secrets → New client secret →
  24-month expiry. **Copy the Value immediately** — hidden after first view.

- [ ] **Step 6: Collect the three values**

  From Overview tab: Application (client) ID, Directory (tenant) ID.
  From step 5: Client secret Value.

---

## Phase 2 — DNS + env var wiring (automatable once Phase 1 done)

### Task 4: MX record

**Files:** Azure DNS zone `meglerai.no` (managed via `az network dns`).

- [ ] **Step 1: Add MX pointing at Exchange Online**

  ```bash
  RG=$(az network dns zone list --query "[?name=='meglerai.no'].resourceGroup" -o tsv)
  az network dns record-set mx add-record \
    --zone-name meglerai.no \
    --resource-group "$RG" \
    --record-set-name @ \
    --exchange meglerai-no.mail.protection.outlook.com \
    --preference 0
  ```

- [ ] **Step 2: Verify**

  Run: `dig +short MX meglerai.no`
  Expected: `0 meglerai-no.mail.protection.outlook.com.` within 10 min.

### Task 5: SPF hardening (optional but recommended)

The current SPF is `v=spf1 include:spf.protection.outlook.com -all`.
That covers Exchange Online sends; ACS sends rely on DKIM since ACS
doesn't publish an SPF include. Left as-is unless insurers start
reporting anbud mails landing in spam.

- [ ] **Step 1: Monitor spam folder reports for 2 weeks post-launch**

  If insurers report anbud mails in spam → add `spf.azurecomm.net`
  include. Not in scope for this plan; filed as a follow-up.

### Task 6: Container Apps env vars

**Files:** Azure Container App `ca-api` env config (set via `az` CLI).

- [ ] **Step 1: Generate client-state secret**

  ```bash
  CLIENT_STATE=$(openssl rand -hex 32)
  echo "$CLIENT_STATE"  # save — needed for bootstrap + debugging
  ```

- [ ] **Step 2: Set secrets on the container**

  ```bash
  az containerapp secret set \
    --name ca-api \
    --resource-group rg-broker-accelerator-prod \
    --secrets \
      azure-ad-client-secret="<secret-value-from-task-3-step-5>" \
      msgraph-subscription-client-state="$CLIENT_STATE"
  ```

- [ ] **Step 3: Wire env vars referencing secrets**

  ```bash
  az containerapp update \
    --name ca-api \
    --resource-group rg-broker-accelerator-prod \
    --set-env-vars \
      AZURE_AD_TENANT_ID="94f56205-4854-45cd-b54c-3383e8abfb3f" \
      AZURE_AD_CLIENT_ID="<app-id-from-task-3-step-6>" \
      AZURE_AD_CLIENT_SECRET=secretref:azure-ad-client-secret \
      MS_GRAPH_SERVICE_MAILBOX="anbud@meglerai.no" \
      MS_GRAPH_SUBSCRIPTION_CLIENT_STATE=secretref:msgraph-subscription-client-state \
      MS_GRAPH_INBOUND_NOTIFICATION_URL="https://meglerai.no/bapi/webhooks/msgraph/inbound"
  ```

  Note: `AZURE_AD_TENANT_ID` is the Antire tenant GUID (confirmed via
  `az account show`).

- [ ] **Step 4: Wait for container revision to become Healthy**

  ```bash
  az containerapp revision list \
    --name ca-api \
    --resource-group rg-broker-accelerator-prod \
    --query "[0].{name:name, state:properties.runningState, health:properties.healthState}" \
    -o json
  ```

  Expected: latest revision reaches `state=Running, health=Healthy`.

- [ ] **Step 5: Sanity-check /ping**

  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" https://meglerai.no/bapi/ping
  ```

  Expected: `200`.

### Task 7: ADMIN_CRON_TOKEN for renewal workflow

**Files:** GitHub Actions secret for the main repo.

- [ ] **Step 1: Verify existing cron tokens**

  The existing nightly-altman / nightly-news workflows don't use a
  bearer token — they hit public admin endpoints. The msgraph-subscription-renew
  workflow I added assumes `secrets.ADMIN_CRON_TOKEN`. Check whether
  any existing workflow uses this secret:

  ```bash
  gh secret list --repo Antire-AS/Decelerates | grep -i CRON
  ```

- [ ] **Step 2: Either add the secret or drop the header**

  Option A (cleanest — align with existing crons):
  edit `.github/workflows/msgraph-subscription-renew.yml` to drop the
  `Authorization` header and make the admin endpoints accept
  unauthenticated requests from the GH runner IP (matches other cron
  endpoints).

  Option B: create an admin JWT, store as `ADMIN_CRON_TOKEN` secret.

  Recommended: Option A, for consistency. This is a 1-line edit to the
  workflow. File a 1-commit PR.

---

## Phase 3 — Bootstrap the subscription

### Task 8: Create the subscription

**Files:** hit `POST /admin/msgraph-inbound/create-subscription` on prod.

- [ ] **Step 1: Get an admin JWT**

  Log into https://meglerai.no as an admin user. DevTools → Application
  → Cookies or Local Storage → copy the session JWT.

- [ ] **Step 2: POST the bootstrap endpoint**

  ```bash
  curl -X POST "https://meglerai.no/bapi/admin/msgraph-inbound/create-subscription" \
    -H "Authorization: Bearer <jwt>" \
    -H "Content-Type: application/json"
  ```

  Expected response:
  ```json
  {
    "id": "<sub-guid>",
    "resource": "users/anbud@meglerai.no/mailFolders('Inbox')/messages",
    "expirationDateTime": "2026-04-26T...",
    "notificationUrl": "https://meglerai.no/bapi/webhooks/msgraph/inbound",
    "clientState": "<redacted by Graph>"
  }
  ```

  **Failure modes:**
  - `validation timed out` → webhook not reachable or >10s to respond.
    Warm the container first with a /ping call.
  - `403 Forbidden` on the Graph call → admin consent missing.
  - `MS_GRAPH_SUBSCRIPTION_CLIENT_STATE unset` → revisit Task 6 Step 2.

- [ ] **Step 3: Verify the subscription exists**

  ```bash
  curl "https://meglerai.no/bapi/admin/msgraph-inbound/subscriptions" \
    -H "Authorization: Bearer <jwt>"
  ```

  Expected: list with one entry whose `id` matches step 2.

---

## Phase 4 — Smoke test end-to-end

### Task 9: Controlled reply test

**Files:** none. This is a manual walkthrough against prod.

- [ ] **Step 1: Create a throwaway tender**

  Log in as a broker. Create a new tender for any company. Add an insurer
  recipient whose email you control (e.g. `<your-personal>@gmail.com`).

- [ ] **Step 2: Send the invite**

  Click "Send invitations". Check the insurer's inbox — the subject must
  contain `[ref: TENDER-<id>-<recipient_id>]`.

- [ ] **Step 3: Reply with a PDF**

  Reply to the invite from the personal address. Attach any PDF (a
  dummy is fine). Preserve the subject ref token (most clients do; if
  Gmail rewrites, copy-paste the ref token back in).

- [ ] **Step 4: Watch the webhook logs**

  ```bash
  az containerapp logs show --name ca-api \
    --resource-group rg-broker-accelerator-prod \
    --tail 50 --follow | grep -i msgraph
  ```

  Expected within 10-20s of sending: a log line about the notification
  being processed.

- [ ] **Step 5: Verify `incoming_email_log`**

  ```sql
  SELECT received_at, sender, subject, status, tender_id,
         recipient_id, offer_id, attachment_count
  FROM incoming_email_log
  ORDER BY received_at DESC LIMIT 1;
  ```

  Expected: one row, `status=matched`, `offer_id` not null, `attachment_count=1`.

- [ ] **Step 6: Verify the broker UI**

  - Tender detail page: recipient row should show "Mottatt" status and
    the offer PDF listed.
  - Notifications bell should show "Nytt tilbud fra …".

- [ ] **Step 7: Delete the test tender + offer**

  Clean up to keep prod data tidy.

---

## Phase 5 — Follow-up hardening (each becomes its own PR)

### Task 10: Dedup

**Files:** `api/services/msgraph_inbound_service.py`,
`api/services/inbound_email_service.py`,
`alembic/versions/<new>_incoming_email_log_message_id.py`.

Graph can replay the same notification if our 2xx ack is missed. Right
now that'd create duplicate `TenderOffer` rows.

- [ ] **Step 1: Add `message_id` column to `incoming_email_log`**

  Migration adds a nullable `TEXT` column with unique index when
  not-null.

- [ ] **Step 2: Extract `message_id` from the Graph fetch**

  The Graph `GET /messages/{id}` response includes `internetMessageId`
  (RFC822 Message-ID). Capture it in `fetch_and_parse_message` and plumb
  through `match_and_ingest` → `_log_row`.

- [ ] **Step 3: Short-circuit when message_id already logged**

  `match_and_ingest` checks `db.query(IncomingEmailLog).filter(
  message_id=...).first()` before ingesting; if present, return
  `{"status": "dedup"}`.

- [ ] **Step 4: Unit test**

  Call `match_and_ingest` twice with the same parsed dict (including
  `message_id`) and assert only one `TenderOffer` / one
  `IncomingEmailLog` row.

### Task 11: Admin page for `incoming_email_log`

**Files:** new `api/routers/admin_router.py` endpoint,
new `frontend/src/app/admin/email-log/page.tsx`.

Brokers can't currently see orphaned/error rows without `psql`. Add a
simple admin page.

- [ ] **Step 1: API endpoint**

  `GET /admin/email-log?limit=50&status=error|orphaned|matched` →
  JSON list. Admin-role only.

- [ ] **Step 2: Frontend page**

  Table with received_at / sender / subject / status / error /
  attachment_count / offer link. Filter chips for status.

- [ ] **Step 3: Nav link**

  Under `/admin` → "Innkommende e-post".

### Task 12: Subscription monitoring

**Files:** `api/routers/msgraph_inbound.py`, new admin endpoint +
alert wiring.

If renewal cron breaks, subscription expires and inbound goes silent
with no user-visible signal.

- [ ] **Step 1: Endpoint returning subscription health**

  `GET /admin/msgraph-inbound/health` returns the current subscription
  expiry and `minutes_until_expiry`. If < 4h or no subscription: 503.

- [ ] **Step 2: Uptime check**

  Add the endpoint to the existing prod health monitor (Azure Monitor
  or whatever you currently use). Alerts if non-200.

### Task 13: "Reply without PDF" surfacing

**Files:** `api/services/inbound_email_service.py`,
frontend tender detail component.

When an insurer replies without an attachment, we log `matched` with
`offer_id=null` and the broker never sees it. Should surface as a
note on the tender recipient row.

- [ ] **Step 1: On `offer_id=None`, create a `TenderNote` instead**

  Short text: "Insurer replied but attached no PDF — check mail inbox."

- [ ] **Step 2: Render notes on the tender detail page**

  If not already rendered, add a timeline entry component.

---

## Out of scope

- **SendGrid fallback** — we committed to Graph. If volume stays under
  free-tier and stability holds, no need.
- **Splitting meglerai.no off into its own M365 tenant** — deferred
  until/unless the product spins out from Antire.
- **Multi-firm support** — currently one shared mailbox per deployment.
  Per-firm inbound would need a subscription per firm + routing by
  recipient address.
- **Moving env vars into `main.py`** per the Phase 1 hexagonal
  convention. The Graph config is currently read in the router. That's
  noted in the router's docstring. Can be promoted if a second Graph
  path lands.

---

## Rollback

If anything goes sideways on prod:

1. **Deactivate the webhook** — no code change needed; unset env vars:
   ```bash
   az containerapp update --name ca-api \
     --resource-group rg-broker-accelerator-prod \
     --remove-env-vars AZURE_AD_TENANT_ID AZURE_AD_CLIENT_ID \
       AZURE_AD_CLIENT_SECRET MS_GRAPH_SERVICE_MAILBOX \
       MS_GRAPH_SUBSCRIPTION_CLIENT_STATE
   ```
   Webhook returns `graph_not_configured`; dormant.

2. **Delete the subscription** — so Graph stops POSTing:
   ```bash
   # Get a token via az and DELETE /subscriptions/{id}
   # Or use Graph Explorer in a browser.
   ```

3. **Drop MX** if you want inbound mail to bounce entirely:
   ```bash
   az network dns record-set mx delete --yes \
     --zone-name meglerai.no --resource-group "$RG" --name @
   ```

4. **Outbound is unaffected** — ACS sends continue to work; they don't
   depend on the mailbox existing.
