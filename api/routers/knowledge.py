import json
import logging
import uuid

from fastapi import APIRouter, Query, HTTPException, Depends, Request

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import Company, CompanyNote, CompanyChunk, CompanyHistory, InsuranceOffer
from api.domain.exceptions import LlmUnavailableError, QuotaError
from api.services import (
    _chunk_and_store,
    _retrieve_chunks,
    _llm_answer,
    _build_company_context,
    _embed,
    _llm_answer_raw,
)
from api.services.rag import save_qa_note, clear_chat_session as _clear_chat_session
from api.services.chat_history import ChatHistoryService, format_history_for_prompt
from api.rag_chain import build_rag_chain
from api.schemas import (
    ChatRequest,
    IngestKnowledgeRequest,
    IngestKnowledgeOut,
    KnowledgeStatsOut,
    KnowledgeIndexOut,
    KnowledgeChatOut,
    OrgChatOut,
    SeedRegulationsOut,
)
from api.dependencies import get_db
from api.services.audit import log_audit
from api.limiter import limiter
from api.prompts import CHAT_SYSTEM_PROMPT, KNOWLEDGE_CHAT_SYSTEM_PROMPT

router = APIRouter()


def _auto_ingest_company_data(orgnr: str, db: Session) -> None:
    """Ingest history rows and offer texts into CompanyChunk if not already done."""
    existing_sources = {
        r.source
        for r in db.query(CompanyChunk).filter(CompanyChunk.orgnr == orgnr).all()
    }
    for h in db.query(CompanyHistory).filter(CompanyHistory.orgnr == orgnr).all():
        src = f"annual_report_{h.year}"
        if src not in existing_sources and h.raw:
            _chunk_and_store(orgnr, src, json.dumps(h.raw, ensure_ascii=False), db)
    for offer in db.query(InsuranceOffer).filter(InsuranceOffer.orgnr == orgnr).all():
        src = f"offer_{offer.id}"
        if src not in existing_sources and offer.extracted_text:
            _chunk_and_store(orgnr, src, str(offer.extracted_text), db)


def _build_history_context(
    orgnr: str, db: Session, session_id: str | None = None, limit: int = 5
) -> str:
    """Return last N Q&A pairs as a formatted conversation history string."""
    q = db.query(CompanyNote).filter(CompanyNote.orgnr == orgnr)
    if session_id:
        q = q.filter(CompanyNote.session_id == session_id)
    notes = q.order_by(CompanyNote.id.desc()).limit(limit).all()
    if not notes:
        return ""
    pairs = "\n".join(f"Q: {n.question}\nA: {n.answer}" for n in reversed(notes))
    return f"Previous conversation:\n{pairs}"


def _answer_with_rag_or_notes(
    orgnr: str, question: str, db_obj: Company, db: Session, history_ctx: str = ""
) -> str:
    """Try chunk-based RAG; fall back to CompanyNote cosine search."""
    full_q = (
        f"{history_ctx}\n\nCurrent question: {question}" if history_ctx else question
    )

    chunk_texts = _retrieve_chunks(orgnr, question, db, limit=5)
    if chunk_texts:
        rag = build_rag_chain(
            llm_fn=_llm_answer_raw,
            retriever_fn=lambda q: _retrieve_chunks(orgnr, q, db, limit=5),
            system_prompt=CHAT_SYSTEM_PROMPT,
        )
        return rag(full_q) or ""

    q_emb = _embed(question)
    if q_emb:
        relevant_notes = (
            db.query(CompanyNote)
            .filter(CompanyNote.orgnr == orgnr, CompanyNote.embedding.isnot(None))
            .order_by(CompanyNote.embedding.cosine_distance(q_emb))
            .limit(5)
            .all()
        )
    else:
        relevant_notes = (
            db.query(CompanyNote)
            .filter(CompanyNote.orgnr == orgnr)
            .order_by(CompanyNote.id.desc())
            .limit(5)
            .all()
        )[::-1]
    context = _build_company_context(db_obj, relevant_notes)
    if history_ctx:
        context = f"{context}\n\n{history_ctx}"
    return _llm_answer(context, question)


