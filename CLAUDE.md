# Broker Accelerator — Developer Reference

> **User-facing docs** (setup, features, workflow, deployment): see `README.md`.
> **API reference**: auto-generated OpenAPI at `http://localhost:8000/docs`.
> This file covers architecture, patterns, and non-obvious helpers for contributors.

---

## Developer Setup

1. Install the Antire Claude plugin (once per machine):
   ```bash
   bash scripts/install-antire-plugin.sh
   ```
2. Restart Claude Code.
3. At the start of each Claude Code session, run `/antire-python-init` to load Antire coding standards.

---

## Architecture

```mermaid
graph TD
    UI[ui/main.py · Streamlit :8501] -->|HTTP| API[api/main.py · FastAPI :8000]
    API --> R[api/routers/]
    R --> S[api/services/]
    S --> DB[(PostgreSQL + pgvector)]
    S --> BRREG[BRREG API]
    S --> Gemini[Gemini API]
    S --> Claude[Claude API]
```

Sequence diagrams for key flows (PlantUML — render with IntelliJ, VS Code PlantUML extension, or [plantuml.com](https://www.plantuml.com/plantuml)):
- [`docs/company_lookup_flow.puml`](docs/company_lookup_flow.puml) — `GET /org/{orgnr}` end-to-end
- [`docs/pdf_extraction_flow.puml`](docs/pdf_extraction_flow.puml) — agentic IR discovery + PDF extraction

Class diagrams (auto-generated from source):
```bash
bash scripts/gen_diagrams.sh   # writes docs/classes.mmd + docs/packages.mmd
```

```
api/
  main.py          ← entry: uvicorn api.main:app
  routers/         ← HTTP layer (validate → call service → return response)
    broker.py      broker settings + notes (uses BrokerService)
    company.py     /org/{orgnr}, /search, /companies
    financials.py  /org/{orgnr}/pdf-history, /pdf-sources, /history
    knowledge.py   /org/{orgnr}/chat (RAG/chat)
    offers.py      insurance offer upload + comparison
    risk_router.py risk narrative + structure endpoints
    sla.py         SLA agreement endpoints (uses SlaService)
    documents.py   InsuranceDocument endpoints
  services/        ← Business logic — no FastAPI imports
    broker.py      BrokerService  (db in __init__)
    sla_service.py SlaService     (db in __init__)
    pdf_sources.py PdfSourcesService + backward-compat functions
    documents.py   DocumentService + backward-compat functions
    rag.py         RagService     + backward-compat functions
    llm.py         LlmService     + module-level helpers
    external_apis.py ExternalApiService + module-level helpers
    company.py     CompanyService + module-level helpers
    pdf_extract.py PdfExtractService + module-level helpers
    pdf_generate.py PdfGenerateService + module-level helpers
  domain/
    exceptions.py  NotFoundError, QuotaError, LlmUnavailableError,
                   PdfExtractionError, ExternalApiError
  db.py / risk.py / constants.py / prompts.py / schemas.py

ui/
  main.py          ← entry: streamlit run ui/main.py
  styles.css       ← extracted CSS (loaded at runtime)
  translations.json ← extracted i18n dict (loaded at runtime)
```

---

## Clean Code Principles Followed

- **No HTTPException in services** — services raise domain exceptions (`QuotaError`, `NotFoundError`, etc.); routers catch and convert to HTTP status codes
- **No DB writes in routers** — all `db.add()` / `db.commit()` calls live in services; routers never touch ORM objects directly
- **No LLM calls in routers** — all Gemini/Claude API calls are in `services/llm.py`; routers call service helpers
- **Service classes own one domain** — each `*Service` class takes `db: Session` in `__init__` and exposes clean methods. Inject via `Depends()` in routers.
- **Backward-compat module functions** — `pdf_sources.py`, `documents.py`, `rag.py` expose both the class and standalone functions (same signature as before) so internal callers don't break
- **Functions ≤ 40 lines** — long functions decomposed into named helpers; the two agent loops (`_agent_discover_pdfs_claude`, `_agent_discover_pdfs_gemini`) are ~70 lines but justified by tool-use loop logic
- **Parallel extraction** — `_extract_pending_sources` uses `ThreadPoolExecutor(max_workers=3)`; each thread gets its own DB session
- **Testable background tasks** — `_auto_extract_pdf_sources(db_factory=SessionLocal)` accepts injected session factory
- **Graceful degradation** — Playwright fails → requests fallback; agent fails → DuckDuckGo fallback; BRREG empty → PDF history fallback; no LLM key → silent skip
- **Multi-key Gemini rotation** — `_gemini_api_keys()` reads `GEMINI_API_KEY`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`; all Gemini calls rotate through keys on 429/quota errors

---

## Architecture Deviations (intentional)

The following are intentional deviations from Antire Python standards — documented here so future contributors understand the reasoning:

| Deviation | Antire Standard | Why we deviate |
|-----------|----------------|----------------|
| **Routers/services pattern** | Hexagonal architecture (ports, adapters, use cases) | FastAPI's `Depends()` injection covers DI needs without punq; hexagonal adds ceremony without benefit at this scale |
| **Env vars read in services** | All `os.getenv` in `main.py` only | LLM keys are optional and read lazily — services check `_is_key_set()` at call time and gracefully skip missing keys; centralising them in `main.py` would require plumbing optional config through every service constructor |
| **UI render functions F/E complexity** | All functions ≤ cyclomatic C (10) | Streamlit's imperative widget API means each section branch is one mandatory call; splitting render functions breaks cohesion and increases navigation overhead |
| **High-complexity agent loops** | All functions ≤ cyclomatic C (10) | `_agent_discover_pdfs_*` are tool-use state machines; branching reflects the multi-turn protocol, not accidental complexity |

---

## Service Classes

| Class | File | Key Methods |
|-------|------|-------------|
| `BrokerService` | `api/services/broker.py` | `get_settings`, `save_settings`, `list_notes`, `create_note`, `delete_note` |
| `SlaService` | `api/services/sla_service.py` | `create_agreement` |
| `PdfSourcesService` | `api/services/pdf_sources.py` | `upsert_pdf_source`, `save_insurance_document`, `delete_history_year` |
| `DocumentService` | `api/services/documents.py` | `store_document`, `remove_document`, `save_offers`, `remove_offer`, `get_document_keypoints`, `answer_document_question`, `compare_two_documents` |
| `RagService` | `api/services/rag.py` | `chunk_and_store`, `retrieve_chunks`, `save_qa_note`, `save_to_rag` |
| `LlmService` | `api/services/llm.py` | `embed`, `answer_raw`, `answer`, `compare_offers`, `parse_json` |
| `ExternalApiService` | `api/services/external_apis.py` | `search`, `fetch_enhet`, `fetch_regnskap`, `pep_screen`, `fetch_koordinater`, `fetch_board_members`, `fetch_ssb_benchmark` |
| `CompanyService` | `api/services/company.py` | `fetch_org_profile`, `list_companies`, `seed_pdf_sources` |
| `PdfExtractService` | `api/services/pdf_extract.py` | `fetch_history_from_pdf`, `get_full_history`, `parse_financials_from_pdf` |
| `PdfGenerateService` | `api/services/pdf_generate.py` | `generate_sla`, `generate_risk_report`, `generate_forsikringstilbud` |

---

## Key Private Helpers (non-obvious)

| Helper | File | Purpose |
|--------|------|---------|
| `_is_key_set(key)` | `api/services/llm.py` | Returns True only if key is set and not `"your_key_here"` — used before every LLM call |
| `_gemini_generate_with_fallback(parts, timeout)` | `api/services/llm.py` | Shared Gemini model loop: tries `gemini-2.5-flash` → `gemini-1.5-flash` → `GEMINI_MODEL`; used by `_analyze_document_with_gemini`, `_compare_documents_with_gemini`, `_compare_offers_with_llm` |
| `_org_dict_from_db(db_obj)` | `api/routers/risk_router.py` | Builds the `org` dict from a `Company` ORM object — used by all three risk endpoints to avoid duplication |
| `save_insurance_document(orgnr, navn, filename, pdf_bytes, db)` | `api/services/pdf_sources.py` | Persists a generated forsikringstilbud PDF as an `InsuranceDocument` row — keeps DB writes out of the router |
| `_build_company_context(db_obj, notes)` | `api/services/rag.py` | Builds structured text context for the LLM from a `Company` ORM object + retrieved notes |

---

## Files

### [api/main.py](api/main.py) — FastAPI entry point

Mounts all routers. On startup calls `init_db()` and `_seed_pdf_sources()`. Contains no business logic.

### [api/routers/](api/routers/) — HTTP layer

Each router handles one domain. Routers only: validate input → instantiate service → call method → return response. They catch domain exceptions and convert to HTTPException.

Service injection pattern used in broker.py and sla.py:
```python
def _get_broker_service(db: Session = Depends(get_db)) -> BrokerService:
    return BrokerService(db)

@router.get("/broker/settings")
def get_settings(svc: BrokerService = Depends(_get_broker_service)):
    ...
```

### [api/services/pdf_extract.py](api/services/pdf_extract.py) — PDF discovery + extraction

**Agentic IR discovery pipeline:**
1. `_agent_discover_pdfs(orgnr, navn, hjemmeside, target_years)` — tries Claude first (`ANTHROPIC_API_KEY`), then all Gemini keys in order
2. `_agent_discover_pdfs_claude` — Claude tool-use loop using native `web_search_20250305` + custom `fetch_url` (Playwright-backed)
3. `_agent_discover_pdfs_gemini` — two-phase Gemini loop:
   - Phase 1: `gemini-2.5-flash` Google Search grounding → finds IR page URL
   - Phase 2: `_run_gemini_phase2(chat, navn, phase1_text)` — up to 4 `fetch_url` turns to extract real `pdf_links`
4. `_validate_pdf_urls(discovered)` — HTTP HEAD check; filters out 404/unreachable URLs before storing
5. `_fetch_html(url)` — Playwright (headless Chromium) → requests fallback

**Extraction pipeline:**
- `_parse_financials_from_pdf(pdf_url, orgnr, year)` — Gemini native PDF (inline ≤18MB, Files API >18MB); pdfplumber fallback
- `fetch_history_from_pdf(orgnr, pdf_url, year, label, db)` — orchestrates extraction → upsert into `company_history`
- `_extract_pending_sources(orgnr, sources, db)` — parallel extraction (3 workers, own DB session per thread)
- `_auto_extract_pdf_sources(orgnr, org, db_factory)` — background task; re-runs discovery if ≥3 of last 5 years missing

### [api/services/external_apis.py](api/services/external_apis.py)

**External data sources:**

| Source | What it provides | Auth |
|--------|-----------------|------|
| BRREG Enhetsregisteret | Company registry — name, org form, address, industry code, bankruptcy flags | None |
| BRREG Regnskapsregisteret | Financial statements (P&L + balance sheet) | None |
| Finanstilsynet | Financial licences held by the company | None |
| OpenSanctions | PEP / sanctions screening by name | None |
| Kartverket Geonorge | Geocoding Norwegian addresses to lat/lon | None |
| Løsøreregisteret | Asset encumbrances (pledges on movable assets) | Maskinporten (returns auth_required if missing) |

**API endpoints**: See `http://localhost:8000/docs` for the full auto-generated reference.

### [ui/main.py](ui/main.py) — Streamlit frontend

Single-page app. Uses `st.session_state` to hold search results and the selected org number between rerenders.

- **CSS** is loaded at runtime from `ui/styles.css`
- **Translations** are loaded at runtime from `ui/translations.json` via `_TRANSLATIONS = json.loads(...)`
- **`T(key)`** helper returns the translated label for the current language (`st.session_state["lang"]`)

**Sections rendered:**

*Company Search tab:*
1. Search bar → calls `/search` → lists results with "View profile" buttons
2. Organisation info — two columns: left = company details; right = `st.map()` from Kartverket geocoding
3. Bankruptcy & liquidation status
4. Board members (styremedlemmer) from BRREG
5. Risk summary metrics + risk flags + SSB industry benchmark
6. Key figures table for most recent accounting year
7. Financial history — YoY comparison table + bar charts + equity ratio trend + year drill-down
8. "Add Annual Report PDF" expander — paste any public PDF URL to manually enrich history
9. Insurance offers — upload, compare, view structured comparison
10. PEP / sanctions screening results
11. AI-generated risk narrative and financial estimates
12. Finanstilsynet licences
13. Raw JSON debug views

*Agreements tab:* SLA agreement generator + list existing agreements with download links

*Settings tab (sidebar):* Broker firm settings saved to DB, embedded in SLA PDFs

### [api/risk.py](api/risk.py) — Risk scoring

- `derive_simple_risk(org, regn, pep)` — rule-based score + reasons list
- `build_risk_summary(org, regn, risk, pep)` — flat summary dict for UI metrics

### [api/db.py](api/db.py) — SQLAlchemy models

Nine tables: `companies`, `company_history`, `company_pdf_sources`, `company_notes`, `company_chunks`, `broker_settings`, `broker_notes`, `sla_agreements`, `insurance_offers`, `insurance_documents`.

`DATABASE_URL` is read from the environment; falls back to `postgresql://tharusan@localhost:5432/brokerdb`.

---

## Running locally

```bash
# Start both API + UI
bash scripts/run_all.sh

# Or individually
bash scripts/run_api.sh   # FastAPI on port 8000
bash scripts/run_ui.sh    # Streamlit on port 8501

# Tests (no API keys required)
uv run python -m pytest tests/ -v
```

With Docker:
```bash
docker compose up --build
```

---

## LLM / Model Configuration

The app uses a priority-based fallback for all LLM calls:

**Agentic IR discovery** (`_agent_discover_pdfs`):
1. Claude tool-use loop (`ANTHROPIC_API_KEY`) — preferred
2. Gemini tool-use loop (`GEMINI_API_KEY`) — fallback
3. DuckDuckGo + LLM validation — last resort

**PDF extraction** (`_parse_financials_from_pdf`):
1. `gemini-2.5-flash` (primary — multimodal, reads PDF natively)
2. `gemini-1.5-flash` (fallback)
3. pdfplumber text extraction → text LLM (last resort)

**Text generation** (`_llm_answer_raw`):
1. Claude (`ANTHROPIC_API_KEY`) if set
2. `gemini-2.5-flash`, then older Gemini/Gemma models

**Embeddings** (`_embed`):
1. Voyage AI (`VOYAGE_API_KEY`) if set
2. `text-embedding-004` via Gemini

Configure via environment variables: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `VOYAGE_API_KEY`.

---

## PDF Seed Data

`PDF_SEED_DATA` in `api/constants.py` contains confirmed direct PDF URLs for demo companies. Seeded on every startup (true upsert). Currently covers:

| Company | Orgnr | Years |
|---------|-------|-------|
| DNB Bank ASA | 984851006 | 2019–2024 |
| Gjensidige Forsikring ASA | 995568217 | 2019–2024 |
| Søderberg & Partners Norge AS | 979981344 | 2023 (SEK, group report) |
| Equinor ASA | 923609016 | 2024 (Sanity CDN; 46 MB → Files API) |

PDF extraction is **one-time per year** — once stored in `company_history` it is never re-fetched. To force re-extraction, delete the row from `company_history` and visit the profile.

---

## Tests

```bash
uv run python -m pytest tests/ -v
```

82 tests covering:
- `tests/test_risk.py` — risk scoring rules (54 tests)
- `tests/test_pdf_extract.py` — `_parse_json_financials` (6 tests)
- `tests/test_llm.py` — LLM embed + answer functions with mocked providers (6 tests)
- `tests/test_company.py` — seed, upsert, financials fallback with mocked DB (5 tests)
- `tests/test_external_apis.py` — pure data-transform functions (7 tests)
- `tests/test_clean_code.py` — AST + static analysis (4 tests)

`tests/conftest.py` stubs out heavy optional deps (`google.genai`, `voyageai`, `anthropic`, `pdfplumber`, `playwright`) so tests run without API keys or installed packages.

---

## Notes

- The risk model in `derive_simple_risk` is intentionally simple — it's a starting point, not a production credit model.
- OpenSanctions screening searches on the company *name*, not individuals, so it's a rough proxy for direct sanctions exposure.
- The `/org/{orgnr}` endpoint silently swallows errors from the financials and PEP APIs so a 404 or timeout on one source doesn't block the whole profile load.
- BRREG Regnskapsregisteret only returns the most recent financial year per company. Banks (e.g. DNB) return a 500 error — PDF extraction is the only option for them.
- When BRREG returns no financial data, `fetch_org_profile` falls back to the most recent `company_history` row so Risk Summary metrics are populated from PDF-extracted data.
- PDFs >18 MB automatically use the Gemini Files API instead of inline upload — no size limit.
- SSB industry benchmarks are hardcoded typical ranges per NACE section (A–S). They are a rough guide, not live data.
- Annual report PDF bytes are **not stored** in the database — only the URL (`company_pdf_sources`) and extracted financial figures (`company_history`) are persisted. Insurance offer PDFs are stored in full (`insurance_offers.pdf_content`).
