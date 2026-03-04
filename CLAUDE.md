# Broker Accelerator

A Norwegian company due-diligence tool. Given a company name or org number it pulls data from public Norwegian registries, computes a simple risk score, screens for PEP/sanctions, and persists the result to a local database.

## Architecture

```
ui.py  (Streamlit)
  │  HTTP calls to localhost:8000
  ▼
app.py  (FastAPI)
  ├── fetches from external APIs
  ├── derives risk score
  └── upserts into PostgreSQL via db.py
```

Two processes need to run:
1. The FastAPI backend (`app.py`) on port 8000
2. The Streamlit frontend (`ui.py`) on port 8501

---

## Files

### [app.py](app.py) — FastAPI backend (main logic)

All business logic lives here. On startup it calls `init_db()` and `_seed_pdf_sources()`.

**External data sources:**

| Source | What it provides | Auth |
|--------|-----------------|------|
| BRREG Enhetsregisteret | Company registry — name, org form, address, industry code, bankruptcy flags | None |
| BRREG Regnskapsregisteret | Financial statements (P&L + balance sheet) | None |
| Finanstilsynet | Financial licences held by the company | None |
| OpenSanctions | PEP / sanctions screening by name | None |
| Kartverket Geonorge | Geocoding Norwegian addresses to lat/lon | None |
| Løsøreregisteret | Asset encumbrances (pledges on movable assets) | Maskinporten (returns auth_required if missing) |

**Key functions:**

- `fetch_enhetsregisteret(name, kommunenummer, size)` — search companies by name (and optionally municipality code), returns a list of matches.
- `fetch_enhet_by_orgnr(orgnr)` — look up a single company by its 9-digit org number. Also extracts: `adresse`, `kommunenummer`, `poststed`, `stiftelsesdato`, `konkurs`, `under_konkursbehandling`, `under_avvikling`, `hjemmeside`.
- `fetch_regnskap_keyfigures(orgnr)` — fetch financial statements, pick the most recent year, and flatten ~35 accounting fields into a dict.
- `fetch_regnskap_history(orgnr)` — fetch all available financial years from BRREG, returning full P&L and balance sheet fields for each year.
- `_parse_json_financials(raw)` — shared helper: parses and validates the JSON financial dict returned by any LLM; computes equity_ratio.
- `_extract_pdf_text(pdf_url)` — downloads a public annual report PDF and extracts text via `pdfplumber` (up to 60 pages). Used as fallback only.
- `_parse_financials_from_text(text, orgnr, year)` — fallback: sends pdfplumber-extracted text to LLM; returns key financial figures as absolute currency values.
- `_parse_financials_from_pdf(pdf_url, orgnr, year)` — primary PDF extraction path. Uses Gemini native PDF understanding (no text extraction needed, preserves table structure, no page cap). Automatically uses inline upload for PDFs ≤18 MB and Files API for larger PDFs. Falls back to pdfplumber + text LLM if Gemini is unavailable.
- `fetch_history_from_pdf(orgnr, pdf_url, year, label, db)` — orchestrates PDF extraction via `_parse_financials_from_pdf` → upsert into `company_history` DB table.
- `_get_full_history(orgnr, db)` — merges `company_history` (DB rows, including all raw fields) with BRREG history, deduplicated by year (DB row wins), sorted descending.
- `_seed_pdf_sources(db)` — called at startup; upserts `PDF_SEED_DATA` entries into `company_pdf_sources` (true upsert — always syncs URL/label).
- `_search_for_pdfs(navn, hjemmeside, year)` — searches DuckDuckGo HTML for annual report PDF URLs. Extracts: (1) direct `https://...pdf` links, (2) `uddg=`-encoded redirect URLs that end in `.pdf`, (3) `result__url` div text content (bare `domain/path.pdf` shown in DDG results). Tries site-specific query first if `hjemmeside` is set, then a broader fallback query.
- `_discover_ir_pdfs(orgnr, navn, hjemmeside, target_years)` — Phase 2 IR discovery: collects PDF candidate URLs from `_search_for_pdfs` for each of the last 5 target years, then asks LLM to validate which are real annual reports. Returns confirmed list of `{year, pdf_url, label}` dicts.
- `_auto_extract_pdf_sources(orgnr, org)` — background task triggered on every `/org/{orgnr}` load. Phase 1: processes seeded PDFs from `company_pdf_sources` (skips already-extracted years). Phase 2 (if no seeds exist): runs `_discover_ir_pdfs` using `org["navn"]` and `org["hjemmeside"]`, caches discovered URLs in `company_pdf_sources`, then extracts them. Extraction is one-time — already-stored years are never re-fetched.
- `fetch_koordinater(org)` — geocodes company address via Kartverket Geonorge API. Returns `{lat, lon, adressetekst}` or `None`.
- `fetch_losore(orgnr)` — queries Løsøreregisteret for asset encumbrances. Returns `{auth_required: True}` on 401/403, `{count: 0}` on 404, or pledge list on success.
- `fetch_ssb_benchmark(nace_code)` — maps NACE code to section letter (A–S), returns SSB-informed typical equity ratio and profit margin ranges for the industry.
- `derive_simple_risk(org, regn)` — rule-based risk scoring:
  - +5 if bankrupt or under bankruptcy proceedings
  - +3 if under liquidation
  - +1 if AS/ASA (limited liability)
  - +2 if turnover > 100 MNOK, +1 if > 10 MNOK
  - +2 if negative equity, +1 if equity ratio < 20%