def _chat_agent_mode(
    orgnr: str, question: str, firm_id: int, db: Session, session_id: str
) -> dict:
    """Copilot agent mode — tool-use chat that can take actions."""
    from api.services.copilot_agent import chat_with_tools

    try:
        result = chat_with_tools(question, orgnr, firm_id, db)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    answer = result["answer"]
    save_qa_note(orgnr, question, answer, db, session_id=session_id)
    return {
        "orgnr": orgnr,
        "question": question,
        "answer": answer,
        "session_id": session_id,
        "tool_calls": result.get("tool_calls_made", []),
    }


def _build_combined_history(
    orgnr: str, session_id: str, user_oid: str, db: Session
) -> tuple[str, ChatHistoryService]:
    """Combine session-scoped history with user-scoped history across sessions.

    User-scoped block delivers the "memory" brokers asked for: continuity
    even after a reload or coming back next week. Returns the combined
    prompt block plus the service handle so the caller can append the
    current turn after the LLM answers.
    """
    session_ctx = _build_history_context(orgnr, db, session_id=session_id)
    svc = ChatHistoryService(db)
    user_history = svc.load_history(user_oid, orgnr, limit_turns=20)
    user_block = format_history_for_prompt(user_history)
    combined = "\n\n".join(b for b in (user_block, session_ctx) if b)
    return combined, svc


def _run_rag_chat(
    orgnr: str,
    body: ChatRequest,
    db_obj: Company,
    active_session: str,
    user: CurrentUser,
    db: Session,
) -> str:
    """Execute the RAG chat path: build history, call LLM, persist turn.

    Wraps LLM domain exceptions as HTTP errors so chat_about_org stays short.
    """
    history_ctx, chat_history_svc = _build_combined_history(
        orgnr, active_session, user.oid, db
    )
    try:
        answer = _answer_with_rag_or_notes(
            orgnr, body.question, db_obj, db, history_ctx
        )
    except QuotaError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except LlmUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    note_id = save_qa_note(orgnr, body.question, answer, db, session_id=active_session)
    _chunk_and_store(orgnr, f"qa_{note_id}", f"Q: {body.question}\nA: {answer}", db)
    chat_history_svc.append_turn(user.oid, orgnr, body.question, answer)
    return answer


