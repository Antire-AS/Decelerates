"""
FFS Autorisasjonskurs — video player with chapter navigation and transcript search.
"""
import base64
import json
import os

import streamlit as st
import streamlit.components.v1 as components

_VIDEO_BASE = os.path.join(
    os.path.dirname(__file__), "..", "..", "transksrt", "whisper_input", "Videosubtime"
)

_MODULES = {
    "Forsikringsmegling i praksis": {
        "video":    os.path.join(_VIDEO_BASE, "ffs080524_subs.mp4"),
        "timeline": os.path.join(_VIDEO_BASE, "ffsformidler_timeline.json"),
        "sections": os.path.join(_VIDEO_BASE, "ffsformidler_sections.json"),
    },
    "Behovsanalyse": {
        "video":    os.path.join(_VIDEO_BASE, "ffs100624_subs.mp4"),
        "timeline": os.path.join(_VIDEO_BASE, "ffskunde_timeline.json"),
        "sections": os.path.join(_VIDEO_BASE, "ffskunde_sections.json"),
    },
    "Juridisk ansvar og etikk": {
        "video":    os.path.join(_VIDEO_BASE, "ffs220824_subs.mp4"),
        "timeline": os.path.join(_VIDEO_BASE, "ffslære_timeline.json"),
        "sections": os.path.join(_VIDEO_BASE, "ffslære_sections.json"),
    },
    "Praktiske øvelser": {
        "video":    os.path.join(_VIDEO_BASE, "ffs290824_subs.mp4"),
        "timeline": os.path.join(_VIDEO_BASE, "ffspraktisk_timeline.json"),
        "sections": os.path.join(_VIDEO_BASE, "ffspraktisk_sections.json"),
    },
}

_VID_STEM = {
    "Forsikringsmegling i praksis": "ffs080524_subs",
    "Behovsanalyse":                "ffs100624_subs",
    "Juridisk ansvar og etikk":     "ffs220824_subs",
    "Praktiske øvelser":            "ffs290824_subs",
}

_COLORS = [
    "#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#1abc9c",
    "#3498db", "#9b59b6", "#e91e63", "#00bcd4", "#8bc34a",
    "#ff5722", "#795548", "#607d8b", "#cddc39", "#ff9800",
]


def _load_json(path: str) -> list:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _sprite_b64(stem: str) -> str:
    sprite_path = os.path.join(_VIDEO_BASE, "thumbnails", f"{stem}_sprite.jpg")
    try:
        with open(sprite_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""


def _chapter_bar_html(sections: list, timeline: list, sprite: str) -> str:
    total_s = max((e.get("seconds", 0) for e in timeline), default=0) or 1
    segs = ""
    for si, sec in enumerate(sections):
        color = _COLORS[si % len(_COLORS)]
        s0 = sec.get("start_seconds", 0)
        s1 = sections[si + 1].get("start_seconds", total_s) if si + 1 < len(sections) else total_s
        left = s0 / total_s * 100
        width = (s1 - s0) / total_s * 100
        title = sec.get("title", "")
        desc = sec.get("description", "")[:60]
        tstr = sec.get("start_time", "")
        fidx = s0 // 20
        fcol = fidx % 10
        frow = fidx // 10
        spos = f"-{fcol * 160}px -{frow * 90}px"
        thumb = (
            f'<div class="thumb" style="background-image:url(data:image/jpeg;base64,{sprite});'
            f'background-size:1600px auto;background-position:{spos}"></div>'
        ) if sprite else '<div class="thumb"></div>'
        segs += (
            f'<div class="seg" style="left:{left:.3f}%;width:{width:.3f}%;background:{color}">'
            f'<div class="pop">{thumb}'
            f'<div class="pt">{title}</div>'
            f'<div class="pd">{desc}</div>'
            f'<div class="ps">{tstr}</div>'
            f'</div></div>\n'
        )

    css = (
        "*{box-sizing:border-box;margin:0;padding:0}"
        "body{background:#1a1a1a;overflow:hidden}"
        ".wrap{position:relative;height:50px;background:#1a1a1a;display:flex;align-items:flex-end;padding-bottom:4px}"
        ".inner{position:relative;left:0;right:0;bottom:4px;height:10px;width:100%;}"
        ".seg{position:absolute;top:0;height:100%;opacity:.8;transition:height .12s,opacity .12s;"
        "border-right:2px solid #1a1a1a;cursor:pointer}"
        ".seg:hover{opacity:1;height:150%;}"
        ".pop{display:none;position:absolute;bottom:calc(100% + 14px);left:50%;transform:translateX(-50%);"
        "flex-direction:column;align-items:center;background:rgba(0,0,0,.92);border:1px solid #444;"
        "border-radius:5px;padding:6px 8px;min-width:160px;max-width:190px;z-index:99;"
        "filter:drop-shadow(0 4px 12px rgba(0,0,0,.8));}"
        ".pop::after{content:'';position:absolute;top:100%;left:50%;transform:translateX(-50%);"
        "border:6px solid transparent;border-top-color:rgba(0,0,0,.92)}"
        ".seg:hover .pop{display:flex}"
        ".thumb{width:160px;height:90px;background:#222;background-repeat:no-repeat;border-radius:3px;flex-shrink:0}"
        ".pt{color:#fff;font-size:12px;font-weight:700;margin-top:5px;text-align:center;"
        "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:175px}"
        ".pd{color:#999;font-size:10px;margin-top:2px;text-align:center;"
        "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:175px}"
        ".ps{color:#f44;font-size:11px;margin-top:3px;font-family:monospace}"
    )
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{css}</style></head><body>"
        "<div class='wrap'><div class='inner'>"
        + segs +
        "</div></div></body></html>"
    )


