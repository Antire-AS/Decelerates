import json

from fastapi import APIRouter, Query, HTTPException, Depends, Request
from sqlalchemy.orm import Session

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
from api.services.rag import save_qa_note
from api.rag_chain import build_rag_chain
from api.schemas import ChatRequest, IngestKnowledgeRequest
from api.dependencies import get_db
from api.limiter import limiter
from api.prompts import CHAT_SYSTEM_PROMPT, KNOWLEDGE_CHAT_SYSTEM_PROMPT

router = APIRouter()


def _auto_ingest_company_data(orgnr: str, db: Session) -> None:
    """Ingest history rows and offer texts into CompanyChunk if not already done."""
    existing_sources = {
        r.source for r in db.query(CompanyChunk).filter(CompanyChunk.orgnr == orgnr).all()
    }
    for h in db.query(CompanyHistory).filter(CompanyHistory.orgnr == orgnr).all():
        src = f"annual_report_{h.year}"
        if src not in existing_sources and h.raw:
            _chunk_and_store(orgnr, src, json.dumps(h.raw, ensure_ascii=False), db)
    for offer in db.query(InsuranceOffer).filter(InsuranceOffer.orgnr == orgnr).all():
        src = f"offer_{offer.id}"
        if src not in existing_sources and offer.extracted_text:
            _chunk_and_store(orgnr, src, str(offer.extracted_text), db)


def _answer_with_rag_or_notes(orgnr: str, question: str, db_obj: Company, db: Session) -> str:
    """Try chunk-based RAG; fall back to CompanyNote cosine search."""
    chunk_texts = _retrieve_chunks(orgnr, question, db, limit=5)
    if chunk_texts:
        rag = build_rag_chain(
            llm_fn=_llm_answer_raw,
            retriever_fn=lambda q: _retrieve_chunks(orgnr, q, db, limit=5),
            system_prompt=CHAT_SYSTEM_PROMPT,
        )
        return rag(question) or ""

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
    return _llm_answer(_build_company_context(db_obj, relevant_notes), question)


@router.post("/org/{orgnr}/chat")
@limiter.limit("10/minute")
def chat_about_org(request: Request, orgnr: str, body: ChatRequest, db: Session = Depends(get_db)):
    from api.rag_chain import build_rag_chain
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(
            status_code=404,
            detail="Company not in database — call /org/{orgnr} first to load it",
        )
    _auto_ingest_company_data(orgnr, db)
    try:
        answer = _answer_with_rag_or_notes(orgnr, body.question, db_obj, db)
    except QuotaError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except LlmUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))

    note_id = save_qa_note(orgnr, body.question, answer, db)
    _chunk_and_store(orgnr, f"qa_{note_id}", f"Q: {body.question}\nA: {answer}", db)
    return {"orgnr": orgnr, "question": body.question, "answer": answer}


@router.post("/org/{orgnr}/ingest-knowledge")
def ingest_knowledge(orgnr: str, body: IngestKnowledgeRequest, db: Session = Depends(get_db)) -> dict:
    """Manually chunk and embed text into the company's knowledge base."""
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")
    count = _chunk_and_store(orgnr, body.source, body.text, db)
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
            db.query(CompanyChunk)
            .order_by(CompanyChunk.id.desc())
            .limit(limit)
            .all()
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
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list:
    notes = (
        db.query(CompanyNote)
        .filter(CompanyNote.orgnr == orgnr)
        .order_by(CompanyNote.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": n.id,
            "question": n.question,
            "answer": n.answer,
            "created_at": n.created_at,
        }
        for n in notes
    ]


# ── Knowledge base chat (videos + insurance docs) ─────────────────────────────

def _retrieve_knowledge_chunks(question: str, db: Session, limit: int = 6) -> list:
    """Return [{text, source}] from the knowledge namespace, ordered by relevance."""
    from api.services.knowledge_index import KNOWLEDGE_ORG
    q_emb = _embed(question)
    if q_emb:
        rows = (
            db.query(CompanyChunk)
            .filter(CompanyChunk.orgnr == KNOWLEDGE_ORG, CompanyChunk.embedding.isnot(None))
            .order_by(CompanyChunk.embedding.cosine_distance(q_emb))
            .limit(limit)
            .all()
        )
    else:
        rows = (
            db.query(CompanyChunk)
            .filter(CompanyChunk.orgnr == KNOWLEDGE_ORG)
            .order_by(CompanyChunk.id.desc())
            .limit(limit)
            .all()
        )
    return [{"text": r.chunk_text, "source": r.source} for r in rows]


@router.post("/knowledge/chat")
@limiter.limit("10/minute")
def chat_knowledge(request: Request, body: ChatRequest, db: Session = Depends(get_db)):
    """RAG chat over indexed knowledge (video transcripts + insurance documents)."""
    from api.services.knowledge_index import KNOWLEDGE_ORG, index_all
    if not db.query(CompanyChunk).filter(CompanyChunk.orgnr == KNOWLEDGE_ORG).first():
        index_all(db)
    chunks = _retrieve_knowledge_chunks(body.question, db)
    if not chunks:
        return {
            "question": body.question,
            "answer": "Ingen kunnskap er indeksert ennå. Gå til Administrer-fanen og klikk 'Indekser kunnskap'.",
            "sources": [],
        }
    context = "\n\n---\n\n".join(f"[Kilde: {c['source']}]\n{c['text']}" for c in chunks)
    sources = list(dict.fromkeys(c["source"] for c in chunks))
    # _llm_answer_raw takes a single pre-formatted prompt string
    prompt = (
        f"[SYSTEM]: {KNOWLEDGE_CHAT_SYSTEM_PROMPT}\n\n"
        f"Kontekst:\n{context}\n\n"
        f"[SPØRSMÅL]: {body.question}"
    )
    try:
        answer = _llm_answer_raw(prompt) or "Beklager, fikk ikke svar fra AI-tjenesten."
    except LlmUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except QuotaError as e:
        raise HTTPException(status_code=429, detail=str(e))
    return {"question": body.question, "answer": answer, "sources": sources}


@router.post("/knowledge/index")
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
    return {
        **result,
        "cleared_chunks": cleared,
        "total_new_chunks": result["docs_chunks"] + result["video_chunks"],
        "index_stats": stats,
    }


@router.get("/knowledge/index/stats")
def knowledge_index_stats(db: Session = Depends(get_db)) -> dict:
    """Return current knowledge index statistics."""
    from api.services.knowledge_index import get_stats
    return get_stats(db)
