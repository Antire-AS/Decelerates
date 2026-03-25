"""Knowledge base tab: AI chat over videos and insurance documents, plus search and management."""
import re

import pandas as pd
import requests
import streamlit as st

from ui.config import API_BASE


# ── formatting helpers ────────────────────────────────────────────────────────

def _fmt_time(s: int) -> str:
    h, m = s // 3600, (s % 3600) // 60
    return f"{h}:{m:02d}:{s % 60:02d}" if h else f"{m}:{s % 60:02d}"


def _source_label(source: str) -> str:
    """Convert a raw source key to a human-readable label."""
    if source.startswith("video::"):
        parts = source.split("::")
        if len(parts) == 5 and parts[4].isdigit():
            parts = parts[:4]
        if len(parts) == 4:
            _, name, start_s, chapter = parts
            ts = _fmt_time(int(start_s)) if start_s.isdigit() else start_s
            return f"🎬 {name} — \"{chapter}\" ({ts})"
        return f"🎬 {source.removeprefix('video::')}"
    if source.startswith("doc::"):
        parts = source.split("::")
        if len(parts) >= 3:
            title = parts[2] if parts[2] != "-" else "ukjent tittel"
            insurer = parts[3] if len(parts) > 3 and parts[3] != "-" else ""
            year = parts[4] if len(parts) > 4 and parts[4] != "-" else ""
            suffix = f" ({', '.join(x for x in [insurer, year] if x)})" if insurer or year else ""
            return f"📄 {title}{suffix}"
        return f"📄 {source.removeprefix('doc::')}"
    if source.startswith("doc_"):
        return f"📄 Forsikringsdokument (ID {source.removeprefix('doc_')})"
    if source.startswith("video_"):
        slug = (
            source.removeprefix("video_whisper_input_Videosubtime_")
            .removesuffix("_sections_json").removesuffix("_timeline_json").replace("_", " ")
        )
        return f"🎬 Video: {slug}"
    return source


@st.cache_data(ttl=300)
def _fetch_videos() -> list:
    try:
        resp = requests.get(f"{API_BASE}/videos", timeout=15)
        return resp.json() if resp.ok else []
    except Exception:
        return []


def _render_inline_player(dl: dict) -> None:
    from ui.views.videos import _render_video_player
    videos = _fetch_videos()
    vid = next((v for v in videos if v.get("filename") == dl["display_name"]), None)
    if vid:
        _render_video_player(vid, compact=True, autoplay_at=float(dl["start_seconds"]))
    else:
        st.info(f"Video ikke funnet: {dl['display_name']}")


# ── table-aware markdown renderer ─────────────────────────────────────────────

def _render_with_tables(text: str) -> None:
    """Render markdown; any embedded markdown tables become interactive st.dataframe."""
    parts = re.split(r'(\|.+\|(?:\n\|[-:| ]+\|)(?:\n\|.+\|)*)', text, flags=re.MULTILINE)
    for part in parts:
        stripped = part.strip()
        if stripped.startswith("|") and "\n" in stripped:
            lines = [ln for ln in stripped.splitlines() if not re.match(r'^\|[-:| ]+\|$', ln.strip())]
            if len(lines) >= 2:
                try:
                    rows = [[c.strip() for c in ln.strip("|").split("|")] for ln in lines]
                    df = pd.DataFrame(rows[1:], columns=rows[0])
                    st.dataframe(df, width="stretch", hide_index=True)
                    continue
                except Exception:
                    pass
        if stripped:
            st.markdown(part)


# ── kb stats ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _fetch_kb_stats() -> dict:
    try:
        r = requests.get(f"{API_BASE}/knowledge/index/stats", timeout=5)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def _render_kb_stats_bar() -> None:
    stats = _fetch_kb_stats()
    total = stats.get("total", 0)
    docs = stats.get("doc_chunks", 0)
    vids = stats.get("video_chunks", 0)
    if total:
        c1, c2, c3 = st.columns(3)
        c1.metric("Totalt indeksert", total)
        c2.metric("📄 Dokumentbiter", docs)
        c3.metric("🎬 Videobiter", vids)
    else:
        st.info("Ingen kunnskap indeksert ennå. Gå til **Administrer** og klikk «Indekser kunnskap».")


# ── chat ─────────────────────────────────────────────────────────────────────

_STARTERS = [
    ("🛡️", "Hva dekker ansvarsforsikring?"),
    ("💻", "Hva er cyberforsikring og hvem trenger det?"),
    ("👔", "Krav og dekning for styreansvarsforsikring?"),
    ("🏗️", "Hva er byggeforsikring?"),
]


