"""Agentic IR discovery — Claude, Gemini, and Azure OpenAI tool-use agent loops."""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from google import genai as google_genai
from google.genai import types as genai_types

from api.prompts import IR_DISCOVERY_PROMPT_TEMPLATE
from api.services.llm import _llm_answer_raw
from api.services.pdf_parse import _gemini_api_keys
from api.services.pdf_web import (
    _ddg_query,
    _ddg_search_results,
    _fetch_url_content,
    _parse_agent_pdf_list,
    _search_all_annual_pdfs,
)

logger = logging.getLogger(__name__)


# ── Shared tool dispatch ───────────────────────────────────────────────────────

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


# ── Claude agent loop ──────────────────────────────────────────────────────────

def _agent_discover_pdfs_claude(
    orgnr: str, navn: str, hjemmeside: Optional[str],
    target_years: List[int], api_key: str,
) -> List[Dict[str, Any]]:
    """Claude tool-use agent loop for annual report PDF discovery.

    Uses Claude's native web_search tool plus a custom fetch_url tool (Playwright-backed).
    """
    import anthropic as _anthropic
    from api.constants import CLAUDE_MODEL

    system_prompt = _agent_system_prompt(navn, orgnr, hjemmeside, target_years)
    client = _anthropic.Anthropic(api_key=api_key)

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
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return _parse_agent_pdf_list(last_text)


# ── Gemini agent loop ──────────────────────────────────────────────────────────