@router.post("/org/{orgnr}/chat", response_model=OrgChatOut)
@limiter.limit("10/minute")
def chat_about_org(
    request: Request,
    orgnr: str,
    body: ChatRequest,
    session_id: str = Query(default=""),
    mode: str = Query(default="rag"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    from api.rag_chain import build_rag_chain  # noqa: F401 (imported for side-effects)

    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(
            status_code=404,
            detail="Company not in database — call /org/{orgnr} first to load it",
        )
    active_session = session_id.strip() or str(uuid.uuid4())
    if mode == "agent":
        return _chat_agent_mode(orgnr, body.question, user.firm_id, db, active_session)
    _auto_ingest_company_data(orgnr, db)
    answer = _run_rag_chat(orgnr, body, db_obj, active_session, user, db)
    log_audit(db, "chat.org", orgnr=orgnr, detail={"session_id": active_session})
    return {
        "orgnr": orgnr,
        "question": body.question,
        "answer": answer,
        "session_id": active_session,
    }


@router.post("/org/{orgnr}/ingest-knowledge", response_model=IngestKnowledgeOut)
def ingest_knowledge(
    orgnr: str, body: IngestKnowledgeRequest, db: Session = Depends(get_db)
) -> dict:
    """Manually chunk and embed text into the company's knowledge base."""
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")
    count = _chunk_and_store(orgnr, body.source, body.text, db)
    log_audit(
        db,
        "knowledge.ingest",
        orgnr=orgnr,
        detail={"source": body.source, "chunks": count},
    )
    return {"orgnr": orgnr, "source": body.source, "chunks_stored": count}


@router.get("/knowledge")
def search_knowledge(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list:
    """Full-knowledge search: find the most relevant chunks across ALL companies."""
    q_emb = _embed(query)
    if q_emb:
        rows = (
            db.query(CompanyChunk)
            .filter(CompanyChunk.embedding.isnot(None))
            .order_by(CompanyChunk.embedding.cosine_distance(q_emb))
            .limit(limit)
            .all()
        )
    else:
        rows = (
            db.query(CompanyChunk).order_by(CompanyChunk.id.desc()).limit(limit).all()
        )
    return [
        {
            "orgnr": r.orgnr,
            "source": r.source,
            "chunk_text": r.chunk_text[:400],
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/org/{orgnr}/chat")
def get_chat_history(
    orgnr: str,
    session_id: str = Query(default=""),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list:
    q = db.query(CompanyNote).filter(CompanyNote.orgnr == orgnr)
    if session_id.strip():
        q = q.filter(CompanyNote.session_id == session_id.strip())
    notes = q.order_by(CompanyNote.id.asc()).limit(limit).all()
    return [
        {
            "id": n.id,
            "session_id": n.session_id,
            "question": n.question,
            "answer": n.answer,
            "created_at": n.created_at,
        }
        for n in notes
    ]


@router.delete("/org/{orgnr}/chat")
def delete_chat_session(
    orgnr: str,
    session_id: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    """Delete all Q&A notes for a specific chat session."""
    deleted = _clear_chat_session(orgnr, session_id, db)
    log_audit(
        db,
        "chat.delete",
        orgnr=orgnr,
        detail={"session_id": session_id, "deleted": deleted},
    )
    return {"deleted": deleted, "session_id": session_id}


# ── Knowledge base chat (videos + insurance docs) ─────────────────────────────


def _chunk_snippet(text: str, max_len: int = 140) -> str:
    """Return the first meaningful sentence from a chunk, skipping header lines."""
    _HEADERS = (
        "Video:",
        "Kapittel:",
        "Tid:",
        "Dokument:",
        "Forsikringsselskap:",
        "År:",
        "Kategori:",
    )
    lines = [
        l.strip()
        for l in text.splitlines()
        if l.strip() and not any(l.startswith(h) for h in _HEADERS)
    ]
    snippet = " ".join(lines)[:max_len]
    return snippet + "…" if len(" ".join(lines)) > max_len else snippet


def _readable_source(source: str) -> str:
    """Return a human-readable citation label for LLM context."""
    if source.startswith("video::"):
        parts = source.split("::")
        if len(parts) == 5 and parts[4].isdigit():
            parts = parts[:4]
        if len(parts) == 4:
            _, name, start_s, chapter = parts
            try:
                s = int(start_s)
                h, m = s // 3600, (s % 3600) // 60
                ts = f"{h}:{m:02d}:{s % 60:02d}" if h else f"{m}:{s % 60:02d}"
            except ValueError:
                ts = start_s
            return f"{name} — {chapter} ({ts})"
    if source.startswith("doc::"):
        parts = source.split("::")
        return parts[2] if len(parts) >= 3 and parts[2] != "-" else source
    return source


# pgvector cosine_distance: 0 = identical, 1 = orthogonal, 2 = opposite.
# 0.55 keeps borderline-relevant matches (corpus is conversational transcript
# data so similarity scores run lower than a clean document set).
_MAX_COSINE_DISTANCE = 0.55


def _vector_matches(question: str, db: Session, limit: int) -> list:
    """Vector similarity hits above the relevance threshold."""
    from api.services.knowledge_index import KNOWLEDGE_ORG

    q_emb = _embed(question)
    if not q_emb:
        return []
    distance = CompanyChunk.embedding.cosine_distance(q_emb)
    return list(
        db.query(CompanyChunk)
        .filter(
            CompanyChunk.orgnr == KNOWLEDGE_ORG,
            CompanyChunk.embedding.isnot(None),
            distance < _MAX_COSINE_DISTANCE,
        )
        .order_by(distance)
        .limit(limit)
        .all()
    )


def _keyword_matches(question: str, db: Session, seen: set[int]) -> list:
    """Source-key keyword matches — catches exact chapter hits the vector misses."""
    from api.services.knowledge_index import KNOWLEDGE_ORG

    extra = []
    keywords = [w for w in question.lower().split() if len(w) > 3]
    for kw in keywords[:4]:
        for r in (
            db.query(CompanyChunk)
            .filter(
                CompanyChunk.orgnr == KNOWLEDGE_ORG,
                CompanyChunk.source.ilike(f"%{kw}%"),
            )
            .limit(4)
            .all()
        ):
            if r.id not in seen:
                extra.append(r)
                seen.add(r.id)
    return extra


def _retrieve_knowledge_chunks(question: str, db: Session, limit: int = 8) -> list:
    """Hybrid retrieval: vector similarity (filtered by distance) + keyword match."""
    vector_hits = _vector_matches(question, db, limit)
    seen = {r.id for r in vector_hits}
    keyword_hits = _keyword_matches(question, db, seen)
    results = vector_hits + keyword_hits
    return [{"text": r.chunk_text, "source": r.source} for r in results[: limit + 4]]


def _build_knowledge_prompt(question: str, context: str, history_block: str) -> str:
    """Compose the final knowledge-chat prompt.

    History block goes BEFORE the retrieved context so the LLM treats past
    turns as conversational priors and current context as authoritative.
    """
    parts = [f"[SYSTEM]: {KNOWLEDGE_CHAT_SYSTEM_PROMPT}"]
    if history_block:
        parts.append(history_block)
    parts.append(f"Kontekst:\n{context}")
    parts.append(f"[SPØRSMÅL]: {question}")
    return "\n\n".join(parts)


def _knowledge_no_chunks_response(question: str) -> dict:
    return {
        "question": question,
        "answer": "Ingen kunnskap er indeksert ennå, eller ingen relevante kilder for dette spørsmålet. Gå til Administrer-fanen og klikk 'Indekser kunnskap' hvis basen er tom, eller prøv å omformulere spørsmålet.",
        "sources": [],
        "source_snippets": {},
    }


@router.post("/knowledge/chat", response_model=KnowledgeChatOut)
@limiter.limit("10/minute")
def chat_knowledge(
    request: Request,
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """RAG chat over indexed knowledge (video transcripts + insurance documents)."""
    chunks = _retrieve_knowledge_chunks(body.question, db)
    if not chunks:
        return _knowledge_no_chunks_response(body.question)

    context = "\n\n---\n\n".join(
        f"[Kilde: {_readable_source(c['source'])}]\n{c['text']}" for c in chunks
    )
    sources = list(dict.fromkeys(c["source"] for c in chunks))
    source_snippets = {c["source"]: _chunk_snippet(c["text"]) for c in chunks}

    history_svc = ChatHistoryService(db)
    history = history_svc.load_history(user.oid, orgnr=None, limit_turns=20)
    prompt = _build_knowledge_prompt(
        body.question, context, format_history_for_prompt(history)
    )

    try:
        answer = _llm_answer_raw(prompt) or "Beklager, fikk ikke svar fra AI-tjenesten."
    except LlmUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except QuotaError as e:
        raise HTTPException(status_code=429, detail=str(e))

    history_svc.append_turn(user.oid, orgnr=None, question=body.question, answer=answer)
    log_audit(db, "knowledge.chat", detail={"sources_count": len(sources)})
    return {
        "question": body.question,
        "answer": answer,
        "sources": sources,
        "source_snippets": source_snippets,
    }


@router.post("/knowledge/index", response_model=KnowledgeIndexOut)
def trigger_knowledge_index(force: bool = False, db: Session = Depends(get_db)) -> dict:
    """Trigger (re-)indexing of all video transcripts and insurance documents.
    Set force=true to wipe existing knowledge chunks before re-indexing."""
    from api.services.knowledge_index import index_all, get_stats, clear_knowledge

    if force:
        cleared = clear_knowledge(db)
    else:
        cleared = 0
    result = index_all(db)
    stats = get_stats(db)
    log_audit(db, "knowledge.index", detail={"force": force, "cleared": cleared})
    return {
        **result,
        "cleared_chunks": cleared,
        "total_new_chunks": result["docs_chunks"] + result["video_chunks"],
        "index_stats": stats,
    }


@router.get("/knowledge/index/stats", response_model=KnowledgeStatsOut)
def knowledge_index_stats(db: Session = Depends(get_db)) -> dict:
    """Return current knowledge index statistics."""
    from api.services.knowledge_index import get_stats

    return get_stats(db)


# ── Norwegian insurance regulations ───────────────────────────────────────────

_REGULATION_SOURCES = [
    {
        "name": "Forsikringsavtaleloven (FAL) 1989",
        "url": "https://lovdata.no/dokument/NL/lov/1989-06-16-69",
    },
    {
        "name": "Forsikringsformidlingsloven 2005",
        "url": "https://lovdata.no/dokument/NL/lov/2005-06-10-44",
    },
    {
        "name": "Forsikringsvirksomhetsloven 2015",
        "url": "https://lovdata.no/dokument/NL/lov/2015-04-10-17",
    },
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; BrokerAccelerator/1.0; "
        "+https://github.com/Antire-AS/Decelerates)"
    )
}


def _fetch_regulation_text(url: str) -> str | None:
    """Fetch a Lovdata page and return plain text, or None on failure."""
    import re
    import html as html_lib
    import requests as req

    try:
        r = req.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        text = r.text
        # Remove <script> and <style> blocks
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.S | re.I)
        # Strip all remaining tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Unescape HTML entities (&amp; &nbsp; etc.)
        text = html_lib.unescape(text)
        # Collapse whitespace
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
    except Exception as exc:
        logger.warning("seed_regulations: failed to fetch %s — %s", url, exc)
        return None


@router.post("/knowledge/seed-regulations", response_model=SeedRegulationsOut)
def seed_regulations(db: Session = Depends(get_db)) -> dict:
    """Fetch and index Norwegian insurance regulations into the knowledge base.

    Sources: Forsikringsavtaleloven, Forsikringsformidlingsloven,
    Forsikringsvirksomhetsloven — all from Lovdata.no (open access).
    Already-indexed regulations are skipped (idempotent).
    """
    from api.services.knowledge_index import KNOWLEDGE_ORG
    from api.db import CompanyChunk

    existing_sources = {
        r.source
        for r in db.query(CompanyChunk.source)
        .filter(CompanyChunk.orgnr == KNOWLEDGE_ORG)
        .filter(CompanyChunk.source.like("regulation::%"))
        .all()
    }

    results = []
    for reg in _REGULATION_SOURCES:
        source_key = f"regulation::{reg['name']}"
        if source_key in existing_sources:
            results.append(
                {"name": reg["name"], "chunks": 0, "status": "already_indexed"}
            )
            continue

        text = _fetch_regulation_text(reg["url"])
        if not text or len(text) < 200:
            results.append({"name": reg["name"], "chunks": 0, "status": "fetch_failed"})
            continue

        chunks = _chunk_and_store(KNOWLEDGE_ORG, source_key, text, db)
        results.append({"name": reg["name"], "chunks": chunks, "status": "indexed"})
        logger.info("seed_regulations: indexed %s — %d chunks", reg["name"], chunks)

    log_audit(
        db, "knowledge.seed", detail={"total_chunks": sum(r["chunks"] for r in results)}
    )
    return {"seeded": results, "total_chunks": sum(r["chunks"] for r in results)}
