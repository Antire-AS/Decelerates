"""Broker copilot agent — multi-turn tool-use chat loop.

Wraps the Foundry LLM (gpt-5.4-mini) with function-calling tools so the
chat can take actions: create deals, log activities, run coverage gap
analysis, recommend insurers, and search the knowledge base.

The loop runs up to MAX_TOOL_ROUNDS turns. On each turn:
1. Send messages + tool definitions to the LLM
2. If the response contains tool_calls -> execute them, append results
3. If the response is a plain text -> return it as the final answer

Safety: the system prompt tells the LLM to confirm before sending emails.
All tool executions are logged. Max 5 rounds prevents runaway loops.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from api.services.copilot_tools import TOOL_SCHEMAS, execute_tool

_log = logging.getLogger(__name__)
MAX_TOOL_ROUNDS = 5

COPILOT_SYSTEM_PROMPT = """Du er en norsk forsikringsmegler-assistent med tilgang til verktøy.

Du kan:
- Søke i kunnskapsbasen (årsrapporter, notater, dokumenter)
- Analysere dekningsgap (sammenligne aktive poliser mot anbefalinger)
- Anbefale forsikringsselskaper basert på appetitt og historisk tilslagsrate
- Opprette deals i pipeline
- Logge aktiviteter (møter, telefonsamtaler, notater)

Svar alltid på norsk. Vær konkret og profesjonell.
Når du bruker et verktøy, forklar kort hva du gjør og hvorfor.
Bekreft alltid med brukeren før du sender e-poster."""


def _build_context_message(orgnr: str, db: Session) -> str:
    """Build a compact company context string for the system prompt."""
    from api.db import Company
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not company:
        return f"Selskap: {orgnr} (ikke funnet i databasen)"
    parts = [f"Selskap: {company.navn} ({orgnr})"]
    if company.risk_score is not None:
        parts.append(f"Risikoscore: {company.risk_score}/20")
    if company.sum_driftsinntekter:
        parts.append(f"Omsetning: {company.sum_driftsinntekter:,.0f} NOK")
    if company.naeringskode1_beskrivelse:
        parts.append(f"Bransje: {company.naeringskode1_beskrivelse}")
    return " · ".join(parts)


def _init_messages(question: str, orgnr: str, db: Session, history: Optional[list[dict]]) -> list[dict]:
    """Build the initial message list with system prompt + context + history."""
    context = _build_context_message(orgnr, db)
    system = f"{COPILOT_SYSTEM_PROMPT}\n\nKontekst: {context}"
    messages: list[dict] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})
    return messages


def _execute_tool_calls(choice, messages, tool_calls_made, db, firm_id, orgnr):
    """Process tool_calls from an LLM response, execute them, append results."""
    messages.append(choice.message.model_dump())
    for tc in choice.message.tool_calls:
        result = execute_tool(tc.function.name, tc.function.arguments, db, firm_id, orgnr)
        tool_calls_made.append({
            "tool": tc.function.name, "args": tc.function.arguments, "result": result[:500],
        })
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})


def _get_llm_client():
    """Resolve the Foundry LLM and return (client, model) or (None, None)."""
    from api.container import resolve
    from api.ports.driven.llm_port import LlmPort
    llm: LlmPort = resolve(LlmPort)  # type: ignore[assignment]
    if not llm.is_configured():
        return None, None
    return llm._get_chat_client(), llm._config.default_text_model  # type: ignore[attr-defined]


class CopilotAgentService:
    def __init__(self, db: Session):
        self.db = db

    def chat_with_tools(
        self, question: str, orgnr: str, firm_id: int,
        history: Optional[list[dict]] = None,
    ) -> dict:
        """Run the copilot agent loop. Returns {answer, tool_calls_made}."""
        client, model = _get_llm_client()
        if client is None:
            return {"answer": "LLM er ikke konfigurert.", "tool_calls_made": []}
        messages = _init_messages(question, orgnr, self.db, history)
        tool_calls_made: list[dict] = []
        for _ in range(MAX_TOOL_ROUNDS):
            resp = client.chat.completions.create(
                model=model, messages=messages, tools=TOOL_SCHEMAS, max_completion_tokens=1024,
            )
            choice = resp.choices[0]
            if not choice.message.tool_calls:
                return {"answer": choice.message.content or "", "tool_calls_made": tool_calls_made}
            _execute_tool_calls(choice, messages, tool_calls_made, self.db, firm_id, orgnr)
        # Exhausted rounds — ask for summary
        messages.append({"role": "user", "content": "Oppsummer hva du har gjort så langt."})
        resp = client.chat.completions.create(model=model, messages=messages, max_completion_tokens=512)
        return {"answer": resp.choices[0].message.content or "", "tool_calls_made": tool_calls_made}


# Backward compat
def chat_with_tools(
    question: str, orgnr: str, firm_id: int, db: Session,
    history: Optional[list[dict]] = None,
) -> dict:
    return CopilotAgentService(db).chat_with_tools(question, orgnr, firm_id, history)
