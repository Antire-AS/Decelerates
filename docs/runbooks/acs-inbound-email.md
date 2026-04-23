# ACS Inbound Email — Event Grid Webhook Setup

**Last verified:** 2026-04-22 (prod)

## What this does

An insurer replies to an anbudspakke invite (from `anbud@meglerai.no`)
with their offer PDF attached. Azure Communication Services (ACS)
receives the MIME bytes, publishes an `EmailReceived` event to Event
Grid, and Event Grid POSTs to our webhook. The webhook:

1. Validates the subscription on first call (handshake).
2. Downloads the MIME from the signed URL ACS gave us.
3. Extracts `[ref: TENDER-<tid>-<rid>]` from the subject — this token
   is embedded in every outgoing invite.
4. Stores every PDF attachment as a `TenderOffer` via `TenderService.upload_offer`.
5. Flips the recipient's status to `received`.
6. Pushes an in-app notification to every user in the tender's firm.

No broker action required. End-to-end latency ~5-15 s from insurer
clicking Send to "new offer" notification in the app.

## Terraform state today

Terraform already provisions:
- The ACS resource itself (`azurerm_communication_service.acs`)
- The Email Communication Service (`azurerm_email_communication_service`)
- The managed domain `meglerai.no` (as an ACS sender domain)
- MX + DKIM + SPF records for outbound

It does **not** provision:
- Event Grid system topic for the ACS resource
- Event Grid subscription pointing at our webhook
- Inbound routing (ACS-side inbound domain setup)

Those are manual because the webhook URL has to exist before the
subscription can be created, and we want to be deliberate about which
env the subscription binds to (prod vs staging).

## Azure Portal setup (one-time, per env)

### 1. Enable inbound on the ACS email domain

1. Open the ACS resource → **Email** → **Domains**.
2. Select `meglerai.no` → **Inbound emails** tab.
3. Toggle **Enable inbound email** → Save.
4. Copy the generated MX record value (e.g.
   `10 inbound.azurecomm.net`) and add it to Cloudflare for
   `anbud.meglerai.no` (or the subdomain you chose).
5. Wait 5-15 min for DNS to propagate, then click **Verify**.

### 2. Create Event Grid system topic on the ACS resource

1. Open the ACS resource → **Events** (in the left nav).
2. If no system topic exists, click **+ Event Subscription** — this
   creates the system topic automatically.
3. Name: `acs-inbound-prod` (or `-staging`).
4. Event types: check **Email Received**. Uncheck everything else
   (we don't want delivery reports hitting this webhook).
5. Endpoint type: **Web Hook**.
6. Endpoint URL:
   - **prod:** `https://meglerai.no/bapi/webhooks/acs/email-received`
   - **staging:** `https://staging.meglerai.no/bapi/webhooks/acs/email-received`
7. Click **Create**. Event Grid immediately POSTs a
   `Microsoft.EventGrid.SubscriptionValidationEvent` to the URL. The
   webhook echoes back `{"validationResponse": <code>}` and the
   subscription activates. If the endpoint is not reachable or
   returns non-200, activation fails — check the Activity log on the
   subscription for the retry message.

### 3. Verify end-to-end (smoke test)

1. Log in as a broker and start a tender. Pick any insurer
   (e.g. `tharu+test@example.com`).
2. Click **Send invitations** → check the sent email in the insurer's
   inbox. Subject should include `[ref: TENDER-<id>-<rid>]`.
3. Reply with a PDF attached. Wait ~10 s.
4. In the broker app, the recipient row should flip to "Mottatt" and
   a notification should pop up.
5. Check `incoming_email_log` in Postgres — should be one row with
   `status=matched` and `offer_id` set.

## Debugging

Every webhook call writes a row to `incoming_email_log`, regardless of
outcome:

```sql
-- Most recent 20 events (any env)
SELECT received_at, sender, subject, status, error_message, tender_id,
       recipient_id, offer_id, attachment_count
FROM incoming_email_log
ORDER BY received_at DESC
LIMIT 20;

-- Count by status for today
SELECT status, COUNT(*) FROM incoming_email_log
WHERE received_at >= now() - interval '1 day'
GROUP BY status;
```

Status values:
- `matched` → happy path, one offer row created per PDF
- `orphaned` → reached webhook but couldn't match (no ref token in
  subject, or tender/recipient deleted). Safe to ignore unless the
  subject *should* have a ref.
- `error` → download / parse / ingest failed. `error_message` has the
  root cause. Event Grid does **not** retry — we always return 200 on
  purpose (retries would store duplicate offers).

Event Grid side (Azure portal):
- ACS → **Events** → the subscription → **Metrics**. Track "Dropped
  events" and "Delivery failures" over 24h; both should be 0.

## Known gotchas

- **MX TTL.** If you change MX during a live test, you'll get an hour
  of silent drops. Always verify MX via `dig` before troubleshooting.
- **Reply without attachment.** The insurer clicks Reply and writes
  "coming soon" without a PDF. Webhook returns `matched` with
  `offer_id=null` and `pdf_attachments=0`. No notification fires
  (`_notify_firm_of_offer` only runs when `offer_id` is set).
  Currently not surfaced to the broker — Phase 2 consideration.
- **Ref token stripped.** Some email clients aggressively rewrite
  subjects (e.g. strip `[bracketed]` text). If `incoming_email_log`
  has lots of `orphaned` rows with sane-looking senders, check whether
  the original insurer's reply preserved the ref. Fallback parsing via
  `In-Reply-To` header is Phase 2.
- **ACS URL expiry ~24h.** If the webhook is offline for a day,
  missed events will fail the MIME download step. Check
  `error_message LIKE 'download:%'` and re-ingest manually if needed
  (not currently supported — Phase 2).

## Rollback

To disable inbound entirely:
1. Azure portal → Event Grid subscription → **Delete**.
   Webhook remains deployed but receives nothing.
2. To also reject at the SMTP level: Azure portal → ACS → Email →
   Domains → `meglerai.no` → Inbound → **Disable**. MX still resolves
   but ACS bounces the message with a permanent 5xx.

## Related code

- `api/services/inbound_email_service.py` — pipeline
- `api/routers/inbound_email.py` — webhook endpoint
- `api/services/tender_service.py:_send_tender_email` — embeds ref
  token in outbound subject
- `alembic/versions/c0d1e2f3g4h5_add_incoming_email_log.py` — audit
  table
- `tests/unit/test_inbound_email_service.py` — handshake, regex, MIME,
  dispatcher tests