def _gemini_web_search(query: str) -> List[Dict[str, Any]]:
    """Use Gemini's native Google Search grounding to return [{title, url, snippet}] results."""
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
    _AGENT_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]

    def _is_quota_err(exc: Exception) -> bool:
        msg = str(exc)
        return any(x in msg for x in ["429", "RESOURCE_EXHAUSTED", "NOT_FOUND", "404"])

    for _model in _AGENT_MODELS:
        try:
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
            if not phase1_text or phase1_text in ("[]", ""):
                phase1_text = (
                    f"Homepage: {hjemmeside or 'unknown'}. "
                    f"Try fetching {hjemmeside}/investors/annual-reports or similar IR pages."
                )
            logger.info("[gemini] Phase 1 IR page response for %s: %s", orgnr, phase1_text[:300])

            chat = client.chats.create(
                model=_model,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=[_GEMINI_FETCH_URL_TOOL],
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


# ── Per-year Google Search (fast path) ────────────────────────────────────────

def _search_pdf_url_for_year(
    client: Any, navn: str, hjemmeside: Optional[str], year: int
) -> Optional[str]:
    """Ask Gemini + Google Search for a single year's annual report PDF URL."""
    homepage_hint = f" Their website is {hjemmeside}." if hjemmeside else ""
    prompt = (
        f"Find the direct PDF download URL for the {year} annual report of '{navn}'.{homepage_hint} "
        f"Return ONLY the complete PDF URL on a single line — it must end in .pdf or be a direct PDF download. "
        f"Do not return web pages, only the actual PDF file URL."
    )
    for model in ["gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                ),
            )
            text = (response.text or "").strip()
            pdf_urls = re.findall(r'https?://\S+\.pdf(?:\?\S*)?', text)
            if pdf_urls:
                return pdf_urls[0]
            if response.candidates:
                meta = getattr(response.candidates[0], "grounding_metadata", None)
                for chunk in (getattr(meta, "grounding_chunks", None) or []):
                    uri = getattr(getattr(chunk, "web", None), "uri", "") or ""
                    if ".pdf" in uri.lower():
                        return uri
        except Exception as exc:
            if any(x in str(exc) for x in ["429", "RESOURCE_EXHAUSTED", "quota", "limit: 0"]):
                logger.debug("[discovery] Gemini Google Search quota for %s year %d, trying DDG", navn, year)
                continue
            break
    ddg_urls = _ddg_query(f'{navn} annual report {year} filetype:pdf')
    if ddg_urls:
        logger.info("[discovery] DDG fallback found %d candidates for %s year %d", len(ddg_urls), navn, year)
        return ddg_urls[0]
    return None


def _discover_pdfs_per_year_search(
    orgnr: str, navn: str, hjemmeside: Optional[str],
    target_years: List[int], api_key: str,
) -> List[Dict[str, Any]]:
    """Fast path: one Google Search per year to find the direct PDF URL."""
    client = google_genai.Client(api_key=api_key)
    results: List[Dict[str, Any]] = []
    for year in target_years:
        url = _search_pdf_url_for_year(client, navn, hjemmeside, year)
        if url:
            logger.info("[discovery] Per-year search found %d: %s", year, url[:80])
            results.append({"year": year, "pdf_url": url, "label": f"{navn} Annual Report {year}"})
    return results


# ── Azure OpenAI agent loop ────────────────────────────────────────────────────

def _agent_discover_pdfs_azure_openai(
    orgnr: str, navn: str, hjemmeside: Optional[str],
    target_years: List[int],
) -> List[Dict[str, Any]]:
    """Azure OpenAI (gpt-4o) tool-use agent for annual report PDF discovery."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if not endpoint or not api_key:
        return []
    from openai import AzureOpenAI
    deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
    client = AzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version="2024-02-01")
    tools = [
        {"type": "function", "function": {
            "name": "web_search",
            "description": "Search the web. Returns [{title, url, snippet}].",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}}, "required": ["query"]},
        }},
        {"type": "function", "function": {
            "name": "fetch_url",
            "description": "Fetch a URL. Returns {text, pdf_links, page_links}.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"}}, "required": ["url"]},
        }},
    ]
    system_prompt = _agent_system_prompt(navn, orgnr, hjemmeside, target_years)
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Find annual report PDFs for {navn} (orgnr {orgnr})."},
    ]
    for _ in range(8):
        response = client.chat.completions.create(
            model=deployment, messages=messages, tools=tools, tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_unset=True))
        if response.choices[0].finish_reason == "stop":
            content = (msg.content or "").strip()
            cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", content).strip()
            m = re.search(r"\[.*\]", cleaned, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except Exception as exc:
                    logger.debug("Azure OpenAI agent JSON parse failed: %s", exc)
            return []
        if not msg.tool_calls:
            break
        tool_results = []
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = _run_tool(tc.function.name, args)
            tool_results.append({
                "role": "tool", "tool_call_id": tc.id, "content": json.dumps(result),
            })
        messages.extend(tool_results)
    return []


# ── Top-level orchestration ────────────────────────────────────────────────────

def _agent_discover_pdfs(
    orgnr: str, navn: str, hjemmeside: Optional[str], target_years: List[int],
) -> List[Dict[str, Any]]:
    """Run an LLM tool-use agent to find official annual report PDFs.

    Primary: Foundry tool-use agent (single provider, reliable).
    Fallback: Legacy Claude → Azure OpenAI → Gemini chain (kept for
    environments where Foundry is not configured).
    Returns [] if no agent succeeds — caller falls back to _discover_ir_pdfs.
    """
    logger.info("[discovery] Starting agent PDF discovery for %s (%s), years=%s", navn, orgnr, target_years)

    # Primary: Foundry tool-use agent (Phase 5 migration — single provider)
    try:
        from api.services.pdf_agents_v2 import agent_discover_pdfs as foundry_discover
        result = foundry_discover(orgnr, navn, hjemmeside or "", target_years)
        if result:
            logger.info("[discovery] Foundry agent returned %d results for %s", len(result), orgnr)
            return result
        logger.info("[discovery] Foundry agent returned empty for %s, trying legacy chain", orgnr)
    except Exception as exc:
        logger.warning("[discovery] Foundry agent failed for %s: %s — trying legacy chain", orgnr, exc)

    # Legacy fallback: Claude → Azure OpenAI → Gemini (kept until Foundry is proven stable)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key != "your_key_here":
        try:
            result = _agent_discover_pdfs_claude(orgnr, navn, hjemmeside, target_years, anthropic_key)
            if result:
                return result
        except Exception as exc:
            logger.warning("[discovery] Claude agent failed for %s: %s", orgnr, exc)

    try:
        result = _agent_discover_pdfs_azure_openai(orgnr, navn, hjemmeside, target_years)
        if result:
            return result
    except Exception as exc:
        logger.warning("[discovery] Azure OpenAI agent failed for %s: %s", orgnr, exc)

    for gemini_key in _gemini_api_keys():
        try:
            result = _discover_pdfs_per_year_search(orgnr, navn, hjemmeside, target_years, gemini_key)
            if result:
                return result
            result = _agent_discover_pdfs_gemini(orgnr, navn, hjemmeside, target_years, gemini_key)
            if result:
                return result
        except Exception as exc:
            logger.warning("[discovery] Gemini failed for %s: %s", orgnr, exc)

    logger.warning("[discovery] All agents returned no results for %s", orgnr)
    return []


def _discover_ir_pdfs(
    orgnr: str, navn: str, hjemmeside: Optional[str], target_years: List[int]
) -> List[Dict[str, Any]]:
    """DDG fallback: search for all annual report PDFs in 2 queries, validate with LLM."""
    urls = _search_all_annual_pdfs(navn, hjemmeside)
    if not urls:
        return []

    candidates_text = "\n".join(urls)
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
