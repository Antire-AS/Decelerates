"""PDF extraction helpers — Gemini native PDF, pdfplumber fallback, IR discovery."""
import io
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Callable

logger = logging.getLogger(__name__)

import pdfplumber
import requests
from google import genai as google_genai
from google.genai import types as genai_types
from sqlalchemy.orm import Session

from constants import GEMINI_PDF_MODELS
from db import CompanyHistory, CompanyPdfSource, SessionLocal
from domain.exceptions import PdfExtractionError
from prompts import FINANCIALS_PROMPT, IR_DISCOVERY_PROMPT_TEMPLATE
from services.llm import _llm_answer_raw
from services.external_apis import fetch_regnskap_history


def _parse_json_financials(raw: str) -> Optional[Dict[str, Any]]:
    """Parse and validate the JSON financial dict returned by any LLM."""
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            return None
    eq = data.get("equity")
    assets = data.get("total_assets")
    data["equity_ratio"] = (eq / assets) if (eq and assets) else None
    return data


def _extract_pdf_text(pdf_url: str) -> str:
    """Download a PDF and extract all text using pdfplumber (up to 60 pages)."""
    resp = requests.get(
        pdf_url, timeout=60, headers={"User-Agent": "BrokerAccelerator/1.0"}
    )
    resp.raise_for_status()
    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages[:60])


def _parse_financials_from_text(
    text: str, orgnr: str, year: int
) -> Optional[Dict[str, Any]]:
    """Ask LLM to extract key financial figures from annual report text."""
    prompt = FINANCIALS_PROMPT.format(orgnr=orgnr, year=year) + f"\n\nAnnual report text (first portion):\n{text[:12000]}"
    raw = _llm_answer_raw(prompt)
    if not raw:
        return None
    return _parse_json_financials(raw)


# ── Gemini PDF extraction (decomposed) ───────────────────────────────────────

def _gemini_inline(
    client: Any, model_name: str, pdf_bytes: bytes, prompt: str
) -> Optional[str]:
    """Send PDF bytes inline to Gemini (≤18 MB)."""
    pdf_part = genai_types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    resp = client.models.generate_content(model=model_name, contents=[pdf_part, prompt])
    return resp.text