- `build_risk_summary(org, regn, risk, pep)` — assembles a flat summary dict used by the UI metrics cards. Includes `konkurs`, `under_konkursbehandling`, `under_avvikling` flags.
- `pep_screen_name(name)` — queries OpenSanctions for PEP/sanctions hits on a company name.
- `fetch_finanstilsynet_licenses(orgnr)` — retrieves financial licences from Finanstilsynet.

**API endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ping` | Health check |
| GET | `/search?name=&kommunenummer=&size=` | Search companies by name |
| GET | `/org/{orgnr}` | Full profile: org info + financials + risk + PEP. Also upserts to DB and fires background PDF extraction. |
| GET | `/org/{orgnr}/licenses` | Finanstilsynet licences for org |
| GET | `/org/{orgnr}/bankruptcy` | Bankruptcy and liquidation status flags |
| GET | `/org/{orgnr}/koordinater` | Geocoded HQ coordinates from Kartverket |
| GET | `/org/{orgnr}/losore` | Asset encumbrances from Løsøreregisteret |
| GET | `/org/{orgnr}/benchmark` | SSB-informed industry benchmark for NACE code |
| GET | `/org/{orgnr}/history` | Merged multi-year financial history (PDF + BRREG, deduplicated) |
| POST | `/org/{orgnr}/pdf-history` | Add PDF URL + year, extract financials via Gemini, store in DB |
| GET | `/org/{orgnr}/pdf-sources` | List known PDF annual report sources for an org |
| GET | `/companies?limit=&kommune=` | List previously looked-up companies from DB |
| GET | `/org-by-name?name=` | Convenience: search by name, return profile of first hit |
| GET | `/broker/settings` | Retrieve broker firm settings (name, orgnr, contact details) |
| POST | `/broker/settings` | Save broker firm settings |
| POST | `/org/{orgnr}/offers` | Upload insurance offer PDF for an org |
| GET | `/org/{orgnr}/offers` | List all uploaded insurance offers for an org |
| DELETE | `/org/{orgnr}/offers/{offer_id}` | Delete an insurance offer |
| GET | `/org/{orgnr}/offers/{offer_id}/pdf` | Download the raw offer PDF |
| POST | `/org/{orgnr}/offers/compare` | Upload + compare up to 3 offer PDFs via LLM, return structured comparison |
| POST | `/org/{orgnr}/offers/compare-stored` | Compare already-stored offers by ID via LLM |
| POST | `/sla` | Create a new SLA agreement (generates PDF, stores in DB) |
| GET | `/sla` | List all SLA agreements |
| GET | `/sla/{sla_id}` | Get a single SLA agreement |
| GET | `/sla/{sla_id}/pdf` | Download the generated SLA agreement PDF |

---

### [ui.py](ui.py) — Streamlit frontend

Single-page app. Uses `st.session_state` to hold search results and the selected org number between rerenders.

**Sections rendered:**

*Company Search tab:*
1. Search bar → calls `/search` → lists results with "View profile" buttons. When a result is selected, the results list collapses to a single compact line (company name + orgnr + result count) with a "Ny søk" button to expand again.
2. Organisation info — two columns: left = company details (name, form, orgnr, address, industry, founded date); right = `st.map()` showing HQ pin from Kartverket geocoding
3. Bankruptcy & liquidation status — `st.error()` if bankrupt, `st.warning()` if under liquidation, `st.success()` if clean
4. Board members (styremedlemmer) from BRREG
5. Risk summary metrics (turnover, employees, equity ratio, risk score, PEP hits) + risk flags + industry benchmark comparison (equity ratio and profit margin vs SSB typical range)
6. Key figures table for the most recent accounting year (P&L and balance sheet)
7. Financial history — YoY comparison table (with Source badge: PDF/BRREG) + bar charts (revenue, net result, debt breakdown) + equity ratio trend + year drill-down (selectbox → full P&L + balance sheet for selected year)
8. "Add Annual Report PDF" expander — paste any public PDF URL to manually enrich history
9. Insurance offers — upload up to 3 offer PDFs, trigger LLM comparison, view structured comparison table; also compare stored offers by selecting from uploaded list
10. PEP / sanctions screening results
11. AI-generated narrative and financial estimates
12. Finanstilsynet licences
13. Raw JSON debug views

*Agreements tab:*
- SLA agreement generator: fill in client details, start date, account manager, insurance lines, and fee structure (provisjon/honorar per line); generates a Norwegian PDF agreement and stores it in DB
- List all existing SLA agreements with download links

*Settings tab (sidebar):*
- Broker firm settings: firm name, orgnr, address, contact name/email/phone; saved to `broker_settings` DB table and embedded in generated SLA PDFs

---

### [risk.py](risk.py) — Risk scoring logic

- `derive_simple_risk(org, regn)` — computes score and reasons list from org + financial data. Bankruptcy/liquidation flags are checked first.
- `build_risk_summary(org, regn, risk, pep)` — assembles flat summary dict including all org, financial, risk, and PEP fields.

---

### [db.py](db.py) — SQLAlchemy models

Seven tables: `companies`, `company_history`, `company_pdf_sources`, `company_notes`, `broker_settings`, `sla_agreements`, `insurance_offers`.

`companies` table:

| Column | Type | Notes |
|--------|------|-------|
| `orgnr` | String(9) | unique, indexed |
| `navn` | String | company name |
| `organisasjonsform_kode` | String(10) | e.g. AS, ASA, ENK |
| `kommune` | String | municipality |
| `land` | String | country |
| `naeringskode1` | String | NACE industry code |
| `naeringskode1_beskrivelse` | String | human-readable industry |
| `regnskapsår` | Integer | year of financials |
| `sum_driftsinntekter` | Float | total operating income |
| `sum_egenkapital` | Float | total equity |
| `sum_eiendeler` | Float | total assets |
| `equity_ratio` | Float | egenkapital / eiendeler |
| `risk_score` | Integer | derived score |
| `regnskap_raw` | JSON | full flattened financials dict |
| `pep_raw` | JSON | full OpenSanctions response |

`company_history` table (multi-year financial snapshots per orgnr):

| Column | Type | Notes |
|--------|------|-------|
| `orgnr` | String(9) | indexed |
| `year` | Integer | unique with orgnr |
| `source` | String | `"brreg"` or `"pdf"` |
| `pdf_url` | String | source PDF URL if applicable |
| `revenue` | Float | absolute NOK (not millions) |
| `net_result` | Float | absolute NOK |
| `equity` | Float | absolute NOK |
| `total_assets` | Float | absolute NOK |
| `equity_ratio` | Float | computed from equity/assets |
| `short_term_debt` | Float | absolute NOK or null |
| `long_term_debt` | Float | absolute NOK or null |
| `antall_ansatte` | Integer | employees |
| `currency` | String(10) | e.g. `"NOK"`, `"SEK"` |
| `raw` | JSON | full Gemini-extracted dict (all P&L + balance sheet fields) |

`company_pdf_sources` table (known annual report PDFs per orgnr):

| Column | Type | Notes |
|--------|------|-------|
| `orgnr` | String(9) | indexed |
| `year` | Integer | unique with orgnr |
| `pdf_url` | String | public PDF URL |
| `label` | String | human-readable label |
| `added_at` | String | ISO timestamp |

`company_notes` table (Q&A pairs with embeddings for RAG/chat):

| Column | Type | Notes |
|--------|------|-------|
| `orgnr` | String(9) | indexed |
| `question` | String | user question |
| `answer` | String | LLM-generated answer |
| `created_at` | String | ISO timestamp |
| `embedding` | Vector | pgvector embedding for similarity search |

`broker_settings` table (singleton row for the broker's own firm info):

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | always 1 (singleton) |
| `firm_name` | String | broker firm name |
| `orgnr` | String(9) | broker's own org number |
| `address` | String | broker address |
| `contact_name` | String | contact person |
| `contact_email` | String | contact email |
| `contact_phone` | String | contact phone |
| `updated_at` | String | ISO timestamp |

`sla_agreements` table (generated service-level agreements):

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | auto |
| `created_at` | String | ISO timestamp |
| `broker_snapshot` | JSON | copy of BrokerSettings at creation time |
| `client_orgnr` | String(9) | client company org number |
| `client_navn` | String | client company name |
| `client_adresse` | String | client address |
| `client_kontakt` | String | client contact person |
| `start_date` | String | agreement start date |
| `account_manager` | String | assigned account manager |
| `insurance_lines` | JSON | list of covered insurance lines |
| `fee_structure` | JSON | per-line fee type (provisjon/honorar) and rate |
| `status` | String | `"draft"`, `"active"`, or `"terminated"` |
| `form_data` | JSON | full snapshot for PDF regeneration |

`insurance_offers` table (uploaded insurer offer PDFs per orgnr):

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | auto |
| `orgnr` | String(9) | indexed |
| `filename` | String | original filename |
| `insurer_name` | String | insurer name (e.g. "If Skadeforsikring") |
| `uploaded_at` | String | ISO timestamp |
| `pdf_content` | LargeBinary | raw PDF bytes |
| `extracted_text` | String | cached pdfplumber text extraction |

`DATABASE_URL` is read from the environment; falls back to `postgresql://tharusan@localhost:5432/brokerdb`.

