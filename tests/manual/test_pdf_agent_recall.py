"""Opt-in recall harness: how often does each IR-PDF agent find ≥1 PDF?

Part of the B4 plan
(docs/superpowers/plans/2026-04-21-pdf-agents-cleanup.md). Runs each of
the three agent implementations (Azure OpenAI, Anthropic Claude, Gemini
AI-Studio) against a fixed 20-company Norwegian corpus and prints
per-provider hit counts. The decision — whether to keep or delete the
Claude + Gemini branches — depends on the marginal recall they
contribute over Azure-only.

This file is EXCLUDED from the default pytest discovery path by being
under `tests/manual/`. It is additionally gated on PDF_AGENT_RECALL=1
as a belt-and-suspenders check. It is NEVER run in CI.

Expected runtime: ~5 min per provider × 3 providers = ~15 min.
Expected cost: a few USD of API credit.

Usage:

    PDF_AGENT_RECALL=1 \\
      ANTHROPIC_API_KEY=sk-ant-... \\
      GEMINI_API_KEY=AI... \\
      AZURE_OPENAI_API_KEY=... AZURE_OPENAI_ENDPOINT=https://... \\
      uv run python -m pytest tests/manual/test_pdf_agent_recall.py -sv

Each individual test also skips if its provider's key is unset — so
running only one provider is fine. Results land in the test's `print()`
output; use `-s` to see them.
"""

import json
import os
import pathlib
import time
from datetime import datetime, timezone
from typing import Callable, List, Tuple

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("PDF_AGENT_RECALL") != "1",
    reason="set PDF_AGENT_RECALL=1 and supply provider API keys to run",
)


# Twenty Norwegian companies with public IR pages. Mix of large (DNB,
# Equinor, Gjensidige), mid (Schibsted, Orkla, Kongsberg), small
# (Multiconsult, Borgestad). Chosen for provider diversity: Claude tends
# to win on known IR portals, Gemini on Google-Search-indexed
# Sanity/Contentful sites, Azure on corporate domains with plain
# filenames. Tuple: (orgnr, navn, hjemmeside).
RECALL_CORPUS: List[Tuple[str, str, str]] = [
    ("984851006", "DNB Bank ASA", "https://www.dnb.no"),
    ("995568217", "Gjensidige Forsikring ASA", "https://www.gjensidige.no"),
    ("923609016", "Equinor ASA", "https://www.equinor.com"),
    ("916862037", "Telenor ASA", "https://www.telenor.com"),
    ("933192410", "Schibsted ASA", "https://www.schibsted.com"),
    ("930357618", "Orkla ASA", "https://www.orkla.com"),
    ("999001369", "Yara International ASA", "https://www.yara.com"),
    ("930860675", "Grieg Seafood ASA", "https://www.griegseafood.com"),
    ("947990982", "Kongsberg Gruppen ASA", "https://www.kongsberg.com"),
    ("996525450", "Storebrand ASA", "https://www.storebrand.no"),
    ("956936264", "Veidekke ASA", "https://www.veidekke.com"),
    ("963936060", "Kvaerner ASA", "https://www.kvaerner.com"),
    ("934382404", "NEL ASA", "https://nelhydrogen.com"),
    ("937681140", "Tomra Systems ASA", "https://www.tomra.com"),
    ("913540538", "Aker BP ASA", "https://www.akerbp.com"),
    ("970921093", "REC Silicon ASA", "https://www.recsilicon.com"),
    ("986470668", "Glommen Mjøsen Skog SA", "https://www.glommen-mjosen.no"),
    ("975800761", "Borgestad ASA", "https://www.borgestad.com"),
    ("981211524", "NRC Group ASA", "https://www.nrcgroup.com"),
    ("958935096", "Multiconsult ASA", "https://www.multiconsult.no"),
]

# Measure 2024 recall only. Adding more years multiplies runtime without
# meaningfully changing the provider-comparison decision — the signal
# we care about is "did this provider find anything for this company,"
# not "which year's filing is more findable."
TARGET_YEARS = [2024]

