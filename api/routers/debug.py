"""Debug/diagnostic endpoint — blob storage health, DB state, video status."""

import os

from fastapi import APIRouter

router = APIRouter()


def _has_mp4_faststart(data: bytes):
    pos = 0
    while pos + 8 <= len(data):
        size = int.from_bytes(data[pos : pos + 4], "big")
        box_type = data[pos + 4 : pos + 8].decode("ascii", errors="replace")
        if box_type == "moov":
            return True
        if box_type == "mdat":
            return False
        if size < 8 or pos + size > len(data):
            break
        pos += size
    return None


def _debug_blob_status(svc) -> dict:
    try:
        blobs = svc.list_blobs("transksrt")
        return {"count": len(blobs), "sample": blobs[:5], "error": None}
    except Exception as exc:
        return {"count": None, "sample": [], "error": str(exc)}


def _debug_db_status() -> dict:
    from api.db import engine
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar()
            rows = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' ORDER BY table_name"
                )
            ).fetchall()
            tags_col = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='insurance_documents' AND column_name='tags')"
                )
            ).scalar()
        return {
            "alembic_version": version,
            "alembic_error": None,
            "public_tables": [r[0] for r in rows],
            "tags_column_exists": tags_col,
        }
    except Exception as exc:
        return {
            "alembic_version": None,
            "alembic_error": str(exc),
            "public_tables": [],
            "tags_column_exists": None,
        }


def _debug_video_status(svc) -> tuple[dict, bool | None]:
    if not svc._client:
        return {}, None
    video_info: dict = {}
    sas_url_works: bool | None = None
    try:
        mp4_blobs = [b for b in svc.list_blobs("transksrt") if b.endswith(".mp4")]
    except Exception:
        return {}, None
    for mp4 in mp4_blobs:
        try:
            chunks = svc.stream_range("transksrt", mp4, offset=0, length=256)
            header = b"".join(chunks) if chunks else b""
            sas_url = svc.generate_sas_url("transksrt", mp4, hours=1)
            if sas_url_works is None:
                sas_url_works = sas_url is not None
            video_info[mp4] = {
                "size_mb": round((svc.get_blob_size("transksrt", mp4) or 0) / 1e6),
                "faststart": _has_mp4_faststart(header),
                "sas_url_generated": sas_url is not None,
            }
        except Exception as exc:
            video_info[mp4] = {"error": str(exc)}
    return video_info, sas_url_works


@router.get("/debug/status")
def debug_status() -> dict:
    from api.services.blob_storage import BlobStorageService

    azure_client_id = os.getenv("AZURE_CLIENT_ID", "")
    azure_blob_endpoint = os.getenv("AZURE_BLOB_ENDPOINT", "")
    svc = BlobStorageService()
    blob = _debug_blob_status(svc)
    db_info = _debug_db_status()
    video_info, sas_url_works = _debug_video_status(svc)
    return {
        "azure_client_id_set": bool(azure_client_id),
        "azure_client_id_prefix": azure_client_id[:8] + "..."
        if azure_client_id
        else None,
        "azure_blob_endpoint_set": bool(azure_blob_endpoint),
        "blob_client_init": svc._client is not None,
        "blob_count": blob["count"],
        "blob_sample": blob["sample"],
        "blob_error": blob["error"],
        "sas_url_works": sas_url_works,
        "video_info": video_info,
        "alembic_version": db_info["alembic_version"],
        "alembic_error": db_info["alembic_error"],
        "tags_column_exists": db_info["tags_column_exists"],
        "public_tables": db_info["public_tables"],
    }
