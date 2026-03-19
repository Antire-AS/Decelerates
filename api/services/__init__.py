"""services package — re-exports all public functions and service classes.

Service classes (inject via FastAPI Depends()):
  BrokerService      — broker settings + notes CRUD
  SlaService         — SLA agreement creation
  PdfSourcesService  — CompanyPdfSource upsert/delete
  DocumentService         — InsuranceDocument + InsuranceOffer storage CRUD
  DocumentAnalysisService — stateless LLM document analysis (no DB required)
  RagService         — chunk, embed, store, retrieve for chat
  LlmService         — embed, answer, compare offers
  ExternalApiService — BRREG/SSB/NB/Kartverket/PEP/Finanstilsynet
  CompanyService     — fetch org profile, list companies, seed PDF sources
  PdfExtractService  — PDF reading, Gemini extraction, IR discovery
  PdfGenerateService — SLA, risk report, and forsikringstilbud PDF generation

Sub-modules:
  llm.py           — _embed, _fmt_nok, _llm_answer_raw, _llm_answer, _parse_json_from_llm_response
  external_apis.py — fetch_* BRREG/SSB/NB/Kartverket/PEP/Finanstilsynet functions
  pdf_extract.py   — PDF reading, Gemini extraction, IR discovery, _auto_extract_pdf_sources
  rag.py           — RagService + backward-compat module-level helpers
  company.py       — _seed_pdf_sources, _upsert_company, fetch_org_profile, narratives
  pdf_generate.py  — _safe, _extract_offer_summary, _generate_sla_pdf
  broker.py        — BrokerService (settings + notes CRUD)
  sla_service.py   — SlaService (agreement creation)
  pdf_sources.py   — PdfSourcesService + backward-compat helpers
  documents.py     — DocumentService + backward-compat helpers
"""

# ── Service classes ────────────────────────────────────────────────────────────

from api.services.broker import BrokerService  # noqa: F401
from api.services.sla_service import SlaService  # noqa: F401
from api.services.pdf_sources import PdfSourcesService  # noqa: F401
from api.services.documents import DocumentService, DocumentAnalysisService  # noqa: F401
from api.services.rag import RagService  # noqa: F401
from api.services.llm import LlmService  # noqa: F401
from api.services.external_apis import ExternalApiService  # noqa: F401
from api.services.company import CompanyService  # noqa: F401
from api.services.pdf_extract import PdfExtractService  # noqa: F401
from api.services.pdf_generate import PdfGenerateService  # noqa: F401

# ── Module-level function re-exports (backward-compatible) ────────────────────

from api.services.llm import (  # noqa: F401
    _embed,
    _fmt_nok,
    _llm_answer_raw,
    _llm_answer,
    _parse_json_from_llm_response,
)

from api.services.external_apis import (  # noqa: F401
    fetch_enhetsregisteret,
    fetch_enhet_by_orgnr,
    fetch_regnskap_keyfigures,
    fetch_regnskap_history,
    pep_screen_name,
    fetch_finanstilsynet_licenses,
    fetch_koordinater,
    fetch_losore,
    _nace_to_section,
    fetch_ssb_benchmark,
    fetch_norgesbank_rate,
    fetch_company_struktur,
    fetch_board_members,
    _pick_latest_regnskap,
    _extract_periode,
    _extract_virksomhet,
    _extract_resultat,
    _extract_balanse,
    _extract_eiendeler,
    _fetch_ssb_live,
    _SSB_CACHE,
    _NB_RATE_CACHE,
)

from api.services.pdf_extract import (  # noqa: F401
    _parse_json_financials,
    _extract_pdf_text,
    _parse_financials_from_text,
    _parse_financials_from_pdf,
    fetch_history_from_pdf,
    _get_full_history,
    _search_for_pdfs,
    _discover_ir_pdfs,
    _auto_extract_pdf_sources,
)

from api.services.rag import (  # noqa: F401
    _build_company_context,
    _chunk_and_store,
    _retrieve_chunks,
    _save_to_rag,
    save_qa_note,
)

from api.services.company import (  # noqa: F401
    _seed_pdf_sources,
    _upsert_company,
    _fetch_financials_with_fallback,
    fetch_org_profile,
    _generate_risk_narrative,
    _generate_synthetic_financials,
    list_companies,
)

from api.services.pdf_generate import (  # noqa: F401
    _safe,
    _extract_offer_summary,
    _generate_sla_pdf,
    generate_risk_report_pdf,
    generate_forsikringstilbud_pdf,
)

