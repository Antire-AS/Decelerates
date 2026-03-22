"""Knowledge base tab: AI chat over videos and insurance documents, plus search and management."""
import requests
import streamlit as st

from ui.config import API_BASE


def _fmt_time(s: int) -> str:
    h, m = s // 3600, (s % 3600) // 60
    return f"{h}:{m:02d}:{s % 60:02d}" if h else f"{m}:{s % 60:02d}"


def _source_label(source: str) -> str:
    """Convert a raw source key to a human-readable label."""
    # New format: video::{display_name}::{start_seconds}::{chapter_title}[::N]
    if source.startswith("video::"):
        parts = source.split("::")
        # Strip trailing sub-chunk index (::2, ::3, …)
        if len(parts) == 5 and parts[4].isdigit():
            parts = parts[:4]
        if len(parts) == 4:
            _, name, start_s, chapter = parts
            ts = _fmt_time(int(start_s)) if start_s.isdigit() else start_s
            return f"🎬 {name} — \"{chapter}\" ({ts})"
        return f"🎬 {source.removeprefix('video::')}"
    # New format: doc::{id}::{title}::{insurer}::{year}
    if source.startswith("doc::"):
        parts = source.split("::")
        if len(parts) >= 3:
            title = parts[2] if parts[2] != "-" else "ukjent tittel"
            insurer = parts[3] if len(parts) > 3 and parts[3] != "-" else ""
            year = parts[4] if len(parts) > 4 and parts[4] != "-" else ""
            suffix = f" ({', '.join(x for x in [insurer, year] if x)})" if insurer or year else ""
            return f"📄 {title}{suffix}"
        return f"📄 {source.removeprefix('doc::')}"
    # Legacy formats
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


def _render_knowledge_chat() -> None:
    if "kb_messages" not in st.session_state:
        st.session_state["kb_messages"] = []

    chat_col, video_col = st.columns([3, 2], gap="large")

    with chat_col:
        st.caption("Chat direkte med AI om innholdet i kursvideoene og forsikringsdokumentene.")
        for msg_idx, msg in enumerate(st.session_state["kb_messages"]):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
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
            st.session_state["kb_messages"].append({"role": "user", "content": question, "sources": []})
            with st.spinner("Søker i kunnskapsbasen…"):
                try:
                    resp = requests.post(f"{API_BASE}/knowledge/chat", json={"question": question}, timeout=120)
                    data = resp.json() if resp.ok else {}
                    answer = data.get("answer") or f"Feil: {resp.status_code}"
                    sources = data.get("sources", [])
                    source_snippets = data.get("source_snippets", {})
                except Exception as e:
                    answer, sources, source_snippets = f"Kunne ikke kontakte API: {e}", [], {}
            st.session_state["kb_messages"].append({"role": "assistant", "content": answer, "sources": sources, "source_snippets": source_snippets})
            st.rerun()

        if st.session_state["kb_messages"] and st.button("Tøm samtale", key="kb_clear"):
            st.session_state["kb_messages"] = []
            st.session_state.pop("kb_video_player", None)
            st.rerun()

    with video_col:
        dl = st.session_state.get("kb_video_player")
        if dl:
            hdr, close_btn = st.columns([5, 1])
            hdr.caption(f"🎬 **{dl['display_name']}** — {dl['chapter']}")
            if close_btn.button("✕", key="kb_close_player"):
                st.session_state.pop("kb_video_player", None)
                st.rerun()
            _render_inline_player(dl)
        else:
            st.caption("Trykk **▶ Se i video** på en kilde for å spille av her.")


def _render_knowledge_search() -> None:
    kb_query = st.text_input(
        "Søk i kunnskapsbase",
        placeholder="f.eks. 'negativ egenkapital' eller 'cyber dekning'",
        key="kb_query",
    )
    kb_limit = st.slider("Antall resultater", 5, 30, 10, key="kb_limit")

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

        if not results:
            st.info("Ingen relevante treff. Prøv et annet søkeord, eller indekser kunnskap via Administrer-fanen.")
        else:
            st.markdown(f"**{len(results)} treff**")
            for r in results:
                with st.container(border=True):
                    c1, c2 = st.columns([2, 5])
                    with c1:
                        st.markdown(f"**Orgnr:** `{r['orgnr']}`")
                        st.caption(f"Kilde: {_source_label(r['source'])}")
                        st.caption(f"{(r.get('created_at') or '')[:10]}")
                    with c2:
                        st.markdown(r["chunk_text"])


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


def render_knowledge_tab() -> None:
    st.markdown("## Kunnskapsbase")
    chat_tab, search_tab, manage_tab = st.tabs(["💬 Chat", "🔍 Søk", "⚙️ Administrer"])
    with chat_tab:
        _render_knowledge_chat()
    with search_tab:
        _render_knowledge_search()
    with manage_tab:
        _render_knowledge_manage()