---

## Running locally

### With Docker (recommended)

```bash
docker compose up --build
```

This starts:
- `broker-postgres` — Postgres 14 on port 5432
- `broker-api` — FastAPI on port 8000 (with `--reload`)

Then run the UI separately (Streamlit is not in Docker):

```bash
streamlit run ui.py
```

### Without Docker

1. Have a Postgres instance running and set `DATABASE_URL`.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the API:
   ```bash
   uvicorn app:app --reload
   ```
4. Start the UI:
   ```bash
   streamlit run ui.py
   ```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | REST API framework |
| `uvicorn` | ASGI server for FastAPI |
| `sqlalchemy` | ORM + DB connection |
| `psycopg2-binary` | Postgres driver |
| `requests` | HTTP calls to external APIs |
| `pydantic` | Data validation (via FastAPI) |
| `streamlit` | UI framework |
| `pandas` | DataFrame for P&L / balance sheet tables |
| `anthropic` | Claude API (used if `ANTHROPIC_API_KEY` is set; preferred over Gemini for text generation) |
| `google-genai` | Gemini API — native PDF understanding + text generation + embeddings |
| `voyageai` | Voyage embeddings (preferred over Gemini for RAG if `VOYAGE_API_KEY` is set) |
| `pdfplumber` | PDF text extraction — fallback only when Gemini native PDF fails |
| `python-multipart` | Multipart form data parsing for FastAPI file uploads |
| `fpdf2` | PDF generation for SLA agreements |

