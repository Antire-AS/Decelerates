# Phase 6 — Remaining items from the product feedback sweep

**Goal:** Close out the deferred items from `2026-04-20-product-feedback-sweep.md` in priority order.

## Priority tiers

### Tier A — Ship today (one PR)
1. **Tender purring cron** — APScheduler job, sends reminder email 7d + 2d before deadline for pending tender recipients
2. **Whiteboard → risk PDF export** — extend `generate_risk_report` to accept `whiteboard_items` + `whiteboard_notes`
3. **RAG broader-question tuning** — when no chunks match, answer from LLM general knowledge with a clear disclaimer
4. **PDF upload in knowledge chat** — wire the currently-absent attach button to upload PDF → extract text → ingest as knowledge chunk
5. **Admin activity-log simplification** — default to "today only" view with "Show older" expand

### Tier B — Follow-up PRs (if time allows)
6. **Tilbudsfremstilling PDF for client** — new `generate_tilbudsfremstilling(tender_id)` method on `PdfGenerateService`, creates client-facing compare PDF
7. **Mail webhook ingest** — POST endpoint accepting email payload (Azure Communication Services webhook format), parses Excel attachments via pandas, maps to tender by reply-to address

### Tier C — Needs design + infra
8. **Contract generation via DocuSeal** — requires DocuSeal template + webhook back on client signature
9. **Mobile polish** — responsive audit of the new Fokus and anbud portal pages

## Execution approach

- One bundled PR for Tier A (all small, all cleanly deployable)
- Tests pass locally before push
- Staging deploy verifies
- Promote to main once green

## Tier A task details

### 1. Purring cron
- `api/services/tender_reminders.py` — new module with `send_deadline_reminders()` function
- Query: tenders with `status=sent` AND `deadline IN (now+2d, now+7d)` AND recipients with `status=sent` (not `received`)
- Send email via `NotificationPort`
- Log to `audit_log`
- Register in existing APScheduler (check `api/services/risk_monitor.py` or similar for pattern)

### 2. Whiteboard → risk PDF
- Modify `api/services/pdf_generate.py` `generate_risk_report(orgnr, user_oid=None)` to optionally load whiteboard
- Render new section "Meglerens fokuspunkter" with items + notes + AI summary
- Frontend: "Last ned risikorapport" button on Fokus tab already triggers existing endpoint; no frontend change needed if we just add content to the PDF

### 3. RAG general-knowledge fallback
- Modify `api/routers/knowledge.py` `chat_knowledge` — when `chunks` is empty, if the LLM has general knowledge to offer, return it with a disclaimer "Dette er basert på generell forsikringskunnskap, ikke indeksert kildemateriale."
- Only fall back if question is forsikring-adjacent (simple keyword check)

### 4. PDF upload in knowledge chat
- Add small attach button to `ChatTab.tsx`
- Upload to `/insurance-documents/upload` (existing)
- After upload, POST `/knowledge/index?force=false` to re-index
- Show "Dokumentet er indeksert og klart for chat" confirmation

### 5. Admin activity-log simplification
- Current state: flat list, long
- Change: default filter "last 24 hours", "Show older" button expands

## Verification
- `uv run python -m pytest tests/unit -q` → 1936+ passing
- Staging smoke: trigger purring manually for a test tender, verify email sent
- Prod: after bundle promote, monitor deploy workflow
