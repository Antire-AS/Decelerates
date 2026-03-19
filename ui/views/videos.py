"""Dedicated video player tab with chapter navigation."""
import urllib.parse

import requests
import streamlit as st

from ui.config import API_BASE


def _parse_sections(raw) -> list:
    """Normalise various JSON section formats to [{title, start}]."""
    if not raw:
        return []
    if isinstance(raw, dict):
        raw = raw.get("sections") or raw.get("chapters") or raw.get("items") or []
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("label") or item.get("name") or item.get("text") or "")
        start = item.get("start") or item.get("time") or item.get("timestamp") or item.get("startTime") or 0
        if isinstance(start, str):
            parts = start.split(":")
            try:
                if len(parts) == 2:
                    start = int(parts[0]) * 60 + float(parts[1])
                elif len(parts) == 3:
                    start = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                else:
                    start = float(start)
            except (ValueError, IndexError):
                start = 0.0
        out.append({"title": title, "start": float(start)})
    return sorted(out, key=lambda x: x["start"])


def _fmt_time(seconds: float) -> str:
    s = int(seconds)
    h, m = s // 3600, (s % 3600) // 60
    return f"{h}:{m:02d}:{s % 60:02d}" if h else f"{m}:{s % 60:02d}"


def _render_video_player(vid: dict, compact: bool = False) -> None:
    """Render an HTML5 video player card with chapter buttons."""
    blob_name = vid.get("blob_name", "")
    filename = vid.get("filename") or blob_name
    sections = _parse_sections(vid.get("sections"))
    thumbnail_url = vid.get("thumbnail_url") or ""
    proxy_url = f"{API_BASE}/videos/stream?blob={urllib.parse.quote(blob_name)}"

    poster = f'poster="{thumbnail_url}"' if thumbnail_url else ""
    chapter_btns = "".join(
        f'<button class="cpt" onclick="s({ch["start"]})">'
        f'<span class="ts">{_fmt_time(ch["start"])}</span>{ch["title"] or "–"}</button>'
        for ch in sections
    )
    chapters_block = (
        f'<div class="cpts"><div class="cpts-lbl">Kapitler ({len(sections)})</div>{chapter_btns}</div>'
        if sections else ""
    )
    max_h = "340px" if compact else "460px"
    height = (430 if compact else 540) + max(0, (len(sections) - 3) * 28) if sections else (400 if compact else 500)
    css = (
        "*{margin:0;padding:0;box-sizing:border-box}"
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:transparent}"
        ".card{border:1px solid #D0CBC3;border-radius:8px;overflow:hidden;background:#fff}"
        ".hdr{background:#2C3E50;color:#D4C9B8;padding:10px 16px;font-size:.88rem;font-weight:700;"
        "overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        f"video{{width:100%;display:block;background:#000;max-height:{max_h}}}"
        ".cpts{background:#F7F5F2;border-top:1px solid #E0DBD5;padding:10px 12px}"
        ".cpts-lbl{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#8A7F74;"
        "font-weight:700;margin-bottom:6px}"
        ".cpt{display:inline-flex;align-items:center;gap:5px;background:#fff;border:1px solid #D0CBC3;"
        "border-radius:5px;padding:4px 9px;margin:2px;cursor:pointer;font-size:.78rem;color:#3A4E60;"
        "transition:background .15s,border-color .15s}"
        ".cpt:hover{background:#E8F0FB;border-color:#4A6FA5;color:#1565C0}"
        ".ts{font-size:.7rem;color:#8A7F74;background:#EDEAE6;padding:1px 4px;border-radius:3px;"
        "font-variant-numeric:tabular-nums}"
    )
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><style>' + css + '</style></head><body>'
        '<div class="card">'
        f'<div class="hdr">{filename}</div>'
        f'<video id="vp" controls preload="metadata" {poster}>'
        f'<source src="{proxy_url}" type="video/mp4">'
        'Nettleseren din støtter ikke video-avspilling.</video>'
        + chapters_block
        + '</div><script>function s(t){var v=document.getElementById("vp");'
        "v.currentTime=t;v.play();}</script></body></html>"
    )
    st.components.v1.html(html, height=height)


def render_videos_tab() -> None:
    if "selected_video_idx" not in st.session_state:
        st.session_state["selected_video_idx"] = 0

    try:
        resp = requests.get(f"{API_BASE}/videos", timeout=15)
        videos = resp.json() if resp.ok else []
    except Exception:
        videos = []

    if not videos:
        st.info("Ingen videoer tilgjengelig. Last opp via Dokumenter → Videoer.")
        return

    nav_col, player_col = st.columns([1, 3], gap="medium")

    with nav_col:
        st.markdown("#### Velg video")
        for i, vid in enumerate(videos):
            label = vid.get("filename") or vid.get("blob_name", f"Video {i + 1}")
            has_chapters = bool(vid.get("sections"))
            suffix = "  📑" if has_chapters else ""
            is_active = i == st.session_state["selected_video_idx"]
            btn_type = "primary" if is_active else "secondary"
            if st.button(f"{label}{suffix}", key=f"vid_nav_{i}", type=btn_type, use_container_width=True):
                st.session_state["selected_video_idx"] = i
                st.rerun()

        st.markdown("---")
        with st.expander("Last opp video", expanded=False):
            vid_file = st.file_uploader("Velg videofil (.mp4, .mov, .avi)", type=["mp4", "mov", "avi"], key="vid_upload_tab")
            if st.button("Last opp", disabled=vid_file is None, key="vid_upload_btn") and vid_file is not None:
                try:
                    r = requests.post(
                        f"{API_BASE}/videos/upload",
                        files={"file": (vid_file.name, vid_file.getvalue(), vid_file.type)},
                        timeout=120,
                    )
                    if r.ok:
                        st.success(f"Lastet opp: {r.json().get('filename')}")
                        st.rerun()
                    else:
                        st.error(r.text)
                except Exception as e:
                    st.error(str(e))

    with player_col:
        idx = min(st.session_state["selected_video_idx"], len(videos) - 1)
        _render_video_player(videos[idx], compact=False)
