# Anbud End-to-End — Expansion Roadmap

**Date:** 2026-04-25
**Status:** roadmap (each phase needs its own bite-sized TDD plan before
implementation)
**Driving question from Tharusan (2026-04-25):** "look at images and folder
and look closely to what our application doesn't have, implement everything,
then we can remove stuff." Plus a list of specific anbud-flow gaps.

---

## What's already in the app (don't rebuild)

A gap analysis pass against the codebase confirms several of the items the
user asked for are **already shipped**:

| Capability | Where | Notes |
|---|---|---|
| Anbud creation flow | `api/routers/tender_router.py` POST `/tenders` + `frontend/src/app/tenders/[id]/page.tsx` | Title, products, deadline, notes, recipient list |
| Send forespørsler to insurers | `api/services/tender_service.py:_send_tender_email` | HTML email with product table; uses `NotificationPort` (MS Graph in prod) |
| Inbound email parser | `api/services/mail_webhook.py` + `sendgrid_inbound_service.py` | Attachments routed to `TenderOffer`; Excel MIME recognised but parsed shallowly |
| AI comparison (backend) | `tender_service.py:analyse_offers` + `_COMPARISON_PROMPT` | Returns `anbefaling`, `sammenligning[]`, `nøkkelforskjeller[]` JSON |
| Decline status enum | `TenderRecipientStatus.declined` | Insurer can be flipped to `declined` (but no reason field yet) |
| Chat history persistence | `api/services/chat_history.py` + `UserChatMessage` | Per-user × per-orgnr; prepended to LLM prompts. **This is the "minnet sitter igjennom chattene" feature.** |
| DocuSeal contract sign-off | `api/services/docuseal_service.py` + `Tender.contract_session_id` | Webhook flips tender to `analysed` on signature complete |

**Implication for the build queue:** seven of the user's fifteen items are
already shipped to some degree. Don't restart them; finish them.

---

## What's missing (the actual roadmap)

Numbered to match the user's bullet list where possible:

### P1 — Complete the anbud loop (the **most-asked-for**, largest payoff)

#### P1.1 — Comparison-table UI (item 4)

Backend already returns the comparison JSON. Frontend just renders nothing.

- New component `frontend/src/components/tenders/OfferComparison.tsx`
- Table shape: rows = insurance products, columns = insurers, header row =
  premium total, footer row = recommendation badge on the AI-anbefalt column
- Triggered by the existing "Analyse" button on `/tenders/[id]/page.tsx`
- Effort: **~half day**

#### P1.2 — Cost breakdown per offer (item 5)

`TenderOffer.extracted_data` is a free-text JSON blob today. Promote the
shape to typed line-items so the comparison table has real data to render.

- Schema: add `OfferLineItem { product, premium, deductible, coverage_limit, vilkår_summary }` to `api/schemas.py`
- Migration: add `offer_line_items` JSONB column to `tender_offers` (no schema
  change to PDF parser yet — fall back to `extracted_data` until the typed
  shape is populated)
- Backfill: re-extract via Gemini using the new prompt that requests JSON in
  this exact shape; for old rows leave `offer_line_items=null` and render
  the legacy free-text fallback
- Effort: **~1 day** (prompt engineering is the long pole)

#### P1.3 — Decline reason capture (item 6)

Today `declined` is a status flag with no "why."

- Schema: add `decline_reason: enum[capacity, bad_match, high_risk, other]` and `decline_note: text` to `tender_recipients`
- Inbound email parser: detect "avslår" / "decline" body keywords + extract reason heuristically (or just store the body in `decline_note` and let the broker classify)
- UI: render the reason inline on the recipients list with a colored chip
- Effort: **~half day**

#### P1.4 — Excel offer export (item 7)

The user asked to send tilbud out **as Excel**. Pick a customer-facing
recipient and export the comparison as a styled `.xlsx`.

- Backend: `POST /tenders/{id}/export-comparison?format=xlsx` using `openpyxl`
- Reuses the same JSON the comparison-table UI consumes
- Frontend: "Eksporter sammenligning" button next to the Analyse button
- Effort: **~half day** (openpyxl styling is fiddly but well-trodden)

**P1 total: ~2.5 dev days. After this the inbound→outbound anbud loop is end-to-end visible.**

### P2 — Product catalog (item H — "15 produkter på personalforsikring, mange flere på andre")

Today `Tender.product_types` is `List[str]` with no schema. The user wants a
structured catalog — 15 products under personalforsikring, more under
skadeforsikring, etc.

- New table `insurance_products` with hierarchy `(category, sub_category, product_name, description, typical_coverage_limits)`
- Seed with the standard Norwegian broker catalog (personell + bygning + ansvar + transport + cyber + osv.)
- New endpoint `GET /products?category=personell` returning the catalog
- Tender creation form: replace free-text checkboxes with a tree-picker driven by the catalog
- Effort: **~2 days** (the long pole is curating the catalog content; the code is straightforward)

