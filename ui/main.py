import pathlib
import streamlit as st

from ui.config import T
from ui.views.search import render_search_tab
from ui.views.portfolio import render_portfolio_tab
from ui.views.documents import render_documents_tab
from ui.views.sla import render_sla_tab
from ui.views.knowledge import render_knowledge_tab

# ── Language toggle (must happen before any output) ──────────────────────────
if "lang" not in st.session_state:
    st.session_state["lang"] = "no"

st.set_page_config(
    page_title="Broker Accelerator",
    page_icon="⚖️",
    layout="wide",
)

st.markdown(f"<style>{pathlib.Path('ui/styles.css').read_text()}</style>", unsafe_allow_html=True)
st.markdown("""
<div class="broker-header">
    <div class="broker-header-icon">⚖️</div>
    <div>
        <h1>Broker Accelerator</h1>
        <p>Forsikringsmegling &nbsp;&middot;&nbsp; Due Diligence &nbsp;&middot;&nbsp; Risikoprofil</p>
    </div>
</div>
""", unsafe_allow_html=True)

_lang_col, _btn_col = st.columns([9, 1])
with _lang_col:
    _current_lang = st.session_state.get("lang", "no")
    _lang_label = "🇳🇴 Norsk" if _current_lang == "no" else "🇬🇧 English"
    st.caption(f"Språk: **{_lang_label}** — klikk for å bytte" if _current_lang == "no" else f"Language: **{_lang_label}** — click to switch")
with _btn_col:
    _toggle_label = "🇬🇧 EN" if _current_lang == "no" else "🇳🇴 NO"
    if st.button(_toggle_label, key="lang_toggle", type="secondary"):
        st.session_state["lang"] = "en" if _current_lang == "no" else "no"
        st.session_state["forsikringstilbud_pdf"] = None
        st.rerun()

tab_search, tab_portfolio, tab_docs, tab_sla, tab_knowledge = st.tabs(
    ["Selskapsøk", "Portefølje", "Dokumenter", "Avtaler", "Kunnskapsbase"]
)

with tab_search:
    render_search_tab()

with tab_portfolio:
    render_portfolio_tab()

with tab_docs:
    render_documents_tab()

with tab_sla:
    render_sla_tab()

with tab_knowledge:
    render_knowledge_tab()