def _send_kb_question(question: str) -> None:
    """Append user message, call API, append assistant response."""
    st.session_state["kb_messages"].append({"role": "user", "content": question, "sources": []})
    try:
        resp = requests.post(f"{API_BASE}/knowledge/chat", json={"question": question}, timeout=120)
        data = resp.json() if resp.ok else {}
        answer = data.get("answer") or f"Feil: {resp.status_code}"
        sources = data.get("sources", [])
        source_snippets = data.get("source_snippets", {})
    except Exception as e:
        answer, sources, source_snippets = f"Kunne ikke kontakte API: {e}", [], {}
    st.session_state["kb_messages"].append(
        {"role": "assistant", "content": answer, "sources": sources, "source_snippets": source_snippets}
    )


_CHAT_CSS = """
<style>
/* ── user bubble ── */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: #2C3E50 !important;
    border-radius: 12px !important;
    padding: 10px 16px !important;
    margin: 6px 0 !important;
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p,
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) .stMarkdown {
    color: #D4C9B8 !important;
}
/* ── assistant bubble ── */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: #F7F5F2 !important;
    border: 1px solid #D0CBC3 !important;
    border-radius: 12px !important;
    padding: 10px 16px !important;
    margin: 6px 0 !important;
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) p {
    color: #2C3E50 !important;
}
/* ── chat input bar — flat, no bubble ── */
div[data-testid="stChatInput"] {
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
    padding: 0 !important;
}
div[data-testid="stChatInput"] textarea {
    border: 1px solid #D0CBC3 !important;
    border-radius: 8px !important;
    background: #fff !important;
    box-shadow: none !important;
    padding: 10px 14px !important;
    font-size: 0.9rem !important;
    color: #2C3E50 !important;
}
</style>
"""


def _render_knowledge_chat() -> None:
    st.markdown(_CHAT_CSS, unsafe_allow_html=True)

    if "kb_messages" not in st.session_state:
        st.session_state["kb_messages"] = []

    pending = st.session_state.pop("kb_pending_question", None)
    if pending:
        with st.spinner("Søker i kunnskapsbasen…"):
            _send_kb_question(pending)
        st.rerun()

    dl = st.session_state.get("kb_video_player")

    if dl:
        # Split layout: video on left, chat on right
        video_col, chat_col = st.columns([2, 3], gap="large")
        with video_col:
            hdr, close_btn = st.columns([5, 1])
            hdr.caption(f"🎬 **{dl['display_name']}**")
            if close_btn.button("✕", key="kb_close_player"):
                st.session_state.pop("kb_video_player", None)
                st.rerun()
            _render_inline_player(dl)
            videos = _fetch_videos()
            vid = next((v for v in videos if v.get("filename") == dl["display_name"]), None)
            if vid:
                from ui.views.videos import _parse_sections, _fmt_time as _vfmt
                sections = _parse_sections(vid.get("sections") or [])
                if sections:
                    st.markdown("**Steg i videoen**")
                    for step_i, ch in enumerate(sections, 1):
                        ts = _vfmt(ch["start"])
                        label = ch["title"] or f"Steg {step_i}"
                        is_current = abs(ch["start"] - dl.get("start_seconds", 0)) < 30
                        prefix = "▶" if is_current else f"{step_i}."
                        if st.button(
                            f"{prefix}  {ts}  {label}",
                            key=f"kb_step_{step_i}",
                            type="primary" if is_current else "secondary",
                            width="stretch",
                        ):
                            st.session_state["kb_video_player"] = {
                                **dl, "start_seconds": int(ch["start"]), "chapter": label,
                            }
                            st.rerun()
    else:
        chat_col = st  # full-width chat when no video is playing

    with chat_col:
        if not st.session_state["kb_messages"]:
            _render_kb_stats_bar()
            st.markdown("#### Forslag til spørsmål")
            c1, c2 = st.columns(2)
            for i, (icon, q) in enumerate(_STARTERS):
                col = c1 if i % 2 == 0 else c2
                if col.button(f"{icon}  {q}", key=f"kb_starter_{i}", width="stretch"):
                    st.session_state["kb_pending_question"] = q
                    st.rerun()
            st.markdown("---")

        for msg_idx, msg in enumerate(st.session_state["kb_messages"]):
            with st.chat_message(msg["role"]):
                _render_with_tables(msg["content"])
                if msg.get("sources"):
                    with st.expander(f"Kilder ({len(msg['sources'])})", expanded=False):
                        for src_idx, src in enumerate(msg["sources"]):
                            st.caption(_source_label(src))
                            snippet = msg.get("source_snippets", {}).get(src, "")
                            if snippet:
                                st.caption(f"_{snippet}_")
                            if src.startswith("video::"):
                                parts = src.split("::")
                                if len(parts) == 5 and parts[4].isdigit():
                                    parts = parts[:4]
                                if len(parts) == 4:
                                    _, dname, start_s, chapter = parts
                                    ts = _fmt_time(int(start_s)) if start_s.isdigit() else start_s
                                    if st.button(f"▶ Se i video ({ts})", key=f"dl_{msg_idx}_{src_idx}"):
                                        st.session_state["kb_video_player"] = {
                                            "display_name": dname,
                                            "start_seconds": int(start_s) if start_s.isdigit() else 0,
                                            "chapter": chapter,
                                        }
                                        st.rerun()

        question = st.chat_input("Still et spørsmål om videoer eller dokumenter…")
        if question:
            with st.spinner("Søker i kunnskapsbasen…"):
                _send_kb_question(question)
            st.rerun()

        if st.session_state["kb_messages"] and st.button("Tøm samtale", key="kb_clear"):
            st.session_state["kb_messages"] = []
            st.session_state.pop("kb_video_player", None)
            st.rerun()


