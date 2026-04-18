"""Natural-language -> SQL query service.

Uses an LLM (via the LlmPort, currently backed by Antire Azure AI Foundry)
to convert a plain-English/Norwegian question into a read-only SELECT query
against the financial database, then executes it and returns structured
results.
"""

import logging
import re

from sqlalchemy.orm import Session
from sqlalchemy import text

from api.container import resolve
from api.ports.driven.llm_port import LlmPort

log = logging.getLogger(__name__)

# Schema exposed to the LLM — only financial-relevant tables/columns
_SCHEMA = """
Table: companies
  orgnr          TEXT  -- 9-digit org number (primary key)
  navn           TEXT  -- company name
  kommune        TEXT  -- municipality
  naeringskode1_beskrivelse TEXT  -- industry description (NACE)
  risk_score     INT   -- 1–15, higher = more risk
  equity_ratio   FLOAT -- e.g. 0.35 means 35%
  sum_driftsinntekter BIGINT  -- total operating revenue (NOK)
  sum_egenkapital     BIGINT  -- total equity (NOK)
  regnskapsår    INT   -- accounting year for the above figures

Table: company_history
  orgnr          TEXT
  year           INT
  revenue        BIGINT  -- operating revenue (NOK)
  equity         BIGINT  -- total equity (NOK)
  equity_ratio   FLOAT
  net_income     BIGINT
  total_assets   BIGINT

Useful joins: companies.orgnr = company_history.orgnr
"""

_SYSTEM = (
    "You are a PostgreSQL expert. Convert the user's question into a single "
    "read-only SELECT query using only the tables and columns listed in the schema. "
    "Rules:\n"
    "- Output ONLY the SQL, no explanation, no markdown fences.\n"
    "- Only SELECT statements. Never INSERT/UPDATE/DELETE/DROP/CREATE/TRUNCATE.\n"
    "- Use LIMIT 50 unless the question asks for all.\n"
    "- For revenue/equity in MNOK divide by 1000000 and round to 1 decimal.\n"
    "- Order results meaningfully (e.g. DESC for rankings).\n"
    f"\nSchema:\n{_SCHEMA}"
)

_SAFE_SQL = re.compile(
    r"^\s*SELECT\b",
    re.IGNORECASE | re.DOTALL,
)
_UNSAFE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|TRUNCATE|ALTER|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)


def _generate_sql(question: str) -> str | None:
    """Ask the LLM to convert question -> SQL. Returns the SQL string or None."""
    try:
        llm: LlmPort = resolve(LlmPort)  # type: ignore[assignment]
    except Exception as exc:
        log.warning("nl_query: LLM port not available — %s", exc)
        return None
    if not llm.is_configured():
        return None
    raw = llm.chat(
        user_prompt=question,
        system_prompt=_SYSTEM,
        max_completion_tokens=512,
    )
    return raw.strip() if raw else None


class NlQueryService:
    def __init__(self, db: Session):
        self.db = db

    def run_nl_query(self, question: str) -> dict:
        """Convert question to SQL, execute, return results + the generated SQL."""
        sql = _generate_sql(question)
        if not sql:
            return {
                "error": "Kunne ikke generere SQL (ingen AI-nøkkel konfigurert)",
                "sql": None,
                "rows": [],
            }

        # Safety: only allow SELECT
        if not _SAFE_SQL.match(sql) or _UNSAFE.search(sql):
            log.warning("nl_query: unsafe SQL blocked: %s", sql[:200])
            return {
                "error": "Generert SQL er ikke tillatt (kun SELECT).",
                "sql": sql,
                "rows": [],
            }

        try:
            result = self.db.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return {"sql": sql, "columns": columns, "rows": rows, "error": None}
        except Exception as exc:
            log.warning("nl_query: SQL execution failed — %s", exc)
            return {"error": f"SQL-feil: {exc}", "sql": sql, "rows": []}


# Backward compat
def run_nl_query(question: str, db: Session) -> dict:
    return NlQueryService(db).run_nl_query(question)