def _gemini_files_api(
    client: Any, model_name: str, pdf_bytes: bytes, orgnr: str, year: int
) -> Optional[str]:
    """Upload PDF via Files API (>18 MB) and generate content, then delete upload."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        uploaded = client.files.upload(
            file=tmp_path,
            config=genai_types.UploadFileConfig(
                mime_type="application/pdf",
                display_name=f"annual_{orgnr}_{year}.pdf",
            ),
        )
        try:
            prompt_text = FINANCIALS_PROMPT.format(orgnr=orgnr, year=year)
            resp = client.models.generate_content(
                model=model_name, contents=[uploaded, prompt_text]
            )
            return resp.text
        finally:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass
    finally:
        os.unlink(tmp_path)


def _gemini_api_keys() -> List[str]:
    """Return all configured Gemini API keys (primary + fallbacks), deduped."""
    keys = []
    for var in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"):
        k = os.getenv(var)
        if k and k != "your_key_here" and k not in keys:
            keys.append(k)
    return keys


def _try_gemini(pdf_bytes: bytes, orgnr: str, year: int) -> Optional[str]:
    """Try all Gemini API keys × all PDF models; return raw text or None on quota/failure."""
    prompt = FINANCIALS_PROMPT.format(orgnr=orgnr, year=year)
    use_files_api = len(pdf_bytes) > 18 * 1024 * 1024

    for api_key in _gemini_api_keys():
        client = google_genai.Client(api_key=api_key)
        for model_name in GEMINI_PDF_MODELS:
            try:
                if use_files_api:
                    raw = _gemini_files_api(client, model_name, pdf_bytes, orgnr, year)
                else:
                    raw = _gemini_inline(client, model_name, pdf_bytes, prompt)
                if raw:
                    return raw
            except Exception as exc:
                msg = str(exc)
                if "quota" in msg.lower() or "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    continue  # try next model or key
                break  # non-quota error on this key, skip remaining models
    return None


def _parse_financials_from_pdf(
    pdf_url: str, orgnr: str, year: int
) -> Optional[Dict[str, Any]]:
    """Extract key financials from an annual report PDF.

    Primary: Gemini native PDF understanding (table-aware, no page cap).
    Fallback: pdfplumber text extraction + text-based LLM.
    """
    try:
        resp = requests.get(pdf_url, timeout=60, headers={"User-Agent": "BrokerAccelerator/1.0"})
        resp.raise_for_status()
        pdf_bytes = resp.content
    except Exception:
        return None

    raw = _try_gemini(pdf_bytes, orgnr, year)
    if raw:
        result = _parse_json_financials(raw)
        if result:
            return result

    # Fallback: pdfplumber text → text LLM
    try:
        text = "\n".join(
            p.extract_text() or ""
            for p in pdfplumber.open(io.BytesIO(pdf_bytes)).pages[:60]
        )
        return _parse_financials_from_text(text, orgnr, year)
    except Exception:
        return None


def _upsert_history_row(existing: Any, parsed: Dict[str, Any], pdf_url: str) -> None:
    """Copy parsed financial fields onto an existing CompanyHistory ORM object."""
    existing.source = "pdf"
    existing.pdf_url = pdf_url
    existing.revenue = parsed.get("revenue")
    existing.net_result = parsed.get("net_result")
    existing.equity = parsed.get("equity")
    existing.total_assets = parsed.get("total_assets")
    existing.equity_ratio = parsed.get("equity_ratio")
    existing.short_term_debt = parsed.get("short_term_debt")
    existing.long_term_debt = parsed.get("long_term_debt")
    existing.antall_ansatte = parsed.get("antall_ansatte")
    existing.currency = parsed.get("currency", "NOK")
    existing.raw = parsed


def fetch_history_from_pdf(
    orgnr: str, pdf_url: str, year: int, label: str, db: Session
) -> Dict[str, Any]:
    """Parse financials from PDF and upsert into company_history."""
    parsed = _parse_financials_from_pdf(pdf_url, orgnr, year)
    if not parsed:
        raise PdfExtractionError(f"Could not parse financials from PDF: {pdf_url}")

    existing = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr, CompanyHistory.year == year)
        .first()
    )
    if not existing:
        existing = CompanyHistory(orgnr=orgnr, year=year)
        db.add(existing)

    _upsert_history_row(existing, parsed, pdf_url)
    db.commit()

    return {
        "year": year,
        "source": "pdf",
        "pdf_url": pdf_url,
        "label": label,
        "currency": existing.currency,
        "revenue": existing.revenue,
        "net_result": existing.net_result,
        "equity": existing.equity,
        "total_assets": existing.total_assets,
        "equity_ratio": existing.equity_ratio,
        "short_term_debt": existing.short_term_debt,
        "long_term_debt": existing.long_term_debt,
        "antall_ansatte": existing.antall_ansatte,
    }


def _get_full_history(orgnr: str, db: Session) -> List[Dict[str, Any]]:
    """Return merged history: DB rows (PDF/manual) + BRREG, deduped by year, sorted desc."""
    db_rows = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .order_by(CompanyHistory.year.desc())
        .all()
    )
    by_year: Dict[int, Dict[str, Any]] = {}
    for row in db_rows:
        base = dict(row.raw) if row.raw else {}
        base.update({
            "year": row.year,
            "source": row.source,
            "currency": row.currency or "NOK",
            "revenue": row.revenue,
            "net_result": row.net_result,
            "equity": row.equity,
            "total_assets": row.total_assets,
            "equity_ratio": row.equity_ratio,
            "short_term_debt": row.short_term_debt,
            "long_term_debt": row.long_term_debt,
            "antall_ansatte": row.antall_ansatte,
        })
        by_year[row.year] = base

    try:
        brreg_rows = fetch_regnskap_history(orgnr)
    except Exception:
        brreg_rows = []

    for row in brreg_rows:
        year = row.get("year")
        if year and year not in by_year:
            by_year[year] = {**row, "source": "brreg", "currency": "NOK"}

    return sorted(by_year.values(), key=lambda r: r["year"], reverse=True)


def _search_for_pdfs(navn: str, hjemmeside: Optional[str], year: int) -> List[str]:
    """Search DuckDuckGo HTML for annual report PDF URLs for a given company + year."""

    def _extract_pdfs_from_html(html: str) -> List[str]:
        found = []
        found += re.findall(r"https?://[^\s\"'<>]+\.pdf(?:[?#][^\s\"'<>]*)?", html)
        encoded = re.findall(r"uddg=(https?%3A%2F%2F[^&\"]+)", html)
        for u in encoded:
            decoded = requests.utils.unquote(u)
            if ".pdf" in decoded.lower():
                found.append(decoded)
        result_url_texts = re.findall(
            r'class=["\']result__url["\'][^>]*>\s*([^\s<]+)', html
        )
        for u in result_url_texts:
            u = u.strip()
            if ".pdf" in u.lower():
                full = u if u.startswith("http") else f"https://{u}"
                found.append(full)
        return list(dict.fromkeys(found))

    queries = []
    if hjemmeside:
        domain = re.sub(r"^https?://", "", hjemmeside).rstrip("/").split("/")[0]
        queries.append(f'site:{domain} "annual report" {year} filetype:pdf')
    queries.append(f'{navn} annual report {year} filetype:pdf')

    all_urls: List[str] = []
    for query in queries:
        if len(all_urls) >= 8:
            break
        try:
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; BrokerAccelerator/1.0)"},
                timeout=15,
            )
            all_urls += _extract_pdfs_from_html(resp.text)
            all_urls = list(dict.fromkeys(all_urls))
        except Exception:
            continue

    return all_urls[:8]


# ── Agentic IR discovery (Claude tool-use loop) ───────────────────────────────

def _ddg_search_results(query: str) -> List[Dict[str, Any]]:
    """General DuckDuckGo search — returns [{title, url, snippet}], not PDF-filtered."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (compatible; BrokerAccelerator/1.0)"},
            timeout=15,
        )
        html = resp.text
    except Exception:
        return []

    results = []
    # titles + raw hrefs
    for m in re.finditer(
        r'class=["\']result__a["\'][^>]*href=["\']([^"\']+)["\'][^>]*>([^<]+)<', html
    ):
        raw_href, title = m.group(1), m.group(2).strip()
        # decode uddg= redirect
        uddg = re.search(r"uddg=(https?%3A%2F%2F[^&\"]+)", raw_href)
        url = requests.utils.unquote(uddg.group(1)) if uddg else raw_href
        results.append({"title": title, "url": url, "snippet": ""})

    # snippets — zip into existing results by position
    snippets = re.findall(
        r'class=["\']result__snippet["\'][^>]*>([^<]+)<', html
    )
    for i, snip in enumerate(snippets):
        if i < len(results):
            results[i]["snippet"] = snip.strip()

    return results[:8]


