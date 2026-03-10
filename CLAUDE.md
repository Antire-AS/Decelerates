# Broker Accelerator

A Norwegian company due-diligence tool. Given a company name or org number it pulls data from public Norwegian registries, computes a simple risk score, screens for PEP/sanctions, and persists the result to a local database.

## Architecture

```
ui.py  (Streamlit)
  │  HTTP calls to localhost:8000
  ▼
app.py  (FastAPI, 69 lines — thin router mount only)
  │
  ├── routers/          HTTP layer — validates input, calls services, returns HTTP responses
  │     broker.py       broker settings + notes endpoints
  │     company.py      /org/{orgnr}, /search, /companies
  │     financials.py   /org/{orgnr}/pdf-history, /pdf-sources, /history
  │     knowledge.py    /org/{orgnr}/ask (RAG/chat)
  │     offers.py       insurance offer upload + comparison
  │     risk_router.py  risk narrative + structure endpoints
  │     sla.py          SLA agreement endpoints
  │
  ├── services/         Business logic — no FastAPI imports
  │     llm.py          _embed, _llm_answer_raw, _llm_answer, _compare_offers_with_llm,
  │                    _analyze_document_with_gemini, _compare_documents_with_gemini
  │     external_apis.py  BRREG, SSB, Norges Bank, Kartverket, OpenSanctions, Finanstilsynet
  │     pdf_extract.py  agentic IR discovery, Playwright fetch, Gemini PDF extraction
  │     rag.py          chunk, embed, store, retrieve for chat
  │     company.py      fetch_org_profile, _upsert_company, synthetic financials
  │     broker.py       broker settings + notes CRUD
  │     sla_service.py  SLA agreement creation
  │     pdf_generate.py SLA, risk report, and forsikringstilbud PDF generation (fpdf2)
  │     pdf_sources.py  CompanyPdfSource upsert/delete
  │
  ├── domain/           Pure Python — no framework dependencies
  │     exceptions.py  NotFoundError, QuotaError, LlmUnavailableError,
  │                    PdfExtractionError, ExternalApiError
  │
  └── db.py / risk.py / constants.py / prompts.py / schemas.py
```

Two processes need to run:
1. The FastAPI backend (`app.py`) on port 8000
2. The Streamlit frontend (`ui.py`) on port 8501

---

## Clean Code Principles Followed

