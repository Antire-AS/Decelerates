"""Agentic IR discovery — Foundry tool-use agent (replaces multi-LLM pdf_agents.py).

Single LLM provider (Azure Foundry gpt-5.4-mini) with two tools:
  1. web_search — DuckDuckGo text search (Foundry has no native web search)
  2. fetch_url — Playwright → requests fallback, returns page text + PDF links

Replaces the fragile 4-provider fallback chain (Claude → Azure OpenAI →
Gemini → DuckDuckGo) with a single reliable implementation.
"""

import json
import logging
from typing import Any, Dict, List

from api.services.pdf_web import (
    _ddg_search_results,
    _fetch_url_content,
)

logger = logging.getLogger(__name__)

MAX_AGENT_ROUNDS = 8

# ── Tool definitions (OpenAI function-calling format) ────────────────────────

IR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information. Returns a list of results with title, url, and snippet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch the content of a URL. Returns text content and lists of PDF links and page links found on the page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"}
                },
                "required": ["url"],
            },
        },
    },
]


def _execute_ir_tool(name: str, args_json: str) -> str:
    """Execute an IR discovery tool and return result as string."""
    try:
        args = json.loads(args_json) if args_json else {}
    except json.JSONDecodeError:
        args = {}
    if name == "web_search":
        results = _ddg_search_results(args.get("query", ""))
        return json.dumps(results[:5], ensure_ascii=False)
    if name == "fetch_url":
        content = _fetch_url_content(args.get("url", ""))
        return json.dumps(content, ensure_ascii=False)[:8000]
    return f"Unknown tool: {name}"


def _build_ir_system_prompt(
    orgnr: str, navn: str, hjemmeside: str, target_years: List[int]
) -> str:
    years_str = ", ".join(str(y) for y in target_years)
    return (
        f"You are a research assistant finding annual report PDFs for a Norwegian company.\n\n"
        f"Company: {navn} (org.nr {orgnr})\n"
        f"Website: {hjemmeside or 'unknown'}\n"
        f"Target years: {years_str}\n\n"
        f"Your task: Find direct PDF download URLs for annual reports (årsrapporter) for each target year.\n\n"
        f"Strategy:\n"
        f"1. Search for '{navn} årsrapport {target_years[0] if target_years else 2024} filetype:pdf'\n"
        f"2. If the company has a website, try fetching their investor relations / annual reports page\n"
        f"3. Look for direct .pdf links in the page content\n"
        f'4. Return results as JSON: {{"pdfs": [{{"year": 2024, "url": "https://...pdf", "label": "annual"}}]}}\n\n'
        f"Always return valid JSON with the pdfs array, even if empty."
    )


def _run_ir_agent_loop(
    client, model: str, messages: list[dict]
) -> List[Dict[str, Any]]:
    """Run the tool-use loop and return parsed PDF list."""
    for _ in range(MAX_AGENT_ROUNDS):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=IR_TOOLS,
            max_completion_tokens=2048,
        )
        choice = resp.choices[0]
        if not choice.message.tool_calls:
            return _parse_agent_response(choice.message.content or "")
        messages.append(choice.message.model_dump())
        for tc in choice.message.tool_calls:
            result = _execute_ir_tool(tc.function.name, tc.function.arguments)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return []


def agent_discover_pdfs(
    orgnr: str,
    navn: str,
    hjemmeside: str,
    target_years: List[int],
) -> List[Dict[str, Any]]:
    """Run Foundry tool-use agent for IR PDF discovery. Falls back to DDG."""
    from api.container import resolve
    from api.ports.driven.llm_port import LlmPort

    llm: LlmPort = resolve(LlmPort)  # type: ignore[assignment]
    if not llm.is_configured():
        return _fallback_ddg_search(navn, target_years)
    try:
        client = llm._get_chat_client()  # type: ignore[attr-defined]
        model = llm._config.default_text_model  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("IR discovery: LLM init failed: %s", exc)
        return _fallback_ddg_search(navn, target_years)
    system = _build_ir_system_prompt(orgnr, navn, hjemmeside, target_years)
    messages: list[dict] = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"Find annual report PDFs for {navn}. Return JSON.",
        },
    ]
    try:
        return _run_ir_agent_loop(client, model, messages) or _fallback_ddg_search(
            navn, target_years
        )
    except Exception as exc:
        logger.warning("IR discovery: agent loop failed: %s", exc)
        return _fallback_ddg_search(navn, target_years)


def _parse_agent_response(text: str) -> List[Dict[str, Any]]:
    """Parse the agent's final JSON response into a list of PDF dicts."""
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "pdfs" in data:
            return data["pdfs"]
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    # Try to extract JSON from markdown code block
    import re

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            return data.get("pdfs", [])
        except json.JSONDecodeError:
            pass
    return []


def _fallback_ddg_search(navn: str, target_years: List[int]) -> List[Dict[str, Any]]:
    """Last-resort: direct DuckDuckGo search for PDFs."""
    results = []
    for year in target_years:
        query = f"{navn} årsrapport {year} filetype:pdf"
        try:
            hits = _ddg_search_results(query)
            for h in hits[:3]:
                url = h.get("href") or h.get("url", "")
                if url.lower().endswith(".pdf"):
                    results.append({"year": year, "url": url, "label": "annual"})
                    break
        except Exception:
            # DuckDuckGo rate-limits per-IP; per-year isolation prevents one
            # failed lookup from killing the whole fallback scan. Log at
            # warning so persistent rate limits surface in telemetry.
            logger.warning("DDG fallback search failed for %r year=%d", navn, year)
            continue
    return results
