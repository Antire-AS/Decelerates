"""RAG helpers — chunking, embedding, retrieval, and context building."""
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from db import Company, CompanyNote, CompanyChunk
from rag_chain import chunk_text, embed_chunks
from services.llm import _embed, _fmt_nok


def _build_company_context(db_obj: Company, relevant_notes: List) -> str:
    pep_raw = db_obj.pep_raw or {}
    pep_hits = pep_raw.get("hit_count", 0)

    lines = [
        f"Company: {db_obj.navn} (orgnr: {db_obj.orgnr})",
        f"Legal form: {db_obj.organisasjonsform_kode}",
        f"Municipality: {db_obj.kommune}, {db_obj.land}",
        f"Industry: {db_obj.naeringskode1} – {db_obj.naeringskode1_beskrivelse}",
        f"PEP/sanctions hits: {pep_hits}",
    ]

    if db_obj.regnskapsår:
        eq_pct = (
            f"{db_obj.equity_ratio * 100:.1f}%"
            if db_obj.equity_ratio is not None
            else "–"
        )
        lines += [
            f"\nFinancials ({db_obj.regnskapsår}):",
            f"  Turnover: {_fmt_nok(db_obj.sum_driftsinntekter)}",
            f"  Total equity: {_fmt_nok(db_obj.sum_egenkapital)}",
            f"  Total assets: {_fmt_nok(db_obj.sum_eiendeler)}",
            f"  Equity ratio: {eq_pct}",
            f"  Risk score: {db_obj.risk_score}",
        ]
        raw = db_obj.regnskap_raw or {}
        if raw.get("aarsresultat") is not None:
            lines.append(f"  Annual result: {_fmt_nok(raw.get('aarsresultat'))}")
        if raw.get("antall_ansatte") is not None:
            lines.append(f"  Employees: {raw.get('antall_ansatte')}")
        if raw.get("sum_langsiktig_gjeld") is not None:
            lines.append(f"  Long-term debt: {_fmt_nok(raw.get('sum_langsiktig_gjeld'))}")

    if relevant_notes:
        lines.append("\nRelevant analyst notes (retrieved by semantic similarity):")
        for note in relevant_notes:
            if note.orgnr == db_obj.orgnr:
                label = f"[{note.created_at[:10]}]"
            else:
                label = f"[{note.created_at[:10]}, re: orgnr {note.orgnr}]"
            lines.append(f"  {label} Q: {note.question}")
            lines.append(f"  A: {note.answer}")

    return "\n".join(lines)


def _chunk_and_store(orgnr: str, source: str, text: str, db: Session) -> int:
    """Chunk *text* using LangChain splitter and store in CompanyChunk. Returns chunk count."""
    chunks = chunk_text(text, source)
    embedded = embed_chunks(chunks, _embed)
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    for chunk_text_val, src, vector in embedded:
        c = CompanyChunk(
            orgnr=orgnr,
            source=src,
            chunk_text=chunk_text_val,
            embedding=vector if vector else None,
            created_at=now,
        )
        db.add(c)
        count += 1
    db.commit()
    return count


def _retrieve_chunks(orgnr: str, question: str, db: Session, limit: int = 5) -> list[str]:
    """Retrieve the most relevant CompanyChunk texts for *question* via cosine distance."""
    q_emb = _embed(question)
    if q_emb:
        rows = (
            db.query(CompanyChunk)
            .filter(CompanyChunk.orgnr == orgnr, CompanyChunk.embedding.isnot(None))
            .order_by(CompanyChunk.embedding.cosine_distance(q_emb))
            .limit(limit)
            .all()
        )
    else:
        rows = (
            db.query(CompanyChunk)
            .filter(CompanyChunk.orgnr == orgnr)
            .order_by(CompanyChunk.id.desc())
            .limit(limit)
            .all()
        )
    return [r.chunk_text for r in rows]


def save_qa_note(orgnr: str, question: str, answer: str, db: Session) -> int:
    """Persist a Q&A pair as a CompanyNote with embedding. Returns the note ID."""
    emb = _embed(f"{question} {answer}")
    note = CompanyNote(
        orgnr=orgnr,
        question=question,
        answer=answer,
        created_at=datetime.now(timezone.utc).isoformat(),
        embedding=emb if emb else None,
    )
    db.add(note)
    db.commit()
    return note.id


def _save_to_rag(orgnr: str, label: str, content: str, db: Session) -> None:
    """Embed and persist AI-generated content to company_notes for RAG retrieval."""
    try:
        emb = _embed(f"{label} {content}")
        note = CompanyNote(
            orgnr=orgnr,
            question=label,
            answer=content,
            created_at=datetime.now(timezone.utc).isoformat(),
            embedding=emb if emb else None,
        )
        db.add(note)
        db.commit()
    except Exception:
        pass