# Where JSON summaries land. Kept per-run so consecutive invocations
# don't overwrite each other — the decision doc in Task 2 of the B4
# plan reads these files.
RESULTS_DIR = pathlib.Path("tests/manual/.recall-results")


def _require_key(env_var: str) -> str:
    """Fail-fast guard so a missing key produces a clear skip instead of
    the provider call tripping over None deep in the stack."""
    value = os.environ.get(env_var)
    if not value or value.lower() in {"your_key_here", "placeholder", "todo"}:
        pytest.skip(f"{env_var} is not set — skipping this provider")
    return value


def _measure_provider(
    fn: Callable[[str, str, str], List[dict]],
    provider_name: str,
) -> None:
    """Run `fn` against every company in RECALL_CORPUS, record per-company
    whether ≥1 PDF URL was returned, persist results to JSON, and print
    a one-line hit summary. The JSON file is what the decision doc in
    Task 2 reads to compute marginal recall."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    per_company: dict = {}
    for orgnr, navn, site in RECALL_CORPUS:
        call_started = time.time()
        try:
            out = fn(orgnr, navn, site)
            urls = [r.get("pdf_url") for r in (out or []) if r.get("pdf_url")]
            per_company[orgnr] = {
                "navn": navn,
                "hjemmeside": site,
                "any_pdf": bool(urls),
                "pdf_count": len(urls),
                "urls": urls[:3],  # cap stored evidence; full list is rarely useful
                "elapsed_s": round(time.time() - call_started, 1),
            }
        except Exception as exc:
            per_company[orgnr] = {
                "navn": navn,
                "hjemmeside": site,
                "any_pdf": False,
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_s": round(time.time() - call_started, 1),
            }
    hits = sum(1 for r in per_company.values() if r.get("any_pdf"))
    summary = {
        "provider": provider_name,
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "corpus_size": len(RECALL_CORPUS),
        "target_years": TARGET_YEARS,
        "hit_count": hits,
        "per_company": per_company,
    }
    path = RESULTS_DIR / f"{provider_name}-{started.strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n{provider_name}: {hits}/{len(RECALL_CORPUS)} hits → {path}")


def test_azure_recall() -> None:
    """Azure OpenAI agent reads its own env vars; guard just asserts
    they're present so we skip rather than report a false-zero."""
    _require_key("AZURE_OPENAI_API_KEY")
    _require_key("AZURE_OPENAI_ENDPOINT")
    from api.services.pdf_agents import _agent_discover_pdfs_azure_openai

    def _call(orgnr: str, navn: str, hjemmeside: str) -> List[dict]:
        return _agent_discover_pdfs_azure_openai(orgnr, navn, hjemmeside, TARGET_YEARS)

    _measure_provider(_call, "azure")


def test_claude_recall() -> None:
    """Anthropic Claude agent — needs ANTHROPIC_API_KEY. Uses Claude's
    native web_search + a custom fetch_url tool (Playwright-backed)."""
    api_key = _require_key("ANTHROPIC_API_KEY")
    from api.services.pdf_agents import _agent_discover_pdfs_claude

    def _call(orgnr: str, navn: str, hjemmeside: str) -> List[dict]:
        return _agent_discover_pdfs_claude(
            orgnr, navn, hjemmeside, TARGET_YEARS, api_key
        )

    _measure_provider(_call, "claude")


def test_gemini_recall() -> None:
    """Gemini AI-Studio agent — needs GEMINI_API_KEY. Uses Google
    Search grounding (phase 1) then fetch_url turns (phase 2)."""
    api_key = _require_key("GEMINI_API_KEY")
    from api.services.pdf_agents import _agent_discover_pdfs_gemini

    def _call(orgnr: str, navn: str, hjemmeside: str) -> List[dict]:
        return _agent_discover_pdfs_gemini(
            orgnr, navn, hjemmeside, TARGET_YEARS, api_key
        )

    _measure_provider(_call, "gemini")