def _fetch_url_content(url: str) -> Dict[str, Any]:
    """Fetch a URL and return {text, pdf_links, page_links} for the agent.

    Uses Playwright (headless Chromium) to execute JavaScript so IR pages that
    load PDF links dynamically are handled correctly. Falls back to a plain
    requests.get if Playwright is not installed or fails.
    """
    html = _fetch_html(url)
    if not html:
        return {"text": "Error: could not fetch URL", "pdf_links": [], "page_links": []}
    return _parse_html_for_agent(html, url)


def _fetch_html(url: str) -> Optional[str]:
    """Fetch raw HTML — Playwright first, requests fallback."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = ctx.new_page()
            try:
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=10000)
            except PWTimeout:
                pass  # use whatever content loaded so far
            html = page.content()
            browser.close()
            return html
    except ImportError:
        pass  # Playwright not installed
    except Exception:
        pass  # Playwright failed (e.g. Chromium not downloaded yet)

    # Plain requests fallback
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BrokerAccelerator/1.0)"},
            timeout=12,
        )
        return resp.text
    except Exception:
        return None


def _parse_html_for_agent(html: str, base_url: str) -> Dict[str, Any]:
    """Extract text, PDF links, and IR-relevant page links from raw HTML."""
    from urllib.parse import urlparse

    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()[:3000]

    pdf_links = list(dict.fromkeys(
        re.findall(r'https?://[^\s"\'<>]+\.pdf(?:[?#][^\s"\'<>]*)?', html, re.I)
    ))[:20]

    ir_keywords = re.compile(
        r"annual|report|arsrapport|investor|ir\b|financial|results|downloads", re.I
    )
    base = urlparse(base_url)
    page_links = []
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html):
        href = m.group(1)
        if not ir_keywords.search(href):
            continue
        if href.startswith("http"):
            page_links.append(href)
        elif href.startswith("/"):
            page_links.append(f"{base.scheme}://{base.netloc}{href}")
    page_links = list(dict.fromkeys(page_links))[:15]

    return {"text": text, "pdf_links": pdf_links, "page_links": page_links}


def _parse_agent_pdf_list(raw: str) -> List[Dict[str, Any]]:
    """Extract and validate a JSON array of {year, pdf_url, label} from agent output."""
    if not raw:
        return []
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    for pattern in (cleaned, re.search(r"\[.*\]", cleaned, re.DOTALL)):
        text = pattern if isinstance(pattern, str) else (pattern.group() if pattern else None)
        if not text:
            continue
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return [
                    r for r in result
                    if isinstance(r.get("year"), int)
                    and isinstance(r.get("pdf_url"), str)
                    and r["pdf_url"].startswith("http")
                ]
        except (json.JSONDecodeError, ValueError):
            continue
    return []



_GEMINI_FETCH_URL_TOOL = genai_types.Tool(function_declarations=[
    genai_types.FunctionDeclaration(
        name="fetch_url",
        description=(
            "Fetch the content of a URL. Returns {text, pdf_links, page_links}. "
            "pdf_links are direct .pdf URLs found on the page. "
            "Use this to navigate to investor relations pages and find PDF download links."
        ),
        parameters=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={"url": genai_types.Schema(
                type=genai_types.Type.STRING, description="The URL to fetch"
            )},
            required=["url"],
        ),
    ),
])


def _gemini_web_search(query: str) -> List[Dict[str, Any]]:
    """Use Gemini's native Google Search grounding to return [{title, url, snippet}] results.

    Results are extracted from grounding_metadata.grounding_chunks, not response.text.
    Rotates through all configured Gemini API keys on quota errors.
    """
    keys = _gemini_api_keys()
    if not keys:
        return []
    _search_models = ["gemini-2.5-flash", "gemini-2.0-flash"]
    for api_key in keys:
        client = google_genai.Client(api_key=api_key)
        for model_name in _search_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=query,
                    config=genai_types.GenerateContentConfig(
                        tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                    ),
                )
                results: List[Dict[str, Any]] = []
                if response.candidates:
                    meta = getattr(response.candidates[0], "grounding_metadata", None)
                    chunks = getattr(meta, "grounding_chunks", None) or []
                    for chunk in chunks:
                        web = getattr(chunk, "web", None)
                        if web:
                            url = getattr(web, "uri", "") or ""
                            title = getattr(web, "title", "") or ""
                            if url:
                                results.append({"title": title, "url": url, "snippet": ""})
                if results:
                    return results[:8]
            except Exception as exc:
                msg = str(exc)
                if "quota" in msg.lower() or "429" in msg or "RESOURCE_EXHAUSTED" in msg or "limit: 0" in msg:
                    logger.warning("[web_search] Quota on %s key ...%s for %r", model_name, api_key[-4:], query)
                    continue
                logger.warning("[web_search] Gemini search failed (%s) for %r: %s", model_name, query, exc)
                break
    return []


def _run_tool(name: str, args: Dict[str, Any]) -> Any:
    """Dispatch a tool call by name. Shared between Claude and Gemini agent loops."""
    if name == "web_search":
        results = _gemini_web_search(args.get("query", ""))
        if not results:
            results = _ddg_search_results(args.get("query", ""))  # fallback
        return results
    if name == "fetch_url":
        return _fetch_url_content(args.get("url", ""))
    return {"error": f"unknown tool: {name}"}


def _agent_discover_pdfs_claude(
    orgnr: str, navn: str, hjemmeside: Optional[str],
    target_years: List[int], api_key: str,
) -> List[Dict[str, Any]]:
    """Claude tool-use agent loop for annual report PDF discovery.

    Uses Claude's native web_search tool (Anthropic's built-in, no external dependency)
    plus a custom fetch_url tool for navigating IR pages with Playwright.
    """
    import anthropic as _anthropic
    from constants import CLAUDE_MODEL

    system_prompt = _agent_system_prompt(navn, orgnr, hjemmeside, target_years)
    client = _anthropic.Anthropic(api_key=api_key)

    # Claude's built-in web search + our custom fetch_url (Playwright-backed)
    tools = [
        {"type": "web_search_20250305"},
        {
            "name": "fetch_url",
            "description": (
                "Fetch the content of a URL. Returns {text, pdf_links, page_links}. "
                "pdf_links are direct .pdf URLs found on the page. "
                "Use this to navigate to investor relations pages and find PDF download links."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "The URL to fetch"}},
                "required": ["url"],
            },
        },
    ]

    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": f"Find annual report PDFs for {navn} (orgnr {orgnr})."}
    ]

    last_text = ""
    for _ in range(8):
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )
        for block in response.content:
            if hasattr(block, "text"):
                last_text = block.text
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        # Handle tool calls — web_search results come back automatically from Anthropic;
        # fetch_url we execute ourselves with Playwright
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "fetch_url":
                output = _fetch_url_content(block.input.get("url", ""))
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(output),
                })
            # web_search_20250305 results are returned by Anthropic automatically — no action needed
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return _parse_agent_pdf_list(last_text)


def _run_gemini_phase2(chat: Any, navn: str, phase1_text: str) -> str:
    """Run the fetch_url tool loop (max 4 turns). Returns last text response."""
    last_text = ""
    response = chat.send_message(
        f"The investor relations page for {navn} is here:\n\n{phase1_text}\n\n"
        "Use fetch_url to navigate to the IR/annual-reports page. "
        "The pdf_links field in the response contains direct PDF URLs — use those. "
        "Do NOT guess or construct PDF URLs. Output the final JSON array."
    )
    for _ in range(4):
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                last_text = part.text
        fn_calls = [
            p.function_call
            for p in response.candidates[0].content.parts
            if p.function_call
        ]
        if not fn_calls:
            break
        fn_responses = [
            genai_types.Part(
                function_response=genai_types.FunctionResponse(
                    name=fc.name,
                    response={"result": json.dumps(_run_tool(fc.name, dict(fc.args)))},
                )
            )
            for fc in fn_calls
        ]
        response = chat.send_message(fn_responses)
    return last_text


def _agent_discover_pdfs_gemini(
    orgnr: str, navn: str, hjemmeside: Optional[str],
    target_years: List[int], api_key: str,
) -> List[Dict[str, Any]]:
    """Gemini agent for annual report PDF discovery using native Google Search + fetch_url.

    Phase 1: Google Search grounding to find direct PDF URLs or IR page URLs.
    Phase 2: If IR pages found but no PDFs, fetch them with fetch_url tool.
    """
    system_prompt = _agent_system_prompt(navn, orgnr, hjemmeside, target_years)
    client = google_genai.Client(api_key=api_key)

    # gemini-2.5-flash has Google Search grounding on free tier; 2.0-flash limit: 0 for grounding.
    _AGENT_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]

    fetch_url_tool = _GEMINI_FETCH_URL_TOOL

    def _is_quota_err(exc: Exception) -> bool:
        msg = str(exc)
        return any(x in msg for x in ["429", "RESOURCE_EXHAUSTED", "NOT_FOUND", "404"])

    for _model in _AGENT_MODELS:
        try:
            # Phase 1: native Google Search — ask only for the IR page URL, not PDF URLs
            search_response = client.models.generate_content(
                model=_model,
                contents=(
                    f"Find the official investor relations or annual reports page URL for {navn} "
                    f"(orgnr {orgnr}, homepage: {hjemmeside or 'unknown'}). "
                    "Return only the IR/annual-reports page URL as plain text, not PDF links."
                ),
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                ),
            )
            phase1_text = (search_response.text or "").strip()
            # If Phase 1 returned nothing useful, fall back to the company homepage
            if not phase1_text or phase1_text in ("[]", ""):
                phase1_text = (
                    f"Homepage: {hjemmeside or 'unknown'}. "
                    f"Try fetching {hjemmeside}/investors/annual-reports or similar IR pages."
                )
            logger.info("[gemini] Phase 1 IR page response for %s: %s", orgnr, phase1_text[:300])

            # Phase 2: fetch the IR page to get real pdf_links (max 4 turns to conserve quota)
            chat = client.chats.create(
                model=_model,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=[fetch_url_tool],
                ),
            )
            last_text = _run_gemini_phase2(chat, navn, phase1_text)
            return _parse_agent_pdf_list(last_text)

        except Exception as _exc:
            if _is_quota_err(_exc):
                logger.warning("[gemini] Quota error on %s for %s, trying next model", _model, orgnr)
                continue
            logger.error("[gemini] Unexpected error for %s: %s", orgnr, _exc)
            raise

    return []  # all models quota-exhausted


def _agent_system_prompt(
    navn: str, orgnr: str, hjemmeside: Optional[str], target_years: List[int]
) -> str:
    return (
        f"You are a research agent finding official annual report PDFs for a Norwegian company.\n"
        f"Company: {navn} (orgnr: {orgnr}, homepage: {hjemmeside or 'unknown'})\n"
        f"Target years: {target_years}\n\n"
        "Strategy:\n"
        "1. Use web_search to find the company's investor relations (IR) page\n"
        "2. Use fetch_url on the IR page to find PDF download links — look in pdf_links returned\n"
        "3. Match each PDF to the correct year — prioritise 'Annual Report' over sustainability/interim\n"
        "4. Only return URLs from the pdf_links field of fetch_url results — never guess or construct PDF URLs.\n\n"
        "When finished, respond with ONLY a JSON array — no markdown, no explanation:\n"
        '[{"year": 2023, "pdf_url": "https://...", "label": "Navn Annual Report 2023"}]\n'
        "Return [] if no official annual reports are found."
    )


def _agent_discover_pdfs(
    orgnr: str,
    navn: str,
    hjemmeside: Optional[str],
    target_years: List[int],
) -> List[Dict[str, Any]]:
    """Run an LLM tool-use agent to find official annual report PDFs.

    Tries Claude first (ANTHROPIC_API_KEY), then Gemini (GEMINI_API_KEY).
    Returns [] if neither key is set — caller falls back to _discover_ir_pdfs.
    """
    logger.info("[discovery] Starting agent PDF discovery for %s (%s), years=%s", navn, orgnr, target_years)

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key != "your_key_here":
        try:
            logger.info("[discovery] Trying Claude agent for %s", orgnr)
            result = _agent_discover_pdfs_claude(orgnr, navn, hjemmeside, target_years, anthropic_key)
            logger.info("[discovery] Claude agent returned %d results for %s", len(result), orgnr)
            return result
        except Exception as exc:
            logger.warning("[discovery] Claude agent failed for %s: %s", orgnr, exc)

    for gemini_key in _gemini_api_keys():
        try:
            logger.info("[discovery] Trying Gemini agent for %s (key ...%s)", orgnr, gemini_key[-4:])
            result = _agent_discover_pdfs_gemini(orgnr, navn, hjemmeside, target_years, gemini_key)
            logger.info("[discovery] Gemini agent returned %d results for %s", len(result), orgnr)
            if result:
                return result
        except Exception as exc:
            logger.warning("[discovery] Gemini agent failed for %s (key ...%s): %s", orgnr, gemini_key[-4:], exc)

    logger.warning("[discovery] All LLM agents returned no results for %s", orgnr)
    return []


def _discover_ir_pdfs(
    orgnr: str, navn: str, hjemmeside: Optional[str], target_years: List[int]
) -> List[Dict[str, Any]]:
    """Phase 2: search for annual report PDFs for each target year, validate with LLM."""
    candidates: List[tuple] = []
    for year in target_years:
        urls = _search_for_pdfs(navn, hjemmeside, year)
        for url in urls:
            candidates.append((year, url))

    if not candidates:
        return []

    candidates_text = "\n".join(f"Year {yr}: {url}" for yr, url in candidates)
    prompt = IR_DISCOVERY_PROMPT_TEMPLATE.format(
        navn=navn, orgnr=orgnr, candidates_text=candidates_text
    )
    raw = _llm_answer_raw(prompt)
    if not raw:
        return []

    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return [r for r in result if r.get("pdf_url") and r.get("year")]
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, list):
                    return [r for r in result if r.get("pdf_url") and r.get("year")]
            except (json.JSONDecodeError, ValueError):
                pass
    return []


# ── Background task helpers (decomposed) ─────────────────────────────────────

def _validate_pdf_urls(discovered: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter discovered PDF items to those reachable via HTTP HEAD (status < 400)."""
    valid = []
    for item in discovered:
        url = item.get("pdf_url", "")
        try:
            r = requests.head(url, timeout=10, allow_redirects=True,
                              headers={"User-Agent": "BrokerAccelerator/1.0"})
            if r.status_code < 400:
                valid.append(item)
                logger.info("[discovery] URL OK (%s): %s", r.status_code, url)
            else:
                logger.warning("[discovery] URL %s returned %s — skipping", url, r.status_code)
        except Exception as exc:
            logger.warning("[discovery] URL check failed for %s: %s — skipping", url, exc)
    return valid


