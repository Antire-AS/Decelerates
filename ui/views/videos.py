"""Dedicated video player tab with chapter navigation."""
import base64
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
        # sections JSON uses start_seconds; fall back to other common field names
        start = (
            item.get("start_seconds")
            or item.get("start")
            or item.get("time")
            or item.get("timestamp")
            or item.get("startTime")
            or 0
        )
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


def _vtt_timestamp(s: float) -> str:
    h = int(s) // 3600
    m = (int(s) % 3600) // 60
    sec = int(s) % 60
    ms = int((s - int(s)) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d}.{ms:03d}"


def _build_vtt(raw_sections) -> str:
    """Build WebVTT subtitle content from sections entries list."""
    if not raw_sections or not isinstance(raw_sections, list):
        return ""
    all_entries = []
    for sec in raw_sections:
        for entry in (sec.get("entries") or []):
            secs = entry.get("seconds") or entry.get("start_seconds") or 0
            text = (entry.get("text") or "").strip()
            if text:
                all_entries.append({"s": float(secs), "text": text})
    if not all_entries:
        return ""
    all_entries.sort(key=lambda x: x["s"])
    lines = ["WEBVTT", ""]
    for i, e in enumerate(all_entries):
        end = all_entries[i + 1]["s"] if i + 1 < len(all_entries) else e["s"] + 5.0
        lines += [f"{_vtt_timestamp(e['s'])} --> {_vtt_timestamp(end)}", e["text"], ""]
    return "\n".join(lines)


def _render_video_player(vid: dict, compact: bool = False, autoplay_at: float | None = None) -> None:
    """Render an HTML5 video player card with chapter buttons and subtitle track."""
    blob_name = vid.get("blob_name", "")
    filename = vid.get("filename") or blob_name
    raw_sections = vid.get("sections") or []
    sections = _parse_sections(raw_sections)
    thumbnail_url = vid.get("thumbnail_url") or ""
    proxy_url = f"{API_BASE}/videos/stream?blob={urllib.parse.quote(blob_name)}"
    video_src = vid.get("video_url") or proxy_url

    # Build subtitle track from transcript entries
    vtt_content = _build_vtt(raw_sections if isinstance(raw_sections, list) else [])
    track_el = ""
    if vtt_content:
        vtt_b64 = base64.b64encode(vtt_content.encode("utf-8")).decode()
        track_el = (
            f'<track kind="subtitles" src="data:text/vtt;base64,{vtt_b64}" '
            'srclang="no" label="Norsk" default>'
        )

    poster = f'poster="{thumbnail_url}"' if thumbnail_url else ""
    chapter_btns = "".join(
        f'<button class="cpt" onclick="s({ch["start"]})">'
        f'<span class="ts">{_fmt_time(ch["start"])}</span>'
        f'<span class="ct">{ch["title"] or "–"}</span></button>'
        for ch in sections
    )
    chapters_block = (
        f'<div class="cpts"><div class="cpts-lbl">Kapitler ({len(sections)})</div>'
        f'<div class="cpts-grid">{chapter_btns}</div></div>'
        if sections else ""
    )
    max_h = "340px" if compact else "460px"
    # 2-column grid: ceil(n/2) rows × 32px per row
    import math
    grid_rows = math.ceil(len(sections) / 2) if sections else 0
    chapter_h = grid_rows * 34 + 36  # 34px/row + label
    height = (400 if compact else 510) + chapter_h if sections else (400 if compact else 500)
    css = (
        "*{margin:0;padding:0;box-sizing:border-box}"
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:transparent}"
        ".card{border:1px solid #D0CBC3;border-radius:8px;overflow:hidden;background:#fff}"
        ".hdr{background:#2C3E50;color:#D4C9B8;padding:10px 16px;font-size:.88rem;font-weight:700;"
        "overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
        f"video{{width:100%;display:block;background:#000;max-height:{max_h}}}"
        ".cpts{background:#F7F5F2;border-top:1px solid #E0DBD5;padding:10px 14px}"
        ".cpts-lbl{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#8A7F74;"
        "font-weight:700;margin-bottom:8px}"
        ".cpts-grid{display:grid;grid-template-columns:1fr 1fr;gap:4px}"
        ".cpt{display:flex;align-items:center;gap:7px;background:#fff;border:1px solid #D0CBC3;"
        "border-radius:5px;padding:5px 9px;cursor:pointer;font-size:.78rem;color:#3A4E60;"
        "transition:background .15s,border-color .15s;text-align:left;overflow:hidden}"
        ".cpt:hover{background:#E8F0FB;border-color:#4A6FA5;color:#1565C0}"
        ".ts{flex-shrink:0;font-size:.7rem;color:#8A7F74;background:#EDEAE6;padding:2px 5px;"
        "border-radius:3px;font-variant-numeric:tabular-nums}"
        ".ct{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
    )
    autoplay_js = (
        f"v.currentTime={autoplay_at};v.play();" if autoplay_at is not None else ""
    )
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><style>' + css + '</style></head><body>'
        '<div class="card">'
        f'<div class="hdr">{filename}</div>'
        f'<video id="vp" controls preload="metadata" {poster}>'
        f'<source src="{video_src}" type="video/mp4">'
        f'{track_el}'
        'Nettleseren din støtter ikke video-avspilling.</video>'
        + chapters_block
        + '</div><script>function s(t){var v=document.getElementById("vp");'
        f"v.currentTime=t;v.play();}}var v=document.getElementById('vp');"
        f"v.addEventListener('loadedmetadata',function(){{{autoplay_js}if(v.textTracks.length>0)v.textTracks[0].mode='showing';}});"
        "v.addEventListener('error',function(){"
        "var e=v.error,m=e?['','Ukjent feil','Nettverksfeil','Dekodefeil (ugyldig format)','Format ikke støttet'][e.code]||'Feil':(v.networkState===3?'Videofil ikke funnet':'Kan ikke spille av');"
        "v.outerHTML='<div style=\"padding:16px;color:#c0392b;font-size:.85rem\">⚠ Kan ikke spille av video: '+m+'.<br>Videofilen kan mangle faststart-flagg (moov atom). Kjør: <code>ffmpeg -i input.mp4 -c copy -movflags +faststart output.mp4</code></div>';});"
        "</script></body></html>"
    )
    st.components.v1.html(html, height=height)