# ── search ────────────────────────────────────────────────────────────────────

def _render_knowledge_search() -> None:
    kb_query = st.text_input(
        "Søk i kunnskapsbase",
        placeholder="f.eks. 'negativ egenkapital' eller 'cyber dekning'",
        key="kb_query",
    )
    filter_col, limit_col = st.columns([2, 1])
    filter_type = filter_col.radio(
        "Filtrer", ["Alle", "📄 Dokumenter", "🎬 Videoer"], horizontal=True, key="kb_filter_type",
        label_visibility="collapsed",
    )
    kb_limit = limit_col.slider("Antall resultater", 5, 30, 10, key="kb_limit")

    if st.button("Søk", key="kb_search_btn") and kb_query.strip():
        with st.spinner("Søker…"):
            try:
                resp = requests.get(
                    f"{API_BASE}/knowledge",
                    params={"query": kb_query, "limit": kb_limit},
                    timeout=10,
                )
                results = resp.json() if resp.ok else []
            except Exception:
                results = []

        if filter_type == "📄 Dokumenter":
            results = [r for r in results if r.get("source", "").startswith("doc")]
        elif filter_type == "🎬 Videoer":
            results = [r for r in results if r.get("source", "").startswith("video")]

        if not results:
            st.info("Ingen relevante treff. Prøv et annet søkeord, eller indekser kunnskap via Administrer-fanen.")
        else:
            n_docs = sum(1 for r in results if r.get("source", "").startswith("doc"))
            n_vids = len(results) - n_docs
            st.markdown(
                f"**{len(results)} treff** — "
                f"📄 {n_docs} fra dokumenter · 🎬 {n_vids} fra videoer"
            )
            for r in results:
                src = r.get("source", "")
                badge = "🎬" if src.startswith("video") else "📄"
                with st.container(border=True):
                    c1, c2 = st.columns([2, 5])
                    with c1:
                        st.markdown(f"**{badge} {_source_label(src)}**")
                        st.caption(f"Orgnr: `{r['orgnr']}`  ·  {(r.get('created_at') or '')[:10]}")
                    with c2:
                        st.markdown(r["chunk_text"])


# ── analyse ───────────────────────────────────────────────────────────────────

_COMPARISON_PROMPTS = [
    (
        "📊 Sammenlign ansvarsforsikring og produktansvar",
        "Lag en kompakt sammenligningstabell (markdown) av ansvarsforsikring og produktansvarsforsikring "
        "med kolonner: Type | Hva dekkes | Typiske unntak | Hvem trenger det.",
    ),
    (
        "📊 Oversikt over vanlige bedriftsforsikringer",
        "Lag en oversiktstabell (markdown) over de 6 vanligste forsikringstypene for norske SMB-bedrifter "
        "med kolonner: Forsikringstype | Hva dekkes | Typisk forsikringssum | Anbefalt for.",
    ),
    (
        "📊 Cyberforsikring — dekning og unntak",
        "Lag en tabell (markdown) over hva cyberforsikring typisk dekker og ikke dekker, "
        "med kolonner: Område | Dekket? | Eksempel.",
    ),
    (
        "📊 Sammenlign forsikringstilbydere i dokumentene",
        "Basert på forsikringsdokumentene i kunnskapsbasen, lag en sammenligningstabell av "
        "forsikringstilbyderne med kolonner: Selskap | Produkt | Dekning | Premie | Særtrekk.",
    ),
    (
        "📊 Forsikringslovgivning — nøkkelparagrafer",
        "Lag en oversiktstabell (markdown) over de viktigste paragrafene i Forsikringsavtaleloven (FAL) "
        "som er relevante for bedriftsforsikring, med kolonner: § | Tema | Hva det innebærer.",
    ),
]