- **No HTTPException in services** — services raise domain exceptions (`QuotaError`, `NotFoundError`, etc.); routers catch and convert to HTTP status codes
- **No DB queries in routers** — all `db.query()` calls live in services; routers only call service functions
- **No LLM calls in routers** — all Gemini/Claude API calls are in `services/llm.py`; routers call service helpers
- **Functions ≤ 40 lines** — long functions decomposed into named helpers (e.g. PDF endpoints → `generate_risk_report_pdf`, `generate_forsikringstilbud_pdf` with page-builder helpers in `services/pdf_generate.py`)
- **Parallel extraction** — `_extract_pending_sources` uses `ThreadPoolExecutor(max_workers=3)`; each thread gets its own DB session
- **Testable background tasks** — `_auto_extract_pdf_sources(db_factory=SessionLocal)` accepts injected session factory
- **Graceful degradation** — Playwright fails → requests fallback; agent fails → DuckDuckGo fallback; BRREG empty → PDF history fallback; no LLM key → silent skip
- **Multi-key Gemini rotation** — `_gemini_api_keys()` reads `GEMINI_API_KEY`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`; all Gemini calls rotate through keys on 429/quota errors

---

## Files

### [app.py](app.py) — FastAPI entry point (69 lines)

Mounts all routers. On startup calls `init_db()` and `_seed_pdf_sources()`. Contains no business logic.

### [routers/](routers/) — HTTP layer

Each router file handles one domain area. Routers only: validate input → call service → return response. They catch domain exceptions and convert to HTTPException.

### [services/pdf_extract.py](services/pdf_extract.py) — PDF discovery + extraction

**Agentic IR discovery pipeline:**
1. `_agent_discover_pdfs(orgnr, navn, hjemmeside, target_years)` — tries Claude first (`ANTHROPIC_API_KEY`), then all Gemini keys in order
2. `_agent_discover_pdfs_claude` — Claude tool-use loop using native `web_search_20250305` + custom `fetch_url` (Playwright-backed)
3. `_agent_discover_pdfs_gemini` — two-phase Gemini loop:
   - Phase 1: `gemini-2.5-flash` Google Search grounding → finds IR page URL (plain text)
   - Phase 2: `_run_gemini_phase2(chat, navn, phase1_text)` — up to 4 `fetch_url` turns to extract real `pdf_links` from the IR page
4. `_GEMINI_FETCH_URL_TOOL` — module-level `genai_types.Tool` constant shared by the Gemini agent
5. `_validate_pdf_urls(discovered)` — HTTP HEAD check; filters out 404/unreachable URLs before storing
6. `_fetch_html(url)` — Playwright (headless Chromium) → requests fallback
7. `_discover_ir_pdfs()` — last resort: DuckDuckGo PDF links + LLM validation

**Gemini key rotation:**
- `_gemini_api_keys()` returns all configured keys (`GEMINI_API_KEY`, `GEMINI_API_KEY_2`, ...)
- `_try_gemini`, `_gemini_web_search`, `_agent_discover_pdfs` all iterate through keys on quota errors
- `gemini-2.5-flash` tried first for Google Search grounding (free tier supports it); `gemini-2.0-flash` has `limit: 0` for grounding

**Extraction pipeline:**
- `_parse_financials_from_pdf(pdf_url, orgnr, year)` — Gemini native PDF (inline ≤18MB, Files API >18MB); pdfplumber fallback
- `_upsert_history_row(existing, parsed, pdf_url)` — copies parsed fields onto ORM object (caller commits)
- `fetch_history_from_pdf(orgnr, pdf_url, year, label, db)` — orchestrates extraction → upsert into `company_history`
- `_extract_pending_sources(orgnr, sources, db)` — parallel extraction (3 workers, own DB session per thread)
- `_auto_extract_pdf_sources(orgnr, org, db_factory)` — background task; re-runs discovery if ≥3 of last 5 years missing

**Key functions:**
- `_parse_json_financials(raw)` — parses LLM JSON output, computes equity_ratio
- `_get_full_history(orgnr, db)` — merges PDF + BRREG history, deduplicated by year, sorted descending
- `_validate_pdf_urls(discovered)` — HEAD-validates each URL; drops unreachable ones before DB insert

### [services/external_apis.py](services/external_apis.py)

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
- `fetch_enhetsregisteret(name, kommunenummer, size)` — search by name
- `fetch_enhet_by_orgnr(orgnr)` — full org record including flags
- `fetch_regnskap_keyfigures(orgnr)` — most recent year, ~35 flattened fields
- `fetch_regnskap_history(orgnr)` — all years, full P&L + balance sheet
- `_pick_latest_regnskap`, `_extract_resultat`, `_extract_balanse`, `_extract_eiendeler` — pure transform helpers
- `fetch_ssb_benchmark(nace_code)` — SSB industry equity ratio + margin ranges
- `_nace_to_section(nace_code)` — NACE code → section letter A–S
- `pep_screen_name(name)` — OpenSanctions query
- `fetch_finanstilsynet_licenses(orgnr)`
- `fetch_koordinater(org)` — Kartverket geocoding
- `fetch_losore(orgnr)` — asset encumbrances

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
| GET | `/broker/settings` | Retrieve broker firm settings |
| POST | `/broker/settings` | Save broker firm settings |
| POST | `/org/{orgnr}/offers` | Upload insurance offer PDF |
| GET | `/org/{orgnr}/offers` | List all uploaded insurance offers |
| DELETE | `/org/{orgnr}/offers/{offer_id}` | Delete an insurance offer |
| GET | `/org/{orgnr}/offers/{offer_id}/pdf` | Download the raw offer PDF |
| POST | `/org/{orgnr}/offers/compare` | Upload + compare up to 3 offer PDFs via LLM |
| POST | `/org/{orgnr}/offers/compare-stored` | Compare already-stored offers by ID |
| POST | `/sla` | Create a new SLA agreement (generates PDF, stores in DB) |
| GET | `/sla` | List all SLA agreements |
| GET | `/sla/{sla_id}` | Get a single SLA agreement |
| GET | `/sla/{sla_id}/pdf` | Download the generated SLA agreement PDF |
| GET | `/org/{orgnr}/broker-notes` | List broker notes for org |
| POST | `/org/{orgnr}/broker-notes` | Create a broker note |
| DELETE | `/org/{orgnr}/broker-notes/{note_id}` | Delete a broker note |

---

### [ui.py](ui.py) — Streamlit frontend

Single-page app. Uses `st.session_state` to hold search results and the selected org number between rerenders.

**Sections rendered:**

*Company Search tab:*
1. Search bar → calls `/search` → lists results with "View profile" buttons. Collapses to single line on selection.
2. Organisation info — two columns: left = company details; right = `st.map()` from Kartverket geocoding
3. Bankruptcy & liquidation status
4. Board members (styremedlemmer) from BRREG
5. Risk summary metrics + risk flags + SSB industry benchmark
6. Key figures table for most recent accounting year
7. Financial history — YoY comparison table (Source badge: PDF/BRREG) + bar charts + equity ratio trend + year drill-down
8. "Add Annual Report PDF" expander — paste any public PDF URL to manually enrich history
9. Insurance offers — upload, compare, view structured comparison
10. PEP / sanctions screening results
11. AI-generated risk narrative and financial estimates
12. Finanstilsynet licences
13. Raw JSON debug views

*Agreements tab:* SLA agreement generator + list existing agreements with download links

*Settings tab (sidebar):* Broker firm settings saved to DB, embedded in SLA PDFs

---

### [risk.py](risk.py) — Risk scoring

- `derive_simple_risk(org, regn, pep)` — rule-based score + reasons list
- `build_risk_summary(org, regn, risk, pep)` — flat summary dict for UI metrics

---

### [db.py](db.py) — SQLAlchemy models

Nine tables: `companies`, `company_history`, `company_pdf_sources`, `company_notes`, `company_chunks`, `broker_settings`, `broker_notes`, `sla_agreements`, `insurance_offers`, `insurance_documents`.

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
| `currency` | String(10) | e.g. `"NOK"`, `"USD"`, `"SEK"` |
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

`broker_settings` table (singleton row):

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

`sla_agreements` table:

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
| `fee_structure` | JSON | per-line fee type and rate |
| `status` | String | `"draft"`, `"active"`, or `"terminated"` |
| `form_data` | JSON | full snapshot for PDF regeneration |

`insurance_offers` table:

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | auto |
| `orgnr` | String(9) | indexed |
| `filename` | String | original filename |
| `insurer_name` | String | insurer name |
| `uploaded_at` | String | ISO timestamp |
| `pdf_content` | LargeBinary | raw PDF bytes |
| `extracted_text` | String | cached pdfplumber text extraction |

`DATABASE_URL` is read from the environment; falls back to `postgresql://tharusan@localhost:5432/brokerdb`.

