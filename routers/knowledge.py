import json

from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session

from db import Company, CompanyNote, CompanyChunk, CompanyHistory, InsuranceOffer
from domain.exceptions import LlmUnavailableError, QuotaError
from services import (
    _chunk_and_store,
    _retrieve_chunks,
    _llm_answer,
    _build_company_context,
    _embed,
    _llm_answer_raw,
)
from services.rag import save_qa_note
from rag_chain import build_rag_chain
from schemas import ChatRequest, IngestKnowledgeRequest
from dependencies import get_db
from prompts import CHAT_SYSTEM_PROMPT

router = APIRouter()

SYSTEM_PROMPT = CHAT_SYSTEM_PROMPT  # backward-compat alias


@router.post("/org/{orgnr}/chat")
def chat_about_org(orgnr: str, body: ChatRequest, db: Session = Depends(get_db)):
    from rag_chain import build_rag_chain
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(
            status_code=404,
            detail="Company not in database — call /org/{orgnr} first to load it",
        )

    # Auto-ingest company history + offer texts into CompanyChunk if not already done
    history_rows = db.query(CompanyHistory).filter(CompanyHistory.orgnr == orgnr).all()
    existing_sources = {
        r.source for r in db.query(CompanyChunk).filter(CompanyChunk.orgnr == orgnr).all()
    }
    for h in history_rows:
        src = f"annual_report_{h.year}"
        if src not in existing_sources and h.raw:
            text = json.dumps(h.raw, ensure_ascii=False)
            _chunk_and_store(orgnr, src, text, db)

    offers = db.query(InsuranceOffer).filter(InsuranceOffer.orgnr == orgnr).all()
    for offer in offers:
        src = f"offer_{offer.id}"
        if src not in existing_sources and offer.extracted_text:
            _chunk_and_store(orgnr, src, str(offer.extracted_text), db)

    # Build LangChain RAG chain: retriever uses CompanyChunk, falls back to CompanyNote
    chunk_texts = _retrieve_chunks(orgnr, body.question, db, limit=5)
    if not chunk_texts:
        # Fall back to CompanyNote-based context (legacy)
        q_emb = _embed(body.question)
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
        try:
            answer = _llm_answer(context, body.question)
        except QuotaError as e:
            raise HTTPException(status_code=429, detail=str(e))
        except LlmUnavailableError as e:
            raise HTTPException(status_code=503, detail=str(e))
    else:
        # Use LangChain RAG chain with chunk-based retrieval
        rag = build_rag_chain(
            llm_fn=_llm_answer_raw,
            retriever_fn=lambda q: _retrieve_chunks(orgnr, q, db, limit=5),
            system_prompt=SYSTEM_PROMPT,
        )
        try:
            answer = rag(body.question) or ""
        except QuotaError as e:
            raise HTTPException(status_code=429, detail=str(e))
        except LlmUnavailableError as e:
            raise HTTPException(status_code=503, detail=str(e))

    # Persist Q&A to CompanyNote (backward compat) + to CompanyChunk for future retrieval
    note_id = save_qa_note(orgnr, body.question, answer, db)
    _chunk_and_store(orgnr, f"qa_{note_id}", f"Q: {body.question}\nA: {answer}", db)

    return {"orgnr": orgnr, "question": body.question, "answer": answer}


@router.post("/org/{orgnr}/ingest-knowledge")
def ingest_knowledge(orgnr: str, body: IngestKnowledgeRequest, db: Session = Depends(get_db)):
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
):
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
):
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
