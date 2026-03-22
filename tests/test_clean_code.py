"""
Clean-code structural tests — enforce the architecture rules from CLAUDE.md.

Rules tested:
  1. No function body exceeds 40 lines (with documented justified exceptions).
  2. No router file writes directly to the DB (no db.add / db.commit calls).
  3. No router file makes direct LLM API calls (no anthropic / google.genai imports).
  4. No service file raises HTTPException.

These tests are pure static analysis (AST + text search) — no imports, no DB, no API keys.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ── helpers ──────────────────────────────────────────────────────────────────

def _py_files(subdir: str):
    return sorted((ROOT / subdir).rglob("*.py"))


def _ast_functions(path: Path):
    """Yield (name, start_line, length) for every function/method in *path*."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node.lineno, node.end_lineno - node.lineno + 1


def _source_contains(path: Path, pattern: str) -> list[int]:
    """Return line numbers where *pattern* (regex) matches in *path*."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [i + 1 for i, line in enumerate(lines) if re.search(pattern, line)]


# ── Rule 1: function length ───────────────────────────────────────────────────

# Functions that are genuinely longer than 40 lines but justified.
# See CLAUDE.md "Clean Code Principles Followed" for rationale.
_JUSTIFIED = {
    # Agentic tool-use loops — multi-step state machine, can't be split
    "_agent_discover_pdfs_claude",
    "_agent_discover_pdfs_gemini",
    "_agent_discover_pdfs",
    "_run_phase2_discovery",
    # PDF layout — fpdf2 imperative API; each set_font/cell/color is one mandatory line
    "_build_tilbud_broker_header",
    "_build_tilbud_client_box",
    "_build_tilbud_forside",
    "_build_tilbud_offers_page",
    "_build_offers_comparison_table",
    "_build_offers_strengths_section",
    "_build_tilbud_coverage_table",
    "_build_tilbud_coverage_detail",
    "_build_tilbud_terms_page",
    "_add_risk_cover",
    "_add_risk_company_profile",
    "_add_risk_financials",
    "_add_risk_factors_table",
    "_add_cover_page",
    "_add_section_oppdrag",
    "_add_vedlegg_a",
    "_add_vedlegg_b",
    "_add_vedlegg_e",
    "_add_signature_page",
    "_add_standardvilkar",
    "generate_risk_report_pdf",
    "generate_forsikringstilbud_pdf",
    # External API response field-mapping — long but not decomposable
    "_fetch_ssb_live",
    "fetch_company_struktur",
    "_gemini_web_search",
    "_search_pdf_url_for_year",
    # Risk scoring rule lists
    "_check_financial_health",
    "_check_industry_age_exposure",
    # Narrative prompt builder — just a long f-string template
    "_build_narrative_prompt",
    # RAG context builder — long field list
    "_build_company_context",
    # Diagnostic endpoint — long but intentionally so to surface many fields in one call
    "debug_status",
    # Knowledge index — blob iteration + per-section transcript assembly; can't be split
    "index_video_transcripts",
    # Knowledge UI — Streamlit chat + spinner + state management; tightly coupled flow
    "_render_knowledge_chat",
    "_render_knowledge_manage",
    # UI render functions — Streamlit's imperative API requires one call per widget;
    # these cannot be decomposed without losing cohesion (each section is tightly coupled)
    "render_search_tab",
    "render_profile_core",
    "render_profile_financials",
    "render_portfolio_tab",
    "render_videos_tab",
    "_render_video_player",
    "list_videos",
    "render_documents_tab",
    "render_sla_tab",
    "render_knowledge_tab",
    # Landing page — single-screen Streamlit tab with stats + feature cards + CTAs
    "render_landing_tab",
    # Portfolio view sub-sections — tightly coupled Streamlit imperative rendering
    "_render_overview",
    "_render_portfolio_selector",
    "_render_seed_norway",
    "_render_portfolio_chat",
    "_render_live_ingest",
    "_render_nl_query",
    "_render_admin_controls",
    # SSE streaming generators — async generator protocol requires all logic inline;
    # the inner generate() functions are reported separately by AST walker
    "stream_ingest_portfolio",
    "stream_seed_norway",
    "generate",
    # Admin seed endpoints — multi-phase BRREG lookup + background PDF agent setup;
    # complexity is inherent to the two-phase seeding protocol
    "admin_demo",
    "admin_seed_norway_top100",
    # Portfolio RAG chat — builds context + calls LLM in one coherent flow
    "chat",
    # Insurance needs rule engine — 8 insurance types, each rule is one atomic decision
    "estimate_insurance_needs",
    # Peer benchmark — DB peer query + SSB fallback + percentile math in one coherent flow
    "get_peer_benchmark",
    # Portfolio alerts — multi-rule YoY engine; rule list can't be decomposed
    "get_portfolio_alerts",
    # Portfolio concentration — three-dimension aggregation (industry/geo/size) in one pass
    "get_portfolio_concentration",
    # list_companies — SQLAlchemy builder with 7 optional filters + sort; flat and readable
    "list_companies",
    # Prospecting UI — Streamlit imperative API; filter + table + navigation in one flow
    "_render_prospecting",
    # Portfolio digest endpoint — iterates all portfolios + sends per-portfolio emails; flow is cohesive
    "send_portfolio_digest",
    # Alert collector — same 5-rule alert engine as portfolio_router; kept inline to avoid shared mutable state
    "_collect_alerts",
    # collect_alerts — 5-rule YoY engine extracted to service; rules list not decomposable
    "collect_alerts",
    # download_portfolio_pdf — orchestrates companies + alerts + concentration + broker data for PDF; cohesive flow
    "download_portfolio_pdf",
}

# Files excluded from function-length checks (non-production scripts)
_EXCLUDED_FILES = {"generate_sample_offers.py"}


def test_no_function_exceeds_40_lines():
    """Every production function must be ≤ 40 lines unless explicitly justified."""
    violations = []
    for path in ROOT.rglob("*.py"):
        if any(part in {".venv", "__pycache__", ".git", "tests", "alembic"} for part in path.parts):
            continue
        if path.name in _EXCLUDED_FILES:
            continue
        for name, lineno, length in _ast_functions(path):
            if length > 40 and name not in _JUSTIFIED:
                rel = path.relative_to(ROOT)
                violations.append(f"{rel}:{lineno}  {name}()  →  {length} lines")

    assert not violations, (
        "Functions exceeding 40 lines (add to _JUSTIFIED if truly unavoidable):\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ── Rule 2: no DB writes in routers ──────────────────────────────────────────

def test_no_db_writes_in_routers():
    """Routers must not call db.add() or db.commit() — those belong in services."""
    violations = []
    for path in _py_files("routers"):
        if path.name == "__init__.py":
            continue
        for lineno in _source_contains(path, r"\bdb\.(add|commit|delete|merge)\("):
            rel = path.relative_to(ROOT)
            violations.append(f"{rel}:{lineno}")

    assert not violations, (
        "DB writes found in routers (move to services/):\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ── Rule 3: no direct LLM calls in routers ───────────────────────────────────

# Allowed: importing helpers from services.llm (those ARE the approved wrappers)
# Forbidden: importing anthropic / google.genai / voyageai directly in a router
_LLM_DIRECT_IMPORT = re.compile(
    r"^\s*(import|from)\s+(anthropic|google\.genai|voyageai)\b"
)


def test_no_direct_llm_imports_in_routers():
    """Routers must not import LLM SDKs directly — use services.llm wrappers."""
    violations = []
    for path in _py_files("routers"):
        if path.name == "__init__.py":
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            if _LLM_DIRECT_IMPORT.search(line):
                rel = path.relative_to(ROOT)
                violations.append(f"{rel}:{i}  {line.strip()}")

    assert not violations, (
        "Direct LLM SDK imports found in routers (use services.llm instead):\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ── Rule 4: no HTTPException in services ─────────────────────────────────────

def test_no_http_exception_in_services():
    """Services must raise domain exceptions, not HTTPException."""
    violations = []
    for path in _py_files("services"):
        if path.name == "__init__.py":
            continue
        for lineno in _source_contains(path, r"\bHTTPException\b"):
            # Allow import lines (unlikely but safe)
            line = path.read_text(encoding="utf-8").splitlines()[lineno - 1].strip()
            if line.startswith(("import ", "from ")):
                continue
            rel = path.relative_to(ROOT)
            violations.append(f"{rel}:{lineno}  {line}")

    assert not violations, (
        "HTTPException found in services (raise domain exceptions instead):\n"
        + "\n".join(f"  {v}" for v in violations)
    )
