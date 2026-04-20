"""Per-company, per-user focus whiteboard service.

The whiteboard is a workspace where a broker collects facts from the
oversikt/økonomi/forsikring tabs into one place and asks the AI to
reason about them together — "Given these numbers for this company,
what should I be thinking about?"

Service responsibilities:
- CRUD on `company_whiteboards` rows (one per user+orgnr)
- Build the AI prompt from items + notes and call the LLM

Kept free of HTTP concerns — router translates to status codes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from api.models.broker import CompanyWhiteboard
from api.services.llm import _llm_answer_raw

_AI_SYSTEM_PROMPT = (
    "Du er en erfaren forsikringsmegler-rådgiver. Brukeren har samlet "
    "konkrete fakta om et selskap i en arbeidsflate. Gi et kortfattet "
    "sparringssvar: hva er de tre viktigste risikoene, hvilke "
    "forsikringsprodukter som bør prioriteres, og ett konkret neste steg "
    "megleren bør ta. Svar på norsk. Maks 150 ord."
)


class WhiteboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, orgnr: str, user_oid: str) -> Optional[CompanyWhiteboard]:
        return (
            self.db.query(CompanyWhiteboard)
            .filter(
                CompanyWhiteboard.orgnr == orgnr,
                CompanyWhiteboard.user_oid == user_oid,
            )
            .first()
        )

    def upsert(
        self,
        orgnr: str,
        user_oid: str,
        items: List[Dict[str, Any]],
        notes: Optional[str],
    ) -> CompanyWhiteboard:
        """Create or overwrite the whiteboard row for (orgnr, user_oid)."""
        existing = self.get(orgnr, user_oid)
        now = datetime.now(timezone.utc)
        if existing is None:
            wb = CompanyWhiteboard(
                orgnr=orgnr,
                user_oid=user_oid,
                items=items,
                notes=notes,
                updated_at=now,
            )
            self.db.add(wb)
        else:
            existing.items = items
            existing.notes = notes
            existing.updated_at = now
            wb = existing
        self.db.commit()
        self.db.refresh(wb)
        return wb

    def delete(self, orgnr: str, user_oid: str) -> bool:
        wb = self.get(orgnr, user_oid)
        if not wb:
            return False
        self.db.delete(wb)
        self.db.commit()
        return True

    def generate_ai_summary(
        self, orgnr: str, user_oid: str, company_name: str = ""
    ) -> Optional[str]:
        """Run the whiteboard items + notes through the LLM for a sparring summary.

        Returns None if the LLM is unavailable or the whiteboard is empty.
        Stores the summary back on the row so future loads show it without
        re-calling the LLM.
        """
        wb = self.get(orgnr, user_oid)
        if wb is None or (not wb.items and not wb.notes):
            return None
        prompt = _build_whiteboard_prompt(wb, company_name or orgnr)
        try:
            answer = _llm_answer_raw(prompt)
        except Exception:
            return None
        if not answer:
            return None
        wb.ai_summary = answer
        wb.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return answer


def _build_whiteboard_prompt(wb: CompanyWhiteboard, company_name: str) -> str:
    """Compose the LLM prompt: system role + collected facts + notes + ask."""
    fact_lines: List[str] = []
    for item in wb.items or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        value = str(item.get("value", "")).strip()
        tab = str(item.get("source_tab", "")).strip()
        if label and value:
            suffix = f" (fra {tab})" if tab else ""
            fact_lines.append(f"- {label}: {value}{suffix}")
    facts = "\n".join(fact_lines) if fact_lines else "(ingen fakta lagt til)"
    notes = (wb.notes or "").strip() or "(ingen notater)"
    return (
        f"[SYSTEM]: {_AI_SYSTEM_PROMPT}\n\n"
        f"Selskap: {company_name}\n\n"
        f"Fakta samlet av megleren:\n{facts}\n\n"
        f"Meglerens notater:\n{notes}\n\n"
        f"[OPPGAVE]: Gi sparringssvaret."
    )