### P3 — Property + salgsoppgave data (items 6, F, G)

The user wants building-specific fields (year, fire alarm, flammable
materials) on the company profile. Some come from BRREG, but most do not —
they have to come from a separate property/sales-prospectus source.

- Schema: add `property_metadata` JSONB column to `companies` (loose shape so
  we can iterate without migrations)
- Source 1 (free): Kartverket Matrikkel API — gives building year + ground
  area + use code per gnr/bnr. Already plumbed for koordinater; expanding to
  Matrikkel proper is `external_apis.py` work
- Source 2 (paid, deferred): Eiendomsverdi or Ambita — gives valuation + sales
  history. **Don't integrate until a customer asks** — they cost money
- Salgsoppgave: there is no public API. The realistic option is "broker
  uploads PDF, we extract via Gemini." Treat it as another `InsuranceDocument`
  kind, lean on the existing PDF-extraction stack
- Effort: **~2 days for Matrikkel; salgsoppgave PDF intake is ~1 day**

### P4 — Customer-facing offer presentation (item K)

Today `/portal/[token]` is a read-only company snapshot. The user wants a
flow where the broker sends a polished tilbud presentation, customer reviews
it, and approves with one click.

- New route `/portal/[token]/tender/[tender_id]` that renders the comparison
  table with the broker's recommendation, plus an "Approve / Reject" CTA
- New table `tender_customer_decisions` to log approval state + signature
- On approval, kick off the existing DocuSeal contract flow automatically
  (currently a manual step per the gap analysis)
- Effort: **~2 days**

### P5 — Legal bot (item M — "juss bot")

A chat scoped to insurance + contract law. The simplest approach:

- Reuse the existing `/knowledge` chat infrastructure
- New "knowledge area" filter: `legal` — RAG-indexed against a curated corpus
  of Norwegian insurance law (FAL, Forsikringsavtaleloven, NHO standard
  vilkår, etc.)
- Effort: **~1.5 days for the corpus curation + UI; the chat machinery is reused**

### P6 — SharePoint integration (item O)

Defer until a real use case lands. The current MS Graph integration only has
`Mail.Send` scope; SharePoint requires `Sites.Read.All` or
`Files.Read.All`, plus a value question: what would we read from SharePoint
that isn't easier delivered as a SendGrid inbound or DocuSeal upload?

If the user comes back with a concrete need (e.g. "fetch the customer's
existing policy folder"), revisit. Until then: **skip**.

### Already shipped — do nothing

- **Item 11 (chat history persistence)** — `chat_history.py` already does
  this. Verify with the user that it matches their expectation; if so, move
  on.
- **Item 13 (contracts based on tilbud)** — DocuSeal integration is live;
  P4.1 connects it to the auto-approval flow.

---

## Suggested execution order

| Order | Phase | Effort | Why |
|---|---|---|---|
| 1 | P1.1 Comparison UI | ½ d | Backend already returns the JSON; just render it |
| 2 | P1.3 Decline reason | ½ d | Two columns + a chip, but unblocks reporting |
| 3 | P1.2 Cost breakdown | 1 d | Promotes free-text JSON to typed line items |
| 4 | P1.4 Excel export | ½ d | Closes the "tilbud as excel" loop |
| 5 | P2 Product catalog | 2 d | Foundation for product-specific UX everywhere |
| 6 | P4 Customer offer portal | 2 d | High user-facing value |
| 7 | P3 Matrikkel property data | 2 d | Adds depth to company profile |
| 8 | P5 Legal bot | 1.5 d | Defer if P1–P4 take longer than estimated |
| 9 | P6 SharePoint | 0 d | Defer |

**Total scoped: ~10 dev days** (parallel-PR friendly; most phases are
independent).

---

## What we're NOT building

Stating this upfront so scope doesn't creep:

- **A new design system** — Tailwind + shadcn stays. UI work uses existing primitives.
- **A bespoke realtime Excel viewer** — Excel imports/exports are server-side, render to HTML table or `.xlsx` download.
- **Multi-tenant catalog editing** — the product catalog ships seeded; per-firm overrides are a Phase-2 ask.
- **Salgsoppgave OCR pipeline** — leverage the existing Gemini PDF extraction stack rather than building a new one.

---

## How to start (if approved)

If Tharusan approves this roadmap, the recommended first step is **P1.1
Comparison UI**: it's the highest-visibility win and unblocks every later
phase. Spawn a subagent-driven-development run with that one phase scoped as
a TDD plan; merge; then iterate.

If Tharusan wants to ship more aggressively in parallel, P1.1 + P1.3 can run
in parallel because they touch different files.
