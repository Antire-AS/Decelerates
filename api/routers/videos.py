"""Video management endpoints — upload, list, and stream video blobs."""
import os
import posixpath
import re
import uuid

from fastapi import APIRouter, HTTPException, File, UploadFile, Request
from fastapi.responses import StreamingResponse

from api.services.blob_storage import BlobStorageService

_ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo"}
_VIDEOS_CONTAINER = os.getenv("AZURE_VIDEO_CONTAINER", "transksrt")

# Maps MP4 file stem → (sections_json_prefix, display_name, max_seconds|None)
# max_seconds trims chapters whose start_seconds exceed the actual video duration.
# Display names derived from descriptive filenames uploaded to Azure:
#   ffs080524forsikringsformidlingipraksis_fast.mp4  → 32:04 = 1924s
#   ffs100624møtemedkundenbehovsanalysogrådgivning_fast.mp4
#   ffs220824forsikringsmeglerrollen-hvakanvilære_fast.mp4
#   ffs290824_fast.mp4
_VIDEO_SECTIONS_MAP = {
    #                    sections_prefix   display_name                                      max_seconds
    # max_seconds = actual video duration; trims chapters whose timestamps exceed the video.
    # ffs080524: 32:04 — sections from unedited ~52 min recording
    # ffs220824: 45:22 — sections from longer ~89 min recording
    # ffs290824: 122:20 — sections from longer ~143 min recording
    # ffs100624: 99:37 — sections file only covers first 14 min (needs regeneration)
    "ffs080524": ("ffsformidler", "Forsikringsformidling i praksis",              1924),  # 32:04
    "ffs100624": ("ffskunde",     "Møte med kunden, behovsanalyse og rådgivning", None),  # incomplete sections, no trim
    "ffs220824": ("ffslære",      "Forsikringsmeglerrollen – hva kan vi lære?",   2722),  # 45:22
    "ffs290824": ("ffspraktisk",  "Praktisk forsikringsrådgivning",               7340),  # 122:20
}

router = APIRouter()


@router.post("/videos/upload")
async def upload_video(file: UploadFile = File(...)) -> dict:
    """Upload a video file to Azure Blob Storage."""
    content_type = file.content_type or ""
    if content_type not in _ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail="Filtype ikke støttet. Bruk .mp4, .mov eller .avi")
    video_bytes = await file.read()
    blob_name = f"{uuid.uuid4()}_{file.filename}"
    svc = BlobStorageService()
    if not svc.is_configured():
        raise HTTPException(status_code=503, detail="Blob Storage ikke konfigurert (AZURE_BLOB_ENDPOINT mangler)")
    url = svc.upload(_VIDEOS_CONTAINER, blob_name, video_bytes)
    if not url:
        raise HTTPException(status_code=502, detail="Opplasting til Blob Storage feilet")
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
        results.append({
            "blob_name": mp4,
            "filename": display_name,
            "sections": sections,
            "thumbnail_url": thumbnail_url,
            "video_url": video_url,
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
