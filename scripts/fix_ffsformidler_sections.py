"""One-time script: trim ffsformidler_sections.json to chapters within the 32:04 video.

The sections JSON was generated from a longer (~52 min) recording.
The uploaded video is the edited 32:04 version, so chapters 6–12 (39:16+) don't exist.

Run with:
    uv run --env-file .env python scripts/fix_ffsformidler_sections.py

Requires the same Azure env vars as the API (AZURE_BLOB_ENDPOINT).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api.services.blob_storage import BlobStorageService

CONTAINER = os.getenv("AZURE_VIDEO_CONTAINER", "transksrt")
SECTIONS_BLOB = "ffsformidler_sections.json"
VIDEO_DURATION_S = 32 * 60 + 4  # 32:04 = 1924 seconds


def main():
    svc = BlobStorageService()
    if not svc.is_configured():
        print("ERROR: BlobStorageService not configured — set AZURE_BLOB_ENDPOINT.")
        sys.exit(1)

    print(f"Downloading {SECTIONS_BLOB} from container '{CONTAINER}'...")
    data = svc.download_json(CONTAINER, SECTIONS_BLOB)
    if data is None:
        print(f"ERROR: Could not download {SECTIONS_BLOB}")
        sys.exit(1)

    chapters = data if isinstance(data, list) else data.get("chapters", [])
    before = len(chapters)
    trimmed = [ch for ch in chapters if ch.get("start_seconds", 0) <= VIDEO_DURATION_S]
    after = len(trimmed)

    print(f"Chapters before: {before}, after trimming to ≤{VIDEO_DURATION_S}s: {after}")
    for ch in trimmed:
        ts = ch.get("start_seconds", 0)
        print(f"  {ts//60}:{str(ts%60).zfill(2)}  {ch.get('title','')}")

    if before == after:
        print("No chapters removed — nothing to fix.")
        return

    corrected = trimmed if isinstance(data, list) else {**data, "chapters": trimmed}
    corrected_bytes = json.dumps(corrected, ensure_ascii=False, indent=2).encode("utf-8")

    print(f"\nUploading corrected {SECTIONS_BLOB} ({len(corrected_bytes)} bytes)...")
    svc.upload(CONTAINER, SECTIONS_BLOB, corrected_bytes)
    print("Done. Reload the Videoer tab to verify.")


if __name__ == "__main__":
    main()
