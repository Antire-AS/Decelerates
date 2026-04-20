"""HTTP endpoints for user chat history.

    GET  /chat/history[?orgnr=...]  — list messages for the current user
    DELETE /chat/history[?orgnr=...] — clear that thread

The chat endpoints themselves (knowledge + company) persist turns as a
side-effect of producing an answer; this router only exposes read + clear.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.services.chat_history import ChatHistoryService

router = APIRouter()


def _get_chat_history_service(db: Session = Depends(get_db)) -> ChatHistoryService:
    return ChatHistoryService(db)


@router.get("/chat/history")
def list_chat_history(
    orgnr: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user),
    svc: ChatHistoryService = Depends(_get_chat_history_service),
) -> dict:
    """Return recent messages for the current user in the given thread."""
    messages = svc.load_history(user.oid, orgnr, limit_turns=40)
    return {
        "orgnr": orgnr,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.delete("/chat/history")
def clear_chat_history(
    orgnr: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user),
    svc: ChatHistoryService = Depends(_get_chat_history_service),
) -> dict:
    """Wipe all messages for the current user in the given thread."""
    deleted = svc.clear_history(user.oid, orgnr)
    return {"deleted": deleted}
