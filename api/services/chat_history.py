"""Per-user chat history — stores and replays chat turns.

Brokers asked for conversational continuity: if I tell the chat my company
focus is hospitality yesterday, I shouldn't have to repeat it today. This
service persists each (user, company|knowledge) turn and lets the chat
endpoints prepend history to the LLM prompt.

Scoping:
- Knowledge chat  → orgnr = None (one thread per user, shared across sessions)
- Company chat    → orgnr = "<9-digit>" (one thread per user per company)

Retention: unlimited for now. The chat endpoints only load the last N turns
into the prompt (see LlmService call sites), so size is bounded in practice.
A future maintenance job can trim rows older than 90 days if the table grows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from api.models.broker import UserChatMessage


class ChatHistoryService:
    """Thin DB service for UserChatMessage.

    Router-injected via Depends(). No LLM or HTTP knowledge — callers
    translate domain errors into HTTP status codes if needed.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def append_turn(
        self,
        user_oid: str,
        orgnr: Optional[str],
        question: str,
        answer: str,
    ) -> None:
        """Persist a user Q and assistant A as two rows in order."""
        now = datetime.now(timezone.utc)
        self.db.add(
            UserChatMessage(
                user_oid=user_oid,
                orgnr=orgnr,
                role="user",
                content=question,
                created_at=now,
            )
        )
        self.db.add(
            UserChatMessage(
                user_oid=user_oid,
                orgnr=orgnr,
                role="assistant",
                content=answer,
                created_at=now,
            )
        )
        self.db.commit()

    def load_history(
        self,
        user_oid: str,
        orgnr: Optional[str],
        limit_turns: int = 20,
    ) -> List[UserChatMessage]:
        """Return the most recent `limit_turns` messages in chronological order.

        A "turn" here counts each message individually, so `limit_turns=20`
        returns up to 10 Q+A pairs. The result is ordered oldest → newest so
        it can be pasted directly into an LLM prompt.
        """
        q = self.db.query(UserChatMessage).filter(UserChatMessage.user_oid == user_oid)
        if orgnr is None:
            q = q.filter(UserChatMessage.orgnr.is_(None))
        else:
            q = q.filter(UserChatMessage.orgnr == orgnr)

        recent = q.order_by(UserChatMessage.id.desc()).limit(limit_turns).all()
        return list(reversed(recent))

    def clear_history(self, user_oid: str, orgnr: Optional[str]) -> int:
        """Delete all messages for a (user, orgnr) thread. Returns row count."""
        q = self.db.query(UserChatMessage).filter(UserChatMessage.user_oid == user_oid)
        if orgnr is None:
            q = q.filter(UserChatMessage.orgnr.is_(None))
        else:
            q = q.filter(UserChatMessage.orgnr == orgnr)
        count = q.delete(synchronize_session=False)
        self.db.commit()
        return count


def format_history_for_prompt(messages: List[UserChatMessage]) -> str:
    """Render a list of chat messages as a plain-text block for LLM context.

    Example output:
        Tidligere samtale:
        Bruker: Hva er ansvarsforsikring?
        Assistent: Ansvarsforsikring dekker...
        Bruker: Og yrkesskade?

    Returns an empty string if messages is empty (caller should skip the
    section entirely in that case).
    """
    if not messages:
        return ""
    lines = ["Tidligere samtale:"]
    for m in messages:
        speaker = "Bruker" if m.role == "user" else "Assistent"
        lines.append(f"{speaker}: {m.content}")
    return "\n".join(lines)
