"""Service for tender chat session persistence."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.models.tender import TenderChatSession, TenderChatMessage


class TenderChatSessionService:
    def __init__(self, db: Session):
        self.db = db

    def list_sessions(self, user_oid: str, limit: int = 20) -> list[TenderChatSession]:
        return (
            self.db.query(TenderChatSession)
            .filter(TenderChatSession.user_oid == user_oid)
            .order_by(TenderChatSession.updated_at.desc())
            .limit(limit)
            .all()
        )

    def create_session(self, user_oid: str, first_question: str) -> TenderChatSession:
        title = first_question[:80].strip()
        now = datetime.now(timezone.utc)
        session = TenderChatSession(
            user_oid=user_oid,
            title=title,
            created_at=now,
            updated_at=now,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: int, user_oid: str) -> TenderChatSession | None:
        return (
            self.db.query(TenderChatSession)
            .filter(
                TenderChatSession.id == session_id,
                TenderChatSession.user_oid == user_oid,
            )
            .first()
        )

    def get_messages(self, session_id: int, user_oid: str) -> list[TenderChatMessage]:
        session = self.get_session(session_id, user_oid)
        if not session:
            return []
        return session.messages

    def append_turn(self, session_id: int, question: str, answer: str) -> None:
        now = datetime.now(timezone.utc)
        self.db.add(TenderChatMessage(session_id=session_id, role="user",
                                      content=question, created_at=now))
        self.db.add(TenderChatMessage(session_id=session_id, role="assistant",
                                      content=answer, created_at=now))
        self.db.query(TenderChatSession).filter(
            TenderChatSession.id == session_id
        ).update({"updated_at": now})
        self.db.commit()

    def load_history_for_prompt(self, session_id: int, user_oid: str, limit_turns: int = 20) -> str:
        messages = self.get_messages(session_id, user_oid)
        if not messages:
            return ""
        pairs = []
        msgs = messages[-(limit_turns * 2):]
        for m in msgs:
            prefix = "Bruker" if m.role == "user" else "Assistent"
            pairs.append(f"{prefix}: {m.content}")
        return "Tidligere samtale:\n" + "\n".join(pairs)

    def delete_session(self, session_id: int, user_oid: str) -> bool:
        session = self.get_session(session_id, user_oid)
        if not session:
            return False
        self.db.delete(session)
        self.db.commit()
        return True
