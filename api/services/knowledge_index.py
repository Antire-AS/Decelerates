"""Index video transcripts and insurance documents into the knowledge RAG namespace."""
import logging

from sqlalchemy.orm import Session

from api.db import InsuranceDocument, CompanyChunk
from api.services.rag import _chunk_and_store
from api.services.blob_storage import BlobStorageService

logger = logging.getLogger(__name__)

KNOWLEDGE_ORG = "knowledge"
_VIDEOS_CONTAINER = "transksrt"


def _already_indexed(source: str, db: Session) -> bool:
    return (
        db.query(CompanyChunk)
        .filter(CompanyChunk.orgnr == KNOWLEDGE_ORG, CompanyChunk.source == source)
        .first()
    ) is not None


def index_insurance_documents(db: Session) -> int:
    """Chunk and embed all InsuranceDocuments with extracted_text. Returns new chunk count."""
    total = 0
    docs = db.query(InsuranceDocument).filter(InsuranceDocument.extracted_text.isnot(None)).all()
    for doc in docs:
        source = f"doc_{doc.id}"
        if _already_indexed(source, db):
            continue
        header = (
            f"Dokument: {doc.title}\n"
            f"Forsikringsselskap: {doc.insurer or '-'}\n"
            f"År: {doc.year or '-'}\n"
            f"Kategori: {doc.category or '-'}\n\n"
        )
        count = _chunk_and_store(KNOWLEDGE_ORG, source, header + doc.extracted_text, db)
        total += count
        logger.info("Knowledge index: doc %d (%s) → %d chunks", doc.id, doc.title, count)
    return total


def index_video_transcripts(db: Session) -> int:
    """Download sections JSONs from blob and chunk transcript entries. Returns new chunk count."""
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
            source = f"video_{blob_name.replace('/', '_').replace('.', '_')}"
            if _already_indexed(source, db):
                continue
            data = svc.download_json(_VIDEOS_CONTAINER, blob_name)
            if not data:
                continue
            sections = data if isinstance(data, list) else (data.get("sections") or [])
            lines = []
            for sec in sections:
                title = sec.get("title", "")
                desc = sec.get("description", "")
                if title:
                    lines.append(f"\n## {title}")
                if desc:
                    lines.append(desc)
                for entry in (sec.get("entries") or []):
                    t = (entry.get("text") or "").strip()
                    if t:
                        lines.append(t)
            text = "\n".join(lines).strip()
            if not text:
                continue
            count = _chunk_and_store(KNOWLEDGE_ORG, source, text, db)
            total += count
            logger.info("Knowledge index: video %s → %d chunks", blob_name, count)
    except Exception as exc:
        logger.warning("Knowledge index: video indexing failed — %s", exc)
    return total


def index_all(db: Session) -> dict:
    """Index all knowledge sources. Returns counts of new chunks added."""
    docs_chunks = index_insurance_documents(db)
    video_chunks = index_video_transcripts(db)
    return {"docs_chunks": docs_chunks, "video_chunks": video_chunks}


def get_stats(db: Session) -> dict:
    """Return counts of indexed chunks per source type."""
    rows = db.query(CompanyChunk).filter(CompanyChunk.orgnr == KNOWLEDGE_ORG).all()
    doc_count = sum(1 for r in rows if r.source.startswith("doc_"))
    video_count = sum(1 for r in rows if r.source.startswith("video_"))
    return {"total": len(rows), "doc_chunks": doc_count, "video_chunks": video_count}
