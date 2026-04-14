"""Video management endpoints — upload, list, and stream video blobs."""
import base64
import os
import posixpath
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Request
from fastapi.responses import StreamingResponse

from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.services.audit import log_audit
from api.services.blob_storage import BlobStorageService

_ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo"}
_MAX_VIDEO_BYTES = 500 * 1024 * 1024  # 500 MB
_VIDEOS_CONTAINER = os.getenv("AZURE_VIDEO_CONTAINER", "transksrt")

# Maps MP4 file stem → (sections_json_prefix, display_name, max_seconds|None)
# max_seconds trims chapters whose start_seconds exceed the actual video duration.
# Display names derived from descriptive filenames uploaded to Azure:
#   ffs080524forsikringsformidlingipraksis_fast.mp4  → 32:04 = 1924s
#   ffs100624møtemedkundenbehovsanalysogrådgivning_fast.mp4
#   ffs220824forsikringsmeglerrollen-hvakanvilære_fast.mp4
#   ffs290824_fast.mp4
_VIDEO_SECTIONS_MAP = {
    "ffs080524": ("ffsformidler", "Forsikringsformidling i praksis",              None),
    "ffs100624": ("ffskunde",     "Møte med kunden, behovsanalyse og rådgivning", None),
    "ffs220824": ("ffslære",      "Forsikringsmeglerrollen – hva kan vi lære?",   None),
    "ffs290824": ("ffspraktisk",  "Praktisk forsikringsrådgivning",               None),
}

router = APIRouter()


def _vtt_timestamp(s: float) -> str:
    h = int(s) // 3600
    m = (int(s) % 3600) // 60
    sec = int(s) % 60
    ms = int((s - int(s)) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d}.{ms:03d}"


def _build_vtt_data_uri(sections: list) -> str | None:
    """Build a WebVTT data URI from sections that contain transcript entries."""
    entries = []
    for sec in sections:
        for e in sec.get("entries") or []:
            t = (e.get("text") or "").strip()
            s = float(e.get("seconds") or e.get("start_seconds") or 0)
            if t:
                entries.append({"s": s, "text": t})
    if not entries:
        return None
    entries.sort(key=lambda x: x["s"])
    lines = ["WEBVTT", ""]
    for i, e in enumerate(entries):
        end = entries[i + 1]["s"] if i + 1 < len(entries) else e["s"] + 5.0
        lines += [f"{_vtt_timestamp(e['s'])} --> {_vtt_timestamp(end)}", e["text"], ""]
    vtt = "\n".join(lines)
    b64 = base64.b64encode(vtt.encode("utf-8")).decode()
    return f"data:text/vtt;base64,{b64}"


@router.post("/videos/upload")
async def upload_video(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    """Upload a video file to Azure Blob Storage."""
    content_type = file.content_type or ""
    if content_type not in _ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail="Filtype ikke støttet. Bruk .mp4, .mov eller .avi")
    video_bytes = await file.read()
    if len(video_bytes) > _MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="Filen er for stor. Maks 500 MB.")
    blob_name = f"{uuid.uuid4()}_{file.filename}"
    svc = BlobStorageService()
    if not svc.is_configured():
        raise HTTPException(status_code=503, detail="Blob Storage ikke konfigurert (AZURE_BLOB_ENDPOINT mangler)")
    url = svc.upload(_VIDEOS_CONTAINER, blob_name, video_bytes)
    if not url:
        raise HTTPException(status_code=502, detail="Opplasting til Blob Storage feilet")
    log_audit(db, "video.upload", detail={"filename": file.filename, "blob_name": blob_name})
    return {"blob_name": blob_name, "url": url, "filename": file.filename}


def _sections_key(fname: str) -> str:
    """Map a filename stem to a _VIDEO_SECTIONS_MAP key by prefix match."""
    clean = fname.removesuffix("_subs").removesuffix("_fast")
    return next((k for k in _VIDEO_SECTIONS_MAP if clean == k or clean.startswith(k)), clean)