def _render_knowledge_analyse() -> None:
    st.markdown("#### AI-genererte sammenligninger og tabeller")
    st.caption(
        "Klikk en knapp for å be AI-en lage en strukturert tabell basert på kunnskapsbasen. "
        "Tabeller vises som interaktive og sorterbare."
    )
    _render_kb_stats_bar()
    st.markdown("---")

    if "kb_analyse_result" not in st.session_state:
        st.session_state["kb_analyse_result"] = None

    for label, prompt in _COMPARISON_PROMPTS:
        if st.button(label, key=f"analyse_{label[:20]}", width="stretch"):
            with st.spinner("AI analyserer kunnskapsbasen…"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/knowledge/chat", json={"question": prompt}, timeout=120
                    )
                    data = resp.json() if resp.ok else {}
                    st.session_state["kb_analyse_result"] = {
                        "label": label,
                        "answer": data.get("answer", "Ingen svar."),
                        "sources": data.get("sources", []),
                    }
                except Exception as e:
                    st.session_state["kb_analyse_result"] = {
                        "label": label,
                        "answer": f"Feil: {e}",
                        "sources": [],
                    }
            st.rerun()

    result = st.session_state.get("kb_analyse_result")
    if result:
        st.markdown("---")
        st.markdown(f"**{result['label']}**")
        _render_with_tables(result["answer"])

        if result.get("sources"):
            with st.expander(f"Kilder ({len(result['sources'])})", expanded=False):
                for src in result["sources"]:
                    st.caption(_source_label(src))

        answer_text = result["answer"]
        tables = re.findall(r'(\|.+\|(?:\n\|[-:| ]+\|)(?:\n\|.+\|)*)', answer_text, re.MULTILINE)
        if tables:
            for t_idx, tbl in enumerate(tables):
                lines = [ln for ln in tbl.strip().splitlines() if not re.match(r'^\|[-:| ]+\|$', ln.strip())]
                if len(lines) >= 2:
                    try:
                        rows = [[c.strip() for c in ln.strip("|").split("|")] for ln in lines]
                        df = pd.DataFrame(rows[1:], columns=rows[0])
                        buf = df.to_csv(index=False).encode()
                        st.download_button(
                            f"⬇️ Last ned tabell {t_idx + 1} som CSV",
                            data=buf,
                            file_name=f"sammenligning_{t_idx + 1}.csv",
                            mime="text/csv",
                            key=f"dl_csv_{t_idx}",
                        )
                    except Exception:
                        pass

        if st.button("Tøm resultat", key="kb_analyse_clear"):
            st.session_state["kb_analyse_result"] = None
            st.rerun()


# ── manage ────────────────────────────────────────────────────────────────────