---

## Running locally

### With Docker (recommended for all platforms)

```bash
docker compose up --build
```

This starts:
- `broker-postgres` — Postgres 14 on port 5432
- `broker-api` — FastAPI on port 8000 (with `--reload`)

Then run the UI separately:

```bash
streamlit run ui.py
```

### Without Docker — macOS / Linux

1. Have a Postgres instance running and set `DATABASE_URL`.
2. Install dependencies and Playwright browser:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Copy `.env.example` to `.env` and fill in your API keys.
4. Start the API:
   ```bash
   uvicorn app:app --reload
   ```
5. Start the UI:
   ```bash
   streamlit run ui.py
   ```

### Without Docker — Windows

Windows requires a few extra steps due to Playwright system dependencies and PostgreSQL.

**Prerequisites:**
- Python 3.11+ from [python.org](https://www.python.org/downloads/) — tick "Add Python to PATH" during install
- PostgreSQL 14+ from [postgresql.org](https://www.postgresql.org/download/windows/) — note the password you set for `postgres`
- Git from [git-scm.com](https://git-scm.com/)

**Step 1 — Create a virtual environment:**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

**Step 2 — Install dependencies:**
```cmd
pip install -r requirements.txt
```

**Step 3 — Install Playwright system dependencies and Chromium:**
```cmd
playwright install-deps
playwright install chromium
```
> `install-deps` downloads the Visual C++ runtime and other Windows libs Chromium needs. This requires an internet connection and may take a few minutes.

**Step 4 — Create the database:**

Open pgAdmin (installed with PostgreSQL) or run in PowerShell:
```powershell
& "C:\Program Files\PostgreSQL\14\bin\psql.exe" -U postgres -c "CREATE DATABASE brokerdb;"
```

**Step 5 — Set environment variables:**

Copy `.env.example` to `.env` and edit it. Then load it before starting the server:
```cmd
# In PowerShell
$env:DATABASE_URL = "postgresql://postgres:yourpassword@localhost:5432/brokerdb"
$env:GEMINI_API_KEY = "your_key_here"
$env:ANTHROPIC_API_KEY = "your_key_here"   # optional but recommended
```

Or use a `.env` file — `uvicorn` and Streamlit both pick it up automatically via `python-dotenv` if installed, or set the variables in Windows System Properties → Environment Variables for persistence.

**Step 6 — Start the API:**
```cmd
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

**Step 7 — Start the UI (separate terminal):**
```cmd
.venv\Scripts\activate
streamlit run ui.py
```

**Common Windows issues:**

| Problem | Fix |
|---------|-----|
| `psycopg2` build fails | Use `psycopg2-binary` (already in requirements.txt) |
| `playwright install-deps` fails | Run the terminal as Administrator |
| `uvicorn` not found | Make sure the venv is activated: `.venv\Scripts\activate` |
| Port 8000 blocked | Check Windows Firewall or change port with `--port 8001` |
| `DATABASE_URL` not picked up | Set via System Properties → Environment Variables → restart terminal |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | REST API framework |
| `uvicorn` | ASGI server for FastAPI |
| `sqlalchemy` | ORM + DB connection |
| `psycopg[binary]` | Postgres driver (psycopg3 — cross-platform: Mac Intel/ARM, Windows x64/ARM64, Linux) |
| `requests` | HTTP calls to external APIs and DuckDuckGo |
| `pydantic` | Data validation (via FastAPI) |
| `streamlit` | UI framework |
| `pandas` | DataFrame for P&L / balance sheet tables |
| `anthropic` | Claude API — preferred LLM for text generation + agentic IR discovery |
| `google-genai` | Gemini API — native PDF understanding + text generation + embeddings |
| `voyageai` | Voyage embeddings (preferred over Gemini for RAG if `VOYAGE_API_KEY` is set) |
| `pdfplumber` | PDF text extraction — fallback only when Gemini native PDF fails |
| `python-multipart` | Multipart form data parsing for FastAPI file uploads |
| `fpdf2` | PDF generation for SLA agreements |
| `playwright` | Headless Chromium — fetches JS-rendered investor relations pages for PDF discovery |
| `langchain-core` | Core dependency for langchain-text-splitters |
| `langchain-text-splitters` | Text chunking for RAG embeddings |

---

## LLM / Model Configuration

The app uses a priority-based fallback for all LLM calls:

**Agentic IR discovery** (`_agent_discover_pdfs`):
1. Claude tool-use loop (`ANTHROPIC_API_KEY`) — preferred; navigates IR pages with web_search + fetch_url tools
2. Gemini tool-use loop (`GEMINI_API_KEY`) — fallback
3. DuckDuckGo + LLM validation — last resort when no keys set

**PDF extraction** (`_parse_financials_from_pdf`):
1. `gemini-2.5-flash` (primary — multimodal, reads PDF natively)
2. `gemini-1.5-flash` (fallback)
3. pdfplumber text extraction → text LLM (last resort)

**Text generation** (`_llm_answer_raw` — narrative, synthetic financials):
1. Claude (`ANTHROPIC_API_KEY`) if set
2. `gemini-2.5-flash`, then older Gemini/Gemma models

**Embeddings** (`_embed` — RAG/chat):
1. Voyage AI (`VOYAGE_API_KEY`) if set
2. `text-embedding-004` via Gemini

Configure via environment variables: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `VOYAGE_API_KEY`.

---

## PDF Seed Data

`PDF_SEED_DATA` in `constants.py` contains confirmed direct PDF URLs for demo companies. Seeded on every startup (true upsert). Currently covers:

| Company | Orgnr | Years |
|---------|-------|-------|
| DNB Bank ASA | 984851006 | 2019–2024 |
| Gjensidige Forsikring ASA | 995568217 | 2019–2024 |
| Søderberg & Partners Norge AS | 979981344 | 2023 (SEK, group report) |
| Equinor ASA | 923609016 | 2024 (Sanity CDN; 46 MB → Files API) |

PDF extraction is **one-time per year** — once stored in `company_history` it is never re-fetched. To force re-extraction, delete the row from `company_history` and visit the profile.

Phase 2 IR discovery (agent) runs automatically for any company not in seed data when ≥3 of the last 5 years are missing from `company_pdf_sources`. Up to 3 PDFs are extracted in parallel.

---

## Tests

```bash
python -m pytest tests/ -v
```

78 tests covering:
- `tests/test_risk.py` — risk scoring rules (54 tests)
- `tests/test_pdf_extract.py` — `_parse_json_financials` (6 tests)
- `tests/test_llm.py` — LLM embed + answer functions with mocked providers (6 tests)
- `tests/test_company.py` — seed, upsert, financials fallback with mocked DB (5 tests)
- `tests/test_external_apis.py` — pure data-transform functions (7 tests)

`tests/conftest.py` stubs out heavy optional deps (`google.genai`, `voyageai`, `anthropic`, `pdfplumber`, `playwright`) so tests run without API keys or installed packages.

---

## Notes

- The risk model in `derive_simple_risk` is intentionally simple — it's a starting point, not a production credit model.
- OpenSanctions screening searches on the company *name*, not individuals, so it's a rough proxy for direct sanctions exposure.
- The `/org/{orgnr}` endpoint silently swallows errors from the financials and PEP APIs so a 404 or timeout on one source doesn't block the whole profile load.
- BRREG Regnskapsregisteret only returns the most recent financial year per company. Banks (e.g. DNB) return a 500 error — PDF extraction is the only option for them.
- When BRREG returns no financial data, `fetch_org_profile` falls back to the most recent `company_history` row so Risk Summary metrics are populated from PDF-extracted data.
- PDFs >18 MB automatically use the Gemini Files API instead of inline upload — no size limit.
- `_get_full_history` passes all fields from `company_history.raw` through to the UI, so Gemini-extracted detail fields appear in the year drill-down table.
- SSB industry benchmarks are hardcoded typical ranges per NACE section (A–S). They are a rough guide, not live data.
- Kartverket geocoding uses the first address line + postnummer to resolve lat/lon. If geocoding fails the map column shows "Location not found".
- Løsøreregisteret always requires Maskinporten JWT auth in practice. The UI does not show an encumbrances section.
- Annual report PDF bytes are **not stored** in the database — only the URL (`company_pdf_sources`) and extracted financial figures (`company_history`) are persisted. Insurance offer PDFs are stored in full (`insurance_offers.pdf_content`).