@router.get("/videos")
def list_videos() -> list:
    """List MP4 videos with chapter metadata, preferring _fast (faststart) over _subs."""
    svc = BlobStorageService()
    if not svc.is_configured():
        return []
    all_blobs = set(svc.list_blobs(_VIDEOS_CONTAINER))
    mp4s = sorted(b for b in all_blobs if b.lower().endswith(".mp4"))

    # De-duplicate per sections key: prefer _fast over _subs; shortest name wins among ties
    best: dict[str, str] = {}
    for mp4 in mp4s:
        fname = posixpath.basename(mp4)[:-4]
        key = _sections_key(fname)
        is_fast = "_fast" in fname
        existing = best.get(key)
        if existing is None:
            best[key] = mp4
        else:
            existing_fast = "_fast" in posixpath.basename(existing)
            if is_fast and not existing_fast:
                best[key] = mp4
            elif is_fast == existing_fast and len(mp4) < len(existing):
                best[key] = mp4

    results = []
    for key in sorted(best):
        mp4 = best[key]
        directory = posixpath.dirname(mp4)
        fname = posixpath.basename(mp4)[:-4]
        meta = _VIDEO_SECTIONS_MAP.get(key, (key, key.replace("_", " "), None))
        sections_prefix, display_name, max_seconds = meta
        sections = None
        base = mp4[:-4]
        for cand in [
            f"{directory}/{sections_prefix}_sections.json",
            f"{directory}/{sections_prefix}_timeline.json",
            f"{base}.json", f"{base}_sections.json",
        ]:
            if cand in all_blobs:
                sections = svc.download_json(_VIDEOS_CONTAINER, cand)
                if max_seconds is not None and isinstance(sections, list):
                    sections = [ch for ch in sections if ch.get("start_seconds", 0) <= max_seconds]
                break

        thumb_blob = next((
            c for c in [
                f"{directory}/thumbnails/{fname}_sprite.jpg",
                f"{directory}/thumbnails/{fname}.jpg",
                f"{base}.jpg",
            ] if c in all_blobs
        ), None)
        thumbnail_url = svc.generate_sas_url(_VIDEOS_CONTAINER, thumb_blob) if thumb_blob else None
        video_url = svc.generate_sas_url(_VIDEOS_CONTAINER, mp4, hours=4)
        subtitle_url = _build_vtt_data_uri(sections) if isinstance(sections, list) else None
        results.append({
            "blob_name": mp4,
            "filename": display_name,
            "sections": sections,
            "thumbnail_url": thumbnail_url,
            "video_url": video_url,
            "subtitle_url": subtitle_url,
        })
    return results


@router.get("/videos/stream")
async def stream_video(blob: str, request: Request):
    """Stream a video blob with HTTP range request support."""
    svc = BlobStorageService()
    if not svc.is_configured():
        raise HTTPException(status_code=503, detail="Blob Storage ikke konfigurert")
    file_size = svc.get_blob_size(_VIDEOS_CONTAINER, blob)
    if file_size is None:
        raise HTTPException(status_code=404, detail="Video ikke funnet")
    range_header = request.headers.get("range")
    if range_header:
        m = re.match(r"bytes=(\d*)-(\d*)", range_header)
        start = int(m.group(1)) if m and m.group(1) else 0
        end = int(m.group(2)) if m and m.group(2) else file_size - 1
        length = end - start + 1
        chunks = svc.stream_range(_VIDEOS_CONTAINER, blob, offset=start, length=length)
        if chunks is None:
            raise HTTPException(status_code=502)
        return StreamingResponse(
            chunks, status_code=206, media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
            },
        )
    chunks = svc.stream_range(_VIDEOS_CONTAINER, blob)
    if chunks is None:
        raise HTTPException(status_code=502)
    return StreamingResponse(
        chunks, media_type="video/mp4",
        headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
    )