def _video_description(raw_sections) -> str:
    """Extract a short description from the first section's description field."""
    if not isinstance(raw_sections, list) or not raw_sections:
        return ""
    desc = raw_sections[0].get("description") or ""
    return desc[:80] + ("…" if len(desc) > 80 else "")


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
        st.markdown("#### Kursvideoer")
        for i, vid in enumerate(videos):
            raw_label = vid.get("filename") or vid.get("blob_name", f"Video {i + 1}")
            # Strip extension and truncate
            clean = raw_label.rsplit(".", 1)[0] if "." in raw_label else raw_label
            title = clean[:42] + "…" if len(clean) > 44 else clean
            raw_sections = vid.get("sections") or []
            sections = _parse_sections(raw_sections)
            ch = len(sections)
            is_active = i == st.session_state["selected_video_idx"]

            bg = "#EEF4FC" if is_active else "#FAFAF8"
            border = "3px solid #4A6FA5" if is_active else "3px solid #E8E3DC"
            title_w = "700" if is_active else "500"
            title_c = "#1A2E40" if is_active else "#3A4E60"
            st.markdown(
                f"<div style='background:{bg};border-left:{border};border-radius:6px;"
                f"padding:9px 12px;margin-bottom:2px;cursor:pointer'>"
                f"<div style='font-size:13px;font-weight:{title_w};color:{title_c};"
                f"line-height:1.35'>{title}</div>"
                + (f"<div style='font-size:10px;color:#8A7F74;margin-top:3px'>"
                   f"{'▶ ' if is_active else ''}{ch} kapitler</div>" if ch else "")
                + "</div>",
                unsafe_allow_html=True,
            )
            if not is_active:
                if st.button("Spill av", key=f"vid_nav_{i}", use_container_width=True):
                    st.session_state["selected_video_idx"] = i
                    st.rerun()
            else:
                st.button("▶ Spiller nå", key=f"vid_nav_{i}", use_container_width=True,
                          disabled=True, type="primary")

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
        deeplink = st.session_state.pop("video_deeplink", None)
        if deeplink:
            target_name = deeplink["display_name"]
            for i, v in enumerate(videos):
                if v.get("filename") == target_name:
                    st.session_state["selected_video_idx"] = i
                    break
        idx = min(st.session_state["selected_video_idx"], len(videos) - 1)
        autoplay_at = float(deeplink["start_seconds"]) if deeplink else None
        _render_video_player(videos[idx], compact=False, autoplay_at=autoplay_at)
