# Autonomous Polish Plan (no Antire-IT dependency)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship every remaining demo-readiness + hygiene improvement that doesn't require Antire IT (who we'd otherwise need for M365/Graph domain setup). SendGrid already covers inbound end-to-end, so the Graph path stays dormant until IT engages.

**Architecture:** Six small changes — DNS, secrets rotation, a flaky test, removal of a dead webhook, a seed script, and a "Start demo" admin button. No new services, no new infra.

**Tech Stack:** Azure DNS + Container Apps secrets, SendGrid API, FastAPI + SQLAlchemy, Next.js admin UI.

---

## Task 1: Rotate bootstrap SendGrid API key → restricted runtime key

**Files:**
- Azure Container App secret `sendgrid-api-key` (prod)
- Nothing in the repo

**Why:** Bootstrap key was exposed in chat during setup, and it has Full Access scope (can manage sub-users, delete Parse config, etc). Runtime only needs `Mail Send`. Rotating shrinks blast radius.

- [ ] **Step 1: User creates new restricted key**

  SendGrid UI → Settings → API Keys → Create API Key.
  - Name: `meglerai-prod-runtime`
  - Permissions: Restricted → **Mail Send: Full Access** only (everything else No Access)
  - Copy value (starts `SG.…`) and paste into chat.

- [ ] **Step 2: Rotate prod secret**

  ```bash
  az containerapp secret set \
    --name ca-api --resource-group rg-broker-accelerator-prod \
    --secrets sendgrid-api-key="SG.<new>"
  az containerapp update \
    --name ca-api --resource-group rg-broker-accelerator-prod \
    --revision-suffix rotate-$(date +%s)
  ```

- [ ] **Step 3: Smoke test**

  Send mail from Gmail → anbud@meglerai.no → verify forward arrives in `tharu281001@gmail.com`.

- [ ] **Step 4: User deletes old bootstrap key**

  SendGrid UI → API Keys → delete `bootstrap-temp-delete-after-setup`.

---

## Task 2: SPF harden for SendGrid outbound

**Files:** Azure DNS zone `meglerai.no` (no code)

**Why:** Current SPF says `v=spf1 include:spf.protection.outlook.com -all` — from the Graph-era plan. SendGrid-relayed outbound (tender invites, forward copies) now fails SPF; they currently pass inbox filters only because DKIM is valid. Adding the SendGrid include removes that fragility — recipients with strict SPF policies (banks, insurers) stop maybe-spam-treating our mail.

- [ ] **Step 1: Update SPF TXT record**

  ```bash
  RG=$(az network dns zone list --query "[?name=='meglerai.no'].resourceGroup" -o tsv)
  az network dns record-set txt remove-record \
    --zone-name meglerai.no --resource-group "$RG" --record-set-name @ \
    --value "v=spf1 include:spf.protection.outlook.com -all"
  az network dns record-set txt add-record \
    --zone-name meglerai.no --resource-group "$RG" --record-set-name @ \
    --value "v=spf1 include:sendgrid.net include:spf.protection.outlook.com -all"
  ```

- [ ] **Step 2: Verify propagation**

  ```bash
  dig +short TXT meglerai.no | grep spf1
  ```

  Expected: includes both `sendgrid.net` and `spf.protection.outlook.com` within 10 min.

- [ ] **Step 3: Send test via SendGrid + check headers**

  Look at full headers in Gmail for "Received-SPF: pass" from sendgrid.net.

---

## Task 3: Fix flaky `test_orchestrator_skips_claude_when_key_is_placeholder`

**Files:** `tests/unit/test_pdf_agents.py`

**Why:** Test passes in isolation, fails in full suite. Blocks push reliability (the pre-push hook currently fails 30% of pushes). Almost certainly an env-leak — an earlier test leaves `ANTHROPIC_API_KEY` set in the process env.

- [ ] **Step 1: Reproduce + identify leak**

  ```bash
  uv run python -m pytest tests/unit -q -x --tb=short 2>&1 | grep -B2 test_orchestrator_skips_claude
  ```

  Look at which test ran immediately before and whether it mutates env.

- [ ] **Step 2: Add explicit monkeypatch.delenv**

  At the start of `test_orchestrator_skips_claude_when_key_is_placeholder`:

  ```python
  def test_orchestrator_skips_claude_when_key_is_placeholder(monkeypatch):
      monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
      monkeypatch.setenv("ANTHROPIC_API_KEY", "your_key_here")
      # ... rest unchanged
  ```

- [ ] **Step 3: Run suite 3× to confirm stable**

  ```bash
  for i in 1 2 3; do uv run python -m pytest tests/unit -q 2>&1 | tail -1; done
  ```

  All three should say `2144 passed`.

---

## Task 4: Remove dormant ACS inbound webhook

**Files:**
- Delete: `api/routers/inbound_email.py`
- Delete: `docs/runbooks/acs-inbound-email.md`
- Modify: `api/services/inbound_email_service.py` — trim ACS-specific helpers
- Modify: `api/main.py` — remove router registration
- Modify: `tests/unit/test_inbound_email_service.py` — drop ACS dispatcher tests

**Why:** The v5 ACS webhook is dead code — ACS doesn't emit `EmailReceived` events (verified across all 53 ACS Event Grid event types). It sits on prod as a 404-eventually-maybe endpoint that nothing will ever hit. Removing cuts the prod surface area and the future "what does this do?" confusion.