def _run_phase2_discovery(orgnr: str, org: Dict[str, Any], db: Session) -> List[Any]:
    """Discover and cache IR PDFs for *orgnr* via DuckDuckGo + LLM validation."""
    navn = org.get("navn", "")
    hjemmeside = org.get("hjemmeside")
    current_year = datetime.now().year
    target_years = [current_year - i for i in range(1, 6)]

    logger.info("[discovery] Phase 2 starting for %s (%s), homepage=%s", navn, orgnr, hjemmeside)
    discovered = _agent_discover_pdfs(orgnr, navn, hjemmeside, target_years)
    if not discovered:
        logger.info("[discovery] Agent found nothing — falling back to DuckDuckGo for %s", orgnr)
        discovered = _discover_ir_pdfs(orgnr, navn, hjemmeside, target_years)

    # Validate each discovered URL is actually a reachable PDF (HEAD request)
    discovered = _validate_pdf_urls(discovered)
    logger.info("[discovery] Phase 2 validated %d PDF sources for %s", len(discovered), orgnr)
    for item in discovered:
        existing = (
            db.query(CompanyPdfSource)
            .filter(
                CompanyPdfSource.orgnr == orgnr,
                CompanyPdfSource.year == item["year"],
            )
            .first()
        )
        if not existing:
            db.add(CompanyPdfSource(
                orgnr=orgnr,
                year=item["year"],
                pdf_url=item["pdf_url"],
                label=item.get("label", ""),
                added_at=datetime.now(timezone.utc).isoformat(),
            ))
    if discovered:
        db.commit()

    return (
        db.query(CompanyPdfSource)
        .filter(CompanyPdfSource.orgnr == orgnr)
        .all()
    )


