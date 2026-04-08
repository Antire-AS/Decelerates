"""Index video transcripts and insurance documents into the knowledge RAG namespace.

Source key format (used for citations in the UI):
  Videos:  video::{display_name}::{start_seconds}::{chapter_title}
  Docs:    doc::{doc_id}::{title}::{insurer}::{year}
"""
import logging

from sqlalchemy.orm import Session

from api.db import InsuranceDocument, CompanyChunk
from api.services.blob_storage import BlobStorageService

logger = logging.getLogger(__name__)

KNOWLEDGE_ORG = "knowledge"
_VIDEOS_CONTAINER = "transksrt"

# Display names for each sections JSON prefix (mirrors _VIDEO_SECTIONS_MAP in videos.py)
_VIDEO_DISPLAY_NAMES = {
    "ffsformidler": "Forsikringsformidling i praksis",
    "ffskunde":     "Møte med kunden, behovsanalyse og rådgivning",
    "ffslære":      "Forsikringsmeglerrollen – hva kan vi lære?",
    "ffspraktisk":  "Praktisk forsikringsrådgivning",
}


def _fmt_time(s: float) -> str:
    h, m = int(s) // 3600, (int(s) % 3600) // 60
    return f"{h}:{m:02d}:{int(s) % 60:02d}" if h else f"{m}:{int(s) % 60:02d}"


_CHUNK_SIZE = 1800
_CHUNK_OVERLAP = 200


def _split_text(text: str) -> list[str]:
    """Split long text into overlapping windows that fit embedding limits."""
    if len(text) <= _CHUNK_SIZE:
        return [text]
    parts, start = [], 0
    while start < len(text):
        parts.append(text[start:start + _CHUNK_SIZE])
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return parts


def _store_chunk(orgnr: str, source: str, text: str, db: Session) -> None:
    """Embed and store a single chunk directly (bypasses LangChain splitter)."""
    from api.services.llm import _embed
    from api.services.search_service import SearchService
    from datetime import datetime, timezone

    embedding = _embed(text)
    chunk = CompanyChunk(
        orgnr=orgnr,
        source=source,
        chunk_text=text,
        embedding=embedding if embedding else None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(chunk)
    db.flush()
    if embedding:
        SearchService().index_chunk(orgnr, source, text, embedding)


def _source_exists(source: str, db: Session) -> bool:
    return (
        db.query(CompanyChunk)
        .filter(CompanyChunk.orgnr == KNOWLEDGE_ORG, CompanyChunk.source == source)
        .first()
    ) is not None


def clear_knowledge(db: Session) -> int:
    """Delete all knowledge chunks. Returns count deleted."""
    rows = db.query(CompanyChunk).filter(CompanyChunk.orgnr == KNOWLEDGE_ORG).all()
    count = len(rows)
    for r in rows:
        db.delete(r)
    db.commit()
    logger.info("Knowledge index: cleared %d chunks", count)
    return count


def index_insurance_documents(db: Session) -> int:
    """One chunk per insurance document (header + full extracted text). Returns new chunk count."""
    total = 0
    docs = db.query(InsuranceDocument).filter(InsuranceDocument.extracted_text.isnot(None)).all()
    for doc in docs:
        source = f"doc::{doc.id}::{doc.title or '-'}::{doc.insurer or '-'}::{doc.year or '-'}"
        if _source_exists(source, db):
            continue
        text = (
            f"Dokument: {doc.title}\n"
            f"Forsikringsselskap: {doc.insurer or '-'}\n"
            f"År: {doc.year or '-'}\n"
            f"Kategori: {doc.category or '-'}\n\n"
            + doc.extracted_text
        )
        _store_chunk(KNOWLEDGE_ORG, source, text[:3000], db)
        total += 1
        logger.info("Knowledge index: doc %d (%s) indexed", doc.id, doc.title)
    db.commit()
    return total


def index_video_transcripts(db: Session) -> int:
    """One chunk per chapter/section with timestamp. Returns new chunk count."""
    svc = BlobStorageService()
    if not svc.is_configured():
        return 0
    total = 0
    try:
        all_blobs = set(svc.list_blobs(_VIDEOS_CONTAINER))
        json_blobs = [
            b for b in all_blobs
            if b.endswith("_sections.json") or b.endswith("_timeline.json")
        ]
        for blob_name in json_blobs:
            # Derive display name from blob file stem (e.g. "ffsformidler_sections.json")
            stem = blob_name.rsplit("/", 1)[-1].replace("_sections.json", "").replace("_timeline.json", "")
            display_name = _VIDEO_DISPLAY_NAMES.get(stem, stem.replace("_", " ").title())

            data = svc.download_json(_VIDEOS_CONTAINER, blob_name)
            if not data:
                continue
            sections = data if isinstance(data, list) else (data.get("sections") or [])

            for sec in sections:
                chapter_title = (sec.get("title") or "").strip()
                if not chapter_title:
                    continue  # skip untitled intro entries
                start_s = int(sec.get("start_seconds") or 0)
                source = f"video::{display_name}::{start_s}::{chapter_title}"

                if _source_exists(source, db):
                    continue

                # Build self-describing chunk: header + description + transcript lines
                header = "\n".join([
                    f"Video: {display_name}",
                    f"Kapittel: {chapter_title}",
                    f"Tid: {_fmt_time(start_s)}",
                ])
                body_lines = []
                if sec.get("description"):
                    body_lines.append(sec["description"])
                for entry in (sec.get("entries") or []):
                    t = (entry.get("text") or "").strip()
                    if t:
                        body_lines.append(t)

                body = "\n".join(body_lines).strip()
                if len(body) < 10:
                    continue

                # Split long sections into sub-chunks; first chunk gets base source key
                for i, part in enumerate(_split_text(body)):
                    chunk_source = source if i == 0 else f"{source}::{i + 1}"
                    _store_chunk(KNOWLEDGE_ORG, chunk_source, f"{header}\n\n{part}", db)
                    total += 1

        logger.info("Knowledge index: %d new video section chunks", total)
    except Exception as exc:
        logger.warning("Knowledge index: video indexing failed — %s", exc)
        db.rollback()
        return 0
    db.commit()
    return total


def index_all(db: Session) -> dict:
    """Index all knowledge sources. Returns counts of new chunks added."""
    docs_chunks = index_insurance_documents(db)
    video_chunks = index_video_transcripts(db)
    return {"docs_chunks": docs_chunks, "video_chunks": video_chunks}


def get_stats(db: Session) -> dict:
    """Return counts of indexed chunks per source type. Field names match
    KnowledgeStatsOut and the frontend api.ts contract — do not rename."""
    rows = db.query(CompanyChunk).filter(CompanyChunk.orgnr == KNOWLEDGE_ORG).all()
    doc_count = sum(1 for r in rows if r.source.startswith("doc::"))
    video_count = sum(1 for r in rows if r.source.startswith("video::"))
    return {"total_chunks": len(rows), "doc_chunks": doc_count, "video_chunks": video_count}