def _render_knowledge_manage() -> None:
    st.markdown("### Indeksert kunnskap")

    try:
        stats_resp = requests.get(f"{API_BASE}/knowledge/index/stats", timeout=8)
        if stats_resp.ok:
            s = stats_resp.json()
            col1, col2, col3 = st.columns(3)
            col1.metric("Totalt indeksert", s.get("total", 0))
            col2.metric("Dokumentbiter", s.get("doc_chunks", 0))
            col3.metric("Videobiter", s.get("video_chunks", 0))
            if s.get("total", 0) > 0:
                chart_df = pd.DataFrame({
                    "Type": ["📄 Dokumenter", "🎬 Videoer"],
                    "Biter": [s.get("doc_chunks", 0), s.get("video_chunks", 0)],
                })
                st.bar_chart(chart_df.set_index("Type"), height=150)
    except Exception:
        st.info("Klarte ikke hente indeksstatistikk.")

    st.markdown("---")
    st.markdown("### Indekser kunnskap")
    force = st.toggle("Tving full re-indeksering (sletter eksisterende)", key="kb_force_toggle")
    st.caption(
        "Sletter alle eksisterende kunnskapsbiter og bygger opp indeksen på nytt fra scratch."
        if force else
        "Kun nye kilder indekseres — allerede indeksert innhold hoppes over."
    )
    if st.button("Indekser kunnskap", key="kb_index_btn", type="primary"):
        with st.spinner("Indekserer dokumenter og videoer… dette kan ta noen minutter."):
            try:
                r = requests.post(f"{API_BASE}/knowledge/index", params={"force": "true" if force else "false"}, timeout=300)
                if r.ok:
                    data = r.json()
                    cleared = data.get("cleared_chunks", 0)
                    st.success(
                        f"{'Slettet ' + str(cleared) + ' gamle biter. ' if cleared else ''}"
                        f"{data.get('total_new_chunks', 0)} nye biter lagt til "
                        f"({data.get('docs_chunks', 0)} fra dokumenter, "
                        f"{data.get('video_chunks', 0)} fra videoer)."
                    )
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Feil: {r.status_code} — {r.text}")
            except Exception as e:
                st.error(f"Indeksering feilet: {e}")

    st.markdown("---")
    st.markdown("### Norsk forsikringslovgivning")
    st.caption(
        "Henter og indekserer Forsikringsavtaleloven, Forsikringsformidlingsloven og "
        "Forsikringsvirksomhetsloven fra Lovdata.no. Allerede indekserte lover hoppes over."
    )
    if st.button("Last inn forsikringslovgivning", key="kb_regs_btn"):
        with st.spinner("Henter og indekserer lover fra Lovdata.no… kan ta 30–60 sek."):
            try:
                r = requests.post(f"{API_BASE}/knowledge/seed-regulations", timeout=120)
                if r.ok:
                    data = r.json()
                    for reg in data.get("seeded", []):
                        status = reg.get("status", "")
                        if status == "already_indexed":
                            st.info(f"✓ {reg['name']} — allerede indeksert")
                        elif status == "indexed":
                            st.success(f"✓ {reg['name']} — {reg['chunks']} biter indeksert")
                        else:
                            st.warning(f"⚠ {reg['name']} — kunne ikke hentes")
                    st.rerun()
                else:
                    st.error(f"Feil: {r.status_code} — {r.text}")
            except Exception as e:
                st.error(f"Feil: {e}")

    st.markdown("---")
    st.markdown("### Legg til egendefinert tekst")
    st.caption("Teksten vil bli delt opp i biter og embeddet for bruk i AI-chat.")
    ingest_orgnr = st.text_input("Orgnr (9 siffer)", max_chars=9, key="kb_ingest_orgnr")
    ingest_source = st.text_input("Kildelabel", key="kb_ingest_source", value="custom_note")
    ingest_text = st.text_area("Tekst å legge inn", height=150, key="kb_ingest_text")
    if st.button("Lagre i kunnskapsbase", key="kb_ingest_btn"):
        if not ingest_orgnr.strip() or len(ingest_orgnr.strip()) != 9:
            st.error("Skriv inn et gyldig 9-sifret orgnr.")
        elif not ingest_text.strip():
            st.error("Teksten kan ikke være tom.")
        else:
            with st.spinner("Chunker og embedder…"):
                try:
                    r = requests.post(
                        f"{API_BASE}/org/{ingest_orgnr.strip()}/ingest-knowledge",
                        json={"text": ingest_text.strip(), "source": ingest_source.strip() or "custom_note"},
                        timeout=30,
                    )
                    if r.ok:
                        data = r.json()
                        st.success(f"Lagret {data['chunks_stored']} biter for orgnr {data['orgnr']}.")
                    else:
                        st.error(f"Feil: {r.status_code} — {r.text}")
                except Exception as e:
                    st.error(f"Kunne ikke kontakte API: {e}")


# ── tab entry point ───────────────────────────────────────────────────────────

def render_knowledge_tab() -> None:
    st.markdown("## Kunnskapsbase")
    chat_tab, search_tab, analyse_tab, manage_tab = st.tabs(
        ["💬 Chat", "🔍 Søk", "📊 Analyser", "⚙️ Administrer"]
    )
    with chat_tab:
        _render_knowledge_chat()
    with search_tab:
        _render_knowledge_search()
    with analyse_tab:
        _render_knowledge_analyse()
    with manage_tab:
        _render_knowledge_manage()
