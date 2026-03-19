"""RAG helpers — chunking, embedding, retrieval, and context building."""
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from api.db import Company, CompanyNote, CompanyChunk
from api.rag_chain import chunk_text, embed_chunks
from api.services.llm import _embed, _fmt_nok
from api.services.search_service import SearchService


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


class RagService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def chunk_and_store(self, orgnr: str, source: str, text: str) -> int:
        """Chunk *text* using LangChain splitter and store in CompanyChunk. Returns chunk count."""
        chunks = chunk_text(text, source)
        embedded = embed_chunks(chunks, _embed)
        now = datetime.now(timezone.utc).isoformat()
        search_svc = SearchService()
        count = 0
        for chunk_text_val, src, vector in embedded:
            c = CompanyChunk(
                orgnr=orgnr,
                source=src,
                chunk_text=chunk_text_val,
                embedding=vector if vector else None,
                created_at=now,
            )
            self.db.add(c)
            if search_svc.is_configured() and vector:
                search_svc.index_chunk(orgnr, src, chunk_text_val, vector)
            count += 1
        self.db.commit()
        return count

    def retrieve_chunks(self, orgnr: str, question: str, limit: int = 5) -> list[str]:
        """Retrieve the most relevant CompanyChunk texts for *question* via cosine distance."""
        q_emb = _embed(question)
        search_svc = SearchService()
        if search_svc.is_configured() and q_emb:
            results = search_svc.search_chunks(orgnr, q_emb, limit)
            if results:
                return results
        return self._pgvector_retrieve(orgnr, q_emb, limit)

    def _pgvector_retrieve(self, orgnr: str, q_emb, limit: int) -> list[str]:
        """Fallback: retrieve chunks from pgvector."""
        if q_emb:
            rows = (
                self.db.query(CompanyChunk)
                .filter(CompanyChunk.orgnr == orgnr, CompanyChunk.embedding.isnot(None))
                .order_by(CompanyChunk.embedding.cosine_distance(q_emb))
                .limit(limit)
                .all()
            )
        else:
            rows = (
                self.db.query(CompanyChunk)
                .filter(CompanyChunk.orgnr == orgnr)
                .order_by(CompanyChunk.id.desc())
                .limit(limit)
                .all()
            )
        return [r.chunk_text for r in rows]

    def save_qa_note(self, orgnr: str, question: str, answer: str) -> int:
        """Persist a Q&A pair as a CompanyNote with embedding. Returns the note ID."""
        emb = _embed(f"{question} {answer}")
        note = CompanyNote(
            orgnr=orgnr,
            question=question,
            answer=answer,
            created_at=datetime.now(timezone.utc).isoformat(),
            embedding=emb if emb else None,
        )
        self.db.add(note)
        self.db.commit()
        return note.id

    def save_to_rag(self, orgnr: str, label: str, content: str) -> None:
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
            self.db.add(note)
            self.db.commit()
        except Exception:
            pass


# ── Module-level backward-compat wrappers ─────────────────────────────────────

def _chunk_and_store(orgnr: str, source: str, text: str, db: Session) -> int:
    return RagService(db).chunk_and_store(orgnr, source, text)


def _retrieve_chunks(orgnr: str, question: str, db: Session, limit: int = 5) -> list[str]:
    return RagService(db).retrieve_chunks(orgnr, question, limit)


def save_qa_note(orgnr: str, question: str, answer: str, db: Session) -> int:
    return RagService(db).save_qa_note(orgnr, question, answer)


def _save_to_rag(orgnr: str, label: str, content: str, db: Session) -> None:
    RagService(db).save_to_rag(orgnr, label, content)