def render_kurs_tab():
    if "kurs_module" not in st.session_state:
        st.session_state["kurs_module"] = list(_MODULES.keys())[0]
    if "kurs_seek" not in st.session_state:
        st.session_state["kurs_seek"] = 0

    st.subheader("FFS Autorisasjonskurs — Videoer")

    module_keys = list(_MODULES.keys())
    sel_module = st.radio(
        "Modul",
        module_keys,
        index=module_keys.index(st.session_state["kurs_module"]),
        horizontal=True,
        key="kurs_module_radio",
    )
    if sel_module != st.session_state["kurs_module"]:
        st.session_state["kurs_module"] = sel_module
        st.session_state["kurs_seek"] = 0
        st.rerun()

    mod = _MODULES[sel_module]
    sections = _load_json(mod["sections"])
    timeline = _load_json(mod["timeline"])
    stem = _VID_STEM[sel_module]
    vid_path = os.path.join(_VIDEO_BASE, stem + ".mp4")
    sprite = _sprite_b64(stem)
    seek = st.session_state.get("kurs_seek", 0)

    col_video, col_catalog = st.columns([3, 2])

    with col_video:
        if os.path.exists(vid_path):
            st.video(vid_path, start_time=seek)
        else:
            st.error(f"Videofil ikke funnet: {vid_path}")
        if sections:
            components.html(_chapter_bar_html(sections, timeline, sprite), height=55)

    with col_catalog:
        filt = st.text_input(
            "Søk i transkripsjoner",
            placeholder="F.eks. «premie», «ansvar», «skade»...",
            key="kurs_filter",
        )

        if filt:
            hits = [e for e in timeline if filt.lower() in e.get("text", "").lower()]
            st.caption(f"{len(hits)} treff for «{filt}»")
            for entry in hits:
                secs = entry.get("seconds", 0)
                time_str = entry.get("time", "")
                text = entry.get("text", "")
                short = text[:80] + "…" if len(text) > 80 else text
                if st.button(
                    f"▶ {time_str}  {short}",
                    key=f"ksearch_{secs}_{hash(filt)}",
                    use_container_width=True,
                ):
                    st.session_state["kurs_seek"] = secs
                    st.rerun()

        elif sections:
            st.markdown("**Kapitler**")
            for si, sec in enumerate(sections):
                sec_title = sec.get("title", f"Seksjon {si + 1}")
                sec_start = sec.get("start_seconds", 0)
                sec_time = sec.get("start_time", "")
                sec_desc = sec.get("description", "")
                sec_entries = sec.get("entries", [])
                sec_key = f"{sel_module}_{si}"

                with st.expander(f"**{sec_time}** — {sec_title}", expanded=False):
                    if sec_desc:
                        st.caption(sec_desc)
                    if st.button(
                        f"▶ Spill fra {sec_time}",
                        key=f"ksec_{sec_key}_play",
                        type="primary",
                        use_container_width=True,
                    ):
                        st.session_state["kurs_seek"] = sec_start
                        st.rerun()

                    step = max(1, len(sec_entries) // 12)
                    for entry in sec_entries[::step]:
                        secs = entry.get("seconds", 0)
                        time_str = entry.get("time", "")
                        text = entry.get("text", "")
                        short = text[:65] + "…" if len(text) > 65 else text
                        if st.button(
                            f"{time_str}  {short}",
                            key=f"kentry_{sec_key}_{secs}",
                            use_container_width=True,
                        ):
                            st.session_state["kurs_seek"] = secs
                            st.rerun()

        elif timeline:
            st.markdown("**Tidslinje**")
            step = max(1, len(timeline) // 60)
            for entry in timeline[::step]:
                secs = entry.get("seconds", 0)
                time_str = entry.get("time", "")
                text = entry.get("text", "")
                short = text[:70] + "…" if len(text) > 70 else text
                if st.button(
                    f"▶ {time_str}  {short}",
                    key=f"kflat_{secs}_{sel_module}",
                    use_container_width=True,
                ):
                    st.session_state["kurs_seek"] = secs
                    st.rerun()
        else:
            st.info("Ingen tidslinje tilgjengelig for denne modulen.")
