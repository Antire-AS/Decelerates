# ruff: noqa: F401 — every name in this file is an intentional re-export.
"""Backward-compatibility shim — re-exports all public symbols from the split pdf_* modules.

The 1203-line original has been split into focused modules:
  pdf_parse.py       — JSON parsing, Gemini PDF extraction
  pdf_history.py     — DB upsert, history merge (BRREG + PDF rows)
  pdf_web.py         — DuckDuckGo helpers, HTML fetching (Playwright + requests fallback)
  pdf_agents.py      — Claude / Gemini / Azure OpenAI agent loops + orchestration
  pdf_background.py  — URL validation, parallel extraction, PdfExtractService

All existing imports (api.services.pdf_extract.*) continue to work unchanged.
The file-level ruff noqa above prevents the next ruff --fix run from stripping
re-exports that aren't directly used inside this file.
"""

from api.services.pdf_parse import (
    _parse_json_financials,
    _gemini_api_keys,
    _parse_financials_from_pdf,
    _sanity_check_financials,
    _download_pdf_bytes,
    _try_gemini,
)
from api.services.pdf_history import (
    fetch_history_from_pdf,
    _get_full_history,
    _upsert_history_row,
)
from api.services.pdf_web import (
    _DDG_UA,
    _ddg_query,
    _search_for_pdfs,
    _search_all_annual_pdfs,
    _ddg_search_results,
    _fetch_html,
    _fetch_url_content,
    _parse_agent_pdf_list,
)
from api.services.pdf_agents import (
    _agent_discover_pdfs,
    _agent_discover_pdfs_claude,
    _agent_discover_pdfs_gemini,
    _agent_discover_pdfs_azure_openai,
    _discover_ir_pdfs,
    _discover_pdfs_per_year_search,
    _gemini_web_search,
    _run_tool,
)
from api.services.pdf_background import (
    _validate_pdf_urls,
    _run_phase2_discovery,
    _extract_pending_sources,
    _auto_extract_pdf_sources,
    PdfExtractService,
)

__all__ = [
    # pdf_parse
    "_parse_json_financials",
    "_gemini_api_keys",
    "_parse_financials_from_pdf",
    # pdf_history
    "fetch_history_from_pdf",
    "_get_full_history",
    # pdf_web
    "_DDG_UA",
    "_ddg_query",
    "_fetch_html",
    "_fetch_url_content",
    # pdf_agents
    "_agent_discover_pdfs",
    "_discover_ir_pdfs",
    # pdf_background
    "_validate_pdf_urls",
    "_run_phase2_discovery",
    "_extract_pending_sources",
    "_auto_extract_pdf_sources",
    "PdfExtractService",
]
