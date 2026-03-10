"""services package — re-exports all public functions for backward-compatible imports.

Sub-modules:
  llm.py           — _embed, _fmt_nok, _llm_answer_raw, _llm_answer, _parse_json_from_llm_response
  external_apis.py — fetch_* BRREG/SSB/NB/Kartverket/PEP/Finanstilsynet functions
  pdf_extract.py   — PDF reading, Gemini extraction, IR discovery, _auto_extract_pdf_sources
  rag.py           — _build_company_context, _chunk_and_store, _retrieve_chunks, _save_to_rag, save_qa_note
  company.py       — _seed_pdf_sources, _upsert_company, fetch_org_profile, narratives
  pdf_generate.py  — _safe, _extract_offer_summary, _generate_sla_pdf
  broker.py        — broker settings + notes CRUD
  sla_service.py   — SLA agreement creation
  pdf_sources.py   — CompanyPdfSource upsert/delete
  documents.py     — InsuranceDocument + InsuranceOffer CRUD + LLM document analysis
"""

from services.llm import (  # noqa: F401
    _embed,
    _fmt_nok,
    _llm_answer_raw,
    _llm_answer,
    _parse_json_from_llm_response,
)

from services.external_apis import (  # noqa: F401
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

from services.pdf_extract import (  # noqa: F401
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

from services.rag import (  # noqa: F401
    _build_company_context,
    _chunk_and_store,
    _retrieve_chunks,
    _save_to_rag,
    save_qa_note,
)

from services.company import (  # noqa: F401
    _seed_pdf_sources,
    _upsert_company,
    _fetch_financials_with_fallback,
    fetch_org_profile,
    _generate_risk_narrative,
    _generate_synthetic_financials,
    list_companies,
)

from services.pdf_generate import (  # noqa: F401
    _safe,
    _extract_offer_summary,
    _generate_sla_pdf,
)

from services.broker import (  # noqa: F401
    get_broker_settings,
    save_broker_settings,
    list_broker_notes,
    create_broker_note,
    delete_broker_note,
)

from services.sla_service import (  # noqa: F401
    create_sla_agreement,
)

from services.pdf_sources import (  # noqa: F401
    upsert_pdf_source,
    delete_history_year,
)