---

## LLM / Model Configuration

The app uses a priority-based fallback for all LLM calls:

**PDF extraction** (`_parse_financials_from_pdf`):
1. `gemini-2.5-flash` (primary — multimodal, reads PDF natively, 20 RPD free tier)
2. `gemini-1.5-flash` (fallback)
3. pdfplumber text extraction → text LLM (last resort)

**Text generation** (`_llm_answer_raw` — narrative, IR discovery, synthetic financials):
1. Claude (`ANTHROPIC_API_KEY`) if set
2. `gemma-3-12b-it` (14,400 RPD free tier)
3. `gemma-3-27b-it` (14,400 RPD free tier)
4. `gemini-2.5-flash`, then older Gemini models

**Embeddings** (`_embed` — RAG/chat):
1. Voyage AI (`VOYAGE_API_KEY`) if set
2. `text-embedding-004` via Gemini

Configure via environment variables: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `VOYAGE_API_KEY`.

---

## PDF Seed Data

`PDF_SEED_DATA` in `app.py` contains confirmed direct PDF URLs for demo companies. Seeded on every startup (true upsert). Currently covers:

| Company | Orgnr | Years |
|---------|-------|-------|
| DNB Bank ASA | 984851006 | 2019–2024 |
| Gjensidige Forsikring ASA | 995568217 | 2019–2024 |
| Søderberg & Partners Norge AS | 979981344 | 2023 (SEK, group report) |

