"""
Video streaming and thumbnail endpoints for FFS course videos.
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

_VIDEO_DIR = Path(__file__).parent.parent.parent / "transksrt" / "whisper_input" / "Videosubtime"
_THUMB_DIR = _VIDEO_DIR / "thumbnails"

# Allowed filenames (whitelist to prevent path traversal)
_ALLOWED_VIDEOS = {
    "ffs080524_subs.mp4",
    "ffs100624_subs.mp4",
    "ffs220824_subs.mp4",
    "ffs290824_subs.mp4",
}


@router.get("/video/{filename}")
def stream_video(filename: str):
    """Stream an FFS course video with range-request support."""
    if filename not in _ALLOWED_VIDEOS:
        raise HTTPException(status_code=404, detail="Video not found")
    path = _VIDEO_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video file missing on disk")
    return FileResponse(
        str(path),
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/video/{filename}/sprite")
def video_sprite(filename: str):
    """Return the pre-generated thumbnail sprite sheet for a video."""
    stem = filename.replace(".mp4", "")
    sprite_path = _THUMB_DIR / f"{stem}_sprite.jpg"
    if not sprite_path.exists():
        raise HTTPException(status_code=404, detail="Sprite not generated yet")
    return FileResponse(str(sprite_path), media_type="image/jpeg")