Keep: `match_and_ingest`, `_find_existing_by_message_id`, `_log_row`, `_resolve_tender`, `_ingest_and_notify`, `extract_tender_ref`, `format_tender_ref` — all shared with SendGrid (+ future Graph) paths.

Remove: `build_validation_response`, `_is_email_received_event`, `download_mime`, `parse_email_mime`, `_shallow_parsed`, `_download_and_parse`, `process_email_received_event`.

- [ ] **Step 1: Delete the router + runbook**

  ```bash
  git rm api/routers/inbound_email.py docs/runbooks/acs-inbound-email.md
  ```

- [ ] **Step 2: Trim the service**

  Remove the ACS-specific functions listed above. Keep shared helpers.

- [ ] **Step 3: Update main.py**

  Remove `from api.routers import inbound_email` and `app.include_router(inbound_email.router)`.

- [ ] **Step 4: Trim tests**

  In `tests/unit/test_inbound_email_service.py`, delete the Event Grid handshake tests and the `process_email_received_event` dispatcher tests. Keep regex tests, MIME parse tests (still useful for shared code), and match_and_ingest tests.

- [ ] **Step 5: Verify**

  ```bash
  uv run python -m pytest tests/unit -q
  uv run ruff check api/
  ```

  Should stay green with reduced test count (~8-10 fewer tests).

- [ ] **Step 6: Update runbook**

  Replace `docs/runbooks/acs-inbound-email.md` contents with a 3-line redirect to `sendgrid-inbound-email.md`.

---

## Task 5: Seed-demo-tender script

**Files:**
- Create: `scripts/seed_demo_tender.py`
- Use: existing `api/services/tender_service.py::TenderService.create_tender` + `.add_recipients`

**Why:** Current demo path: broker logs in, manually creates a company, manually creates a tender, manually adds recipients, manually uploads the anbudspakke PDF. Five minutes of friction before the actual "magic" (insurer reply → auto-ingest) is visible. A seed script cuts setup to 10 seconds.

- [ ] **Step 1: Create the script**

  ```python
  # scripts/seed_demo_tender.py
  """Seed a ready-to-demo tender for Bergmann Industri AS with 3 insurer
  recipients (If/Gjensidige/Tryg) routed to Gmail aliases you control."""

  from api.db import SessionLocal, Company, Tender, TenderRecipient
  from api.services.tender_service import TenderService
  ...
  ```

  Takes `--forwarding-email tharu281001@gmail.com` as arg. Recipients get `<email>+if@gmail.com`, `+gjensidige@gmail.com`, `+tryg@gmail.com` variants.

- [ ] **Step 2: Add TenderOffer upload step**

  Script can optionally attach the generated anbudspakke-PDF (from `generate_risk_report_pdf`) as the outgoing package, so "Send invitations" works immediately.

- [ ] **Step 3: Print the tender URL**

  Output: `https://meglerai.no/tenders/<id>` → broker clicks, hits "Send invitations", demo flows from there.

---

## Task 6: "Start demo" one-click button in /admin

**Files:**
- Modify: `frontend/src/components/admin/DemoDataSection.tsx`
- Create: `POST /admin/seed-demo-tender` endpoint (admin-role only)
- Wrap: `seed_demo_tender.py` logic into a callable service method

**Why:** Even simpler than the script — one click from the admin UI gives you a live tender ready to send. Pairs with the existing demo-data downloads (same section) so the full loop sits in one place.

- [ ] **Step 1: Add admin endpoint**

  ```python
  # api/routers/admin_email_log.py or new admin_demo.py
  @router.post("/admin/seed-demo-tender", response_model=SeededTenderOut)
  def seed_demo_tender(
      db: Session = Depends(get_db),
      _user: CurrentUser = Depends(require_role("admin")),
  ) -> SeededTenderOut:
      tender_id = _run_seed(db, broker_email=...)
      return SeededTenderOut(tender_id=tender_id, url=f"/tenders/{tender_id}")
  ```

- [ ] **Step 2: Add button to DemoDataSection**

  Primary button at the top: `Start ny demo-tender`. OnClick calls the endpoint, then `window.location = response.url`.

- [ ] **Step 3: Smoke test on prod after deploy**

  Click button → lands on `/tenders/<id>` with all 3 recipients pre-populated → Send invitations → reply from Gmail with one of the offer PDFs → see `status=matched` in `/admin/email-log` within 30 s.

---

## Execution order

Tasks 1, 2, 3, 4 are independent — can be done in any order (and in parallel as separate PRs).

Task 5 depends on nothing.

Task 6 depends on Task 5 (needs the seed-logic to call).

Suggested flow:
1. Task 3 first (cheap, fixes a recurring annoyance)
2. Task 2 in parallel (DNS change, no code)
3. Task 1 after Task 2 (so we're testing with the new SPF)
4. Task 4 next (cleanup, reduces noise in the remaining work)
5. Task 5 (building block)
6. Task 6 (uses Task 5)

Rough total effort: 3-4 hours of my time, ~10 min of user time (SendGrid key creation + verification).

---

## Out of scope

- Microsoft Graph / M365 setup (blocked on Antire IT — separate plan already exists at `docs/superpowers/plans/2026-04-23-msgraph-inbound-activation.md`)
- Moving demo PDFs off GitHub raw to Azure Blob (GitHub works fine; revisit if bandwidth or gating becomes a concern)
- Refactoring Phase 6-7 (separate backlog — doesn't block demo)

## Rollback

Each task ships as its own PR. If anything lands badly, revert the single PR — no cross-task dependencies except 5→6.
