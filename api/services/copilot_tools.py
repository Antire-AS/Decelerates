"""Copilot tool definitions — each tool the broker chat agent can call.

Tools are defined in OpenAI function-calling format. Each tool has:
- A schema (for the LLM to understand what to call and with what args)
- A handler function (executes the tool and returns a string result)

All handlers receive db + firm_id + orgnr for authorization context.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

_log = logging.getLogger(__name__)

# ── Tool schemas (OpenAI function calling format) ─────────────────────────────

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Søk i kunnskapsbasen for et selskap (årsrapporter, notater, dokumenter)",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Søketekst"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_coverage_gap",
            "description": "Analyser dekningsgap — sammenlign aktive poliser mot anbefalte forsikringer",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_insurers",
            "description": "Anbefal de beste forsikringsselskapene for dette selskapet basert på appetitt og tilslagsrate",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_types": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Forsikringstyper å matche (valgfritt — utledes fra dekningsgap hvis tom)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_deal",
            "description": "Opprett en ny deal i pipeline for dette selskapet",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Tittel på dealen"},
                    "expected_premium_nok": {"type": "number", "description": "Forventet premie i NOK"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_activity",
            "description": "Logg en aktivitet (møte, telefonsamtale, e-post) for dette selskapet",
            "parameters": {
                "type": "object",
                "properties": {
                    "activity_type": {
                        "type": "string",
                        "enum": ["meeting", "call", "email", "note", "task"],
                        "description": "Type aktivitet",
                    },
                    "subject": {"type": "string", "description": "Emne"},
                    "body": {"type": "string", "description": "Beskrivelse / notat"},
                },
                "required": ["activity_type", "subject"],
            },
        },
    },
]


# ── Tool handlers ─────────────────────────────────────────────────────────────

def _handle_search_knowledge(
    args: dict, db: Session, firm_id: int, orgnr: str,
) -> str:
    from api.services.rag import retrieve_chunks
    chunks = retrieve_chunks(orgnr, args.get("query", ""), db, limit=5)
    if not chunks:
        return "Ingen relevante resultater funnet i kunnskapsbasen."
    return "\n\n".join(
        f"[{c.get('source', '?')}] {c.get('text', '')[:300]}"
        for c in chunks
    )


def _handle_coverage_gap(
    args: dict, db: Session, firm_id: int, orgnr: str,
) -> str:
    from api.services.coverage_gap import analyze_coverage_gap
    result = analyze_coverage_gap(orgnr, firm_id, db)
    gaps = [i for i in result["items"] if i["status"] == "gap"]
    if not gaps:
        return f"Ingen dekningsgap funnet. {result['covered_count']} av {result['total_count']} anbefalte forsikringer er dekket."
    lines = [f"Dekningsgap: {result['gap_count']} av {result['total_count']} mangler:"]
    for g in gaps:
        lines.append(f"  - {g['type']} ({g['priority']}): {g['reason']}")
    return "\n".join(lines)


def _handle_recommend_insurers(
    args: dict, db: Session, firm_id: int, orgnr: str,
) -> str:
    from api.services.insurer_matching import recommend_insurers
    result = recommend_insurers(orgnr, firm_id, args.get("product_types"), db)
    recs = result.get("recommendations", [])
    if not recs:
        return "Ingen forsikringsselskaper registrert for dette firmaet."
    lines = ["Anbefalte forsikringsselskaper:"]
    for r in recs:
        lines.append(f"  {r['insurer_name']} (score: {r['score']:.0%}) — {r['reasoning']}")
    return "\n".join(lines)


def _handle_create_deal(
    args: dict, db: Session, firm_id: int, orgnr: str,
) -> str:
    from api.services.deal_service import DealService
    from api.schemas import DealCreate
    svc = DealService(db)
    stages = svc.list_stages(firm_id)
    if not stages:
        return "Ingen pipeline-stages konfigurert. Kan ikke opprette deal."
    body = DealCreate(
        orgnr=orgnr,
        stage_id=stages[0].id,
        title=args.get("title", "Ny deal"),
        expected_premium_nok=args.get("expected_premium_nok"),
    )
    deal = svc.create(firm_id, body, "copilot@broker.no")
    return f"Deal opprettet: #{deal.id} '{deal.title}' i fasen '{stages[0].name}'"


def _handle_log_activity(
    args: dict, db: Session, firm_id: int, orgnr: str,
) -> str:
    from api.db import Activity, ActivityType
    try:
        atype = ActivityType[args.get("activity_type", "note")]
    except KeyError:
        atype = ActivityType.note
    activity = Activity(
        orgnr=orgnr, firm_id=firm_id, type=atype,
        subject=args.get("subject", ""), body=args.get("body", ""),
        completed=False, created_at=datetime.now(timezone.utc),
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return f"Aktivitet logget: #{activity.id} '{activity.subject}' ({atype.value})"


# ── Dispatch ──────────────────────────────────────────────────────────────────

_HANDLERS = {
    "search_knowledge":    _handle_search_knowledge,
    "run_coverage_gap":    _handle_coverage_gap,
    "recommend_insurers":  _handle_recommend_insurers,
    "create_deal":         _handle_create_deal,
    "log_activity":        _handle_log_activity,
}


def execute_tool(
    name: str, args_json: str, db: Session, firm_id: int, orgnr: str,
) -> str:
    """Execute a tool by name. Returns the result string for the LLM."""
    handler = _HANDLERS.get(name)
    if not handler:
        return f"Ukjent verktøy: {name}"
    try:
        args = json.loads(args_json) if args_json else {}
    except json.JSONDecodeError:
        args = {}
    try:
        return handler(args, db, firm_id, orgnr)
    except Exception as exc:
        _log.warning("Copilot tool %s failed: %s", name, exc)
        return f"Verktøyet {name} feilet: {exc}"
