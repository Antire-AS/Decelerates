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

# Maps MP4 file stem → (sections_json_prefix, display_name)
_VIDEO_SECTIONS_MAP = {
    "ffs080524": ("ffsformidler", "Forsikringsformidling i praksis"),
    "ffs100624": ("ffskunde", "Kundeorientering og rådgivning"),
    "ffs220824": ("ffslære", "Fagkunnskap og regelverk"),
    "ffs290824": ("ffspraktisk", "Praktisk forsikringsrådgivning"),
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


@router.get("/videos")
def list_videos() -> list:
    """List MP4 videos with chapter metadata. Blobs may be in subdirectories."""
    svc = BlobStorageService()
    if not svc.is_configured():
        return []
    all_blobs = set(svc.list_blobs(_VIDEOS_CONTAINER))
    mp4s = sorted(b for b in all_blobs if b.lower().endswith(".mp4"))
    results = []
    for mp4 in mp4s:
        directory = posixpath.dirname(mp4)
        fname = posixpath.basename(mp4)[:-4]           # e.g. ffs080524_subs
        fname_clean = fname.removesuffix("_subs")      # e.g. ffs080524

        sections_prefix, display_name = _VIDEO_SECTIONS_MAP.get(
            fname_clean, (fname_clean, fname_clean.replace("_", " "))
        )

        sections = None
        base = mp4[:-4]
        candidates = [
            f"{directory}/{sections_prefix}_sections.json",
            f"{directory}/{sections_prefix}_timeline.json",
            f"{base}.json", f"{base}_sections.json",
        ]
        for cand in candidates:
            if cand in all_blobs:
                sections = svc.download_json(_VIDEOS_CONTAINER, cand)
                break

        thumb_candidates = [
            f"{directory}/thumbnails/{fname}_sprite.jpg",
            f"{directory}/thumbnails/{fname}.jpg",
            f"{base}.jpg",
        ]
        thumb_blob = next((c for c in thumb_candidates if c in all_blobs), None)
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
