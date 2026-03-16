"""Knowledge base tab: RAG search and manual text ingest."""
import requests
import streamlit as st

from ui.config import API_BASE


def render_knowledge_tab() -> None:
    st.markdown("## Kunnskapsbase")
    st.caption("Søk på tvers av all lagret selskapskunnskap, eller legg til manuell tekst som en kilde for AI-chat.")

    kb_sub_search, kb_sub_ingest = st.tabs(["Søk i kunnskap", "Legg til kunnskap"])

    with kb_sub_search:
        kb_query = st.text_input("Søk i kunnskapsbase", placeholder="f.eks. 'negativ egenkapital' eller 'cyber dekning'", key="kb_query")
        kb_limit = st.slider("Antall resultater", 5, 30, 10, key="kb_limit")

        if st.button("Søk", key="kb_search_btn") and kb_query.strip():
            with st.spinner("Søker..."):
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
                st.info("Ingen relevante treff. Prøv et annet søkeord, eller legg til mer kunnskap via 'Legg til kunnskap'.")
            else:
                st.markdown(f"**{len(results)} treff**")
                for r in results:
                    with st.container(border=True):
                        c1, c2 = st.columns([2, 5])
                        with c1:
                            st.markdown(f"**Orgnr:** `{r['orgnr']}`")
                            st.caption(f"Kilde: {r['source']}")
                            st.caption(f"{(r.get('created_at') or '')[:10]}")
                        with c2:
                            st.markdown(r["chunk_text"])

    with kb_sub_ingest:
        st.markdown("### Legg til tekst i kunnskapsbasen")
        st.caption("Teksten vil bli delt opp i biter og embeddet for bruk i AI-chat.")

        ingest_orgnr = st.text_input("Orgnr (9 siffer)", max_chars=9, key="kb_ingest_orgnr")
        ingest_source = st.text_input("Kildelabel (f.eks. 'notat_2025' eller 'e-post_klient')", key="kb_ingest_source", value="custom_note")
        ingest_text = st.text_area("Tekst å legge inn", height=200, key="kb_ingest_text")

        if st.button("Lagre i kunnskapsbase", key="kb_ingest_btn"):
            if not ingest_orgnr.strip() or len(ingest_orgnr.strip()) != 9:
                st.error("Skriv inn et gyldig 9-sifret orgnr.")
            elif not ingest_text.strip():
                st.error("Teksten kan ikke være tom.")
            else:
                with st.spinner("Chunker og embedder..."):
                    try:
                        r = requests.post(
                            f"{API_BASE}/org/{ingest_orgnr.strip()}/ingest-knowledge",
                            json={"text": ingest_text.strip(), "source": ingest_source.strip() or "custom_note"},
                            timeout=30,
                        )
                        if r.ok:
                            data = r.json()
                            st.success(f"Lagret {data['chunks_stored']} biter for orgnr {data['orgnr']} (kilde: {data['source']}).")
                        else:
                            st.error(f"Feil: {r.status_code} — {r.text}")
                    except Exception as e:
                        st.error(f"Kunne ikke kontakte API: {e}")