PDF extraction is **one-time per year** — once stored in `company_history` it is never re-fetched. To force re-extraction, delete the row from `company_history` and visit the profile.

---

## Notes

- The risk model in `derive_simple_risk` is intentionally simple — it's a starting point, not a production credit model.
- OpenSanctions screening searches on the company *name*, not individuals, so it's a rough proxy for direct sanctions exposure.
- The `/org/{orgnr}` endpoint silently swallows errors from the financials and PEP APIs so a 404 or timeout on one source doesn't block the whole profile load.
- BRREG Regnskapsregisteret only returns the most recent financial year per company via the public API. Banks (e.g. DNB) return a 500 error because the `BANK` accounting layout is not supported — PDF extraction is the only option for them.
- When BRREG returns no financial data, `fetch_org_profile` falls back to the most recent `company_history` row so the Risk Summary metrics (turnover, equity ratio, risk score) are populated from PDF-extracted data instead of showing blank.
- The `_FINANCIALS_PROMPT` includes insurance/bank-specific field alternatives (e.g. "net premiums earned", "profit for the year", "technical result") so Gjensidige-style reports are handled correctly alongside standard AS companies.
- PDFs >18 MB (e.g. Gjensidige integrated reports ~40 MB) automatically use the Gemini Files API instead of inline upload — no size limit.
- `_get_full_history` passes all fields from `company_history.raw` through to the UI, so Gemini-extracted detail fields (driftsresultat, sum_gjeld, etc.) appear in the year drill-down table.
- Phase 2 IR discovery searches the last 5 full years for any company not in `PDF_SEED_DATA`.
- SSB industry benchmarks are hardcoded typical ranges per NACE section (A–S). They are a rough guide, not live data.
- Kartverket geocoding uses the first address line + postnummer to resolve lat/lon. If geocoding fails the map column shows "Location not found".
- Løsøreregisteret always requires Maskinporten JWT auth in practice. The UI does not show an encumbrances section.
- The Finanstilsynet API response shape isn't fully documented — the code tries both `entities` and `items` keys as a fallback.
