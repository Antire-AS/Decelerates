"""Agentic IR discovery — Claude + Azure OpenAI tool-use agent loops.

Gemini AI-Studio agent paths were deleted on 2026-04-22 (see
docs/decisions/2026-04-22-pdf-agents-recall.md). Measured recall was
2/20 and the free-tier RPM quota made the path unreliable. Phase 2
of the 2026-04-22 redesign replaces the DDG web_search tool with a
Bing Web Search adapter for the remaining agents' tool-use loop.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from api.prompts import IR_DISCOVERY_PROMPT_TEMPLATE
from api.services.llm import _llm_answer_raw
from api.services.pdf_web import (
    _ddg_search_results,
    _fetch_url_content,
    _parse_agent_pdf_list,
    _search_all_annual_pdfs,
)

logger = logging.getLogger(__name__)


# ── Shared tool dispatch ───────────────────────────────────────────────────────


def _run_tool(name: str, args: Dict[str, Any]) -> Any:
    """Dispatch a tool call by name. Shared between Claude and Azure agent loops.

    The `web_search` tool currently uses the DDG fallback only — measurements
    on 2026-04-22 showed DDG's HTML endpoint returns HTTP 202 anti-bot pages,
    so this is effectively broken. Phase 2 of the redesign swaps this for
    a Bing Web Search adapter with real API access.
    """
    if name == "web_search":
        return _ddg_search_results(args.get("query", ""))
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
    orgnr: str,
    navn: str,
    hjemmeside: Optional[str],
    target_years: List[int],
    api_key: str,
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
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"}
                },
                "required": ["url"],
            },
        },
    ]

    messages: List[Dict[str, Any]] = [
        {
            "role": "user",
            "content": f"Find annual report PDFs for {navn} (orgnr {orgnr}).",
        }
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
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(output),
                    }
                )
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return _parse_agent_pdf_list(last_text)


# ── Azure OpenAI agent loop ────────────────────────────────────────────────────


def _agent_discover_pdfs_azure_openai(
    orgnr: str,
    navn: str,
    hjemmeside: Optional[str],
    target_years: List[int],
) -> List[Dict[str, Any]]:
    """Azure OpenAI (gpt-4o) tool-use agent for annual report PDF discovery."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if not endpoint or not api_key:
        return []
    from openai import AzureOpenAI

    deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
    client = AzureOpenAI(
        api_key=api_key, azure_endpoint=endpoint, api_version="2024-02-01"
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web. Returns [{title, url, snippet}].",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "Fetch a URL. Returns {text, pdf_links, page_links}.",
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
        },
    ]
    system_prompt = _agent_system_prompt(navn, orgnr, hjemmeside, target_years)
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Find annual report PDFs for {navn} (orgnr {orgnr}).",
        },
    ]
    for _ in range(8):
        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
            tools=tools,
            tool_choice="auto",
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
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                }
            )
        messages.extend(tool_results)
    return []


# ── Top-level orchestration ────────────────────────────────────────────────────


def _agent_discover_pdfs(
    orgnr: str,
    navn: str,
    hjemmeside: Optional[str],
    target_years: List[int],
) -> List[Dict[str, Any]]:
    """Run an LLM tool-use agent to find official annual report PDFs.

    Primary: Foundry tool-use agent (single provider, reliable).
    Fallback: Claude → Azure OpenAI (kept for environments where
    Foundry is not configured). Gemini was deleted 2026-04-22 after
    measured 2/20 recall + free-tier quota issues.
    Returns [] if no agent succeeds — caller falls back to _discover_ir_pdfs.
    """
    logger.info(
        "[discovery] Starting agent PDF discovery for %s (%s), years=%s",
        navn,
        orgnr,
        target_years,
    )

    # Primary: Foundry tool-use agent (Phase 5 migration — single provider)
    try:
        from api.services.pdf_agents_v2 import agent_discover_pdfs as foundry_discover

        result = foundry_discover(orgnr, navn, hjemmeside or "", target_years)
        if result:
            logger.info(
                "[discovery] Foundry agent returned %d results for %s",
                len(result),
                orgnr,
            )
            return result
        logger.info(
            "[discovery] Foundry agent returned empty for %s, trying legacy chain",
            orgnr,
        )
    except Exception as exc:
        logger.warning(
            "[discovery] Foundry agent failed for %s: %s — trying legacy chain",
            orgnr,
            exc,
        )

    # Legacy fallback: Claude → Azure OpenAI → Gemini (kept until Foundry is proven stable)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key != "your_key_here":
        try:
            result = _agent_discover_pdfs_claude(
                orgnr, navn, hjemmeside, target_years, anthropic_key
            )
            if result:
                return result
        except Exception as exc:
            logger.warning("[discovery] Claude agent failed for %s: %s", orgnr, exc)

    try:
        result = _agent_discover_pdfs_azure_openai(
            orgnr, navn, hjemmeside, target_years
        )
        if result:
            return result
    except Exception as exc:
        logger.warning("[discovery] Azure OpenAI agent failed for %s: %s", orgnr, exc)

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