def _extract_pending_sources(orgnr: str, sources: List[Any], db: Session) -> None:
    """Extract financials for any PDF sources not yet in company_history.

    Runs up to 3 extractions in parallel — each in its own DB session so
    SQLAlchemy sessions are never shared across threads.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    pending = [
        src for src in sources
        if not db.query(CompanyHistory).filter(
            CompanyHistory.orgnr == orgnr,
            CompanyHistory.year == src.year,
        ).first()
    ]

    if not pending:
        return

    def _extract_one(src: Any) -> None:
        thread_db = SessionLocal()
        try:
            logger.info("[extract] Extracting financials from %s (year=%s)", src.pdf_url, src.year)
            fetch_history_from_pdf(orgnr, src.pdf_url, src.year, src.label or "", thread_db)
            logger.info("[extract] Done: %s year=%s", orgnr, src.year)
        except Exception as exc:
            logger.error("[extract] Failed for %s year=%s: %s", orgnr, src.year, exc)
        finally:
            thread_db.close()

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_extract_one, src): src for src in pending}
        for f in as_completed(futures):
            f.result()  # errors already caught inside _extract_one


def _auto_extract_pdf_sources(
    orgnr: str,
    org: Optional[Dict[str, Any]] = None,
    db_factory: Callable[[], Session] = SessionLocal,
) -> None:
    """Background task: Phase 1 seeds + Phase 2 IR discovery fallback.

    Accepts *db_factory* so tests can inject a mock session factory.
    """
    logger.info("[bg] _auto_extract_pdf_sources started for %s", orgnr)
    db = db_factory()
    try:
        sources = (
            db.query(CompanyPdfSource)
            .filter(CompanyPdfSource.orgnr == orgnr)
            .all()
        )

        current_year = datetime.now().year
        target_years = set(range(current_year - 5, current_year))
        covered_years = {s.year for s in sources}
        missing = target_years - covered_years
        needs_discovery = len(missing) >= 3
        logger.info("[bg] %s: covered=%s, missing=%s, needs_discovery=%s", orgnr, sorted(covered_years), sorted(missing), needs_discovery)

        if needs_discovery and org:
            sources = _run_phase2_discovery(orgnr, org, db)
        elif needs_discovery and not org:
            logger.warning("[bg] %s needs discovery but org dict not provided — skipping", orgnr)

        _extract_pending_sources(orgnr, sources, db)
        logger.info("[bg] _auto_extract_pdf_sources done for %s", orgnr)
    except Exception as exc:
        logger.error("[bg] _auto_extract_pdf_sources error for %s: %s", orgnr, exc, exc_info=True)
    finally:
        db.close()
