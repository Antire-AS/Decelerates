import pathlib
import streamlit as st

from ui.config import T
from ui.auth import render_user_badge
from ui.views.landing import render_landing_tab
from ui.views.search import render_search_tab
from ui.views.portfolio import render_portfolio_tab
from ui.views.documents import render_documents_tab
from ui.views.sla import render_sla_tab
from ui.views.knowledge import render_knowledge_tab
from ui.views.videos import render_videos_tab
from ui.views.renewals import render_renewals_tab
from ui.views.admin import render_admin_tab
from ui.views.financials import render_financial_tab
from ui.views.onboarding import render_onboarding_tour, render_onboarding_button

# ── Language toggle (must happen before any output) ──────────────────────────
if "lang" not in st.session_state:
    st.session_state["lang"] = "no"

st.set_page_config(
    page_title="Broker Accelerator",
    page_icon="⚖️",
    layout="wide",
)

# ── Client token intercept — render read-only view before main app ────────────
_client_token = st.query_params.get("client_token")
if _client_token:
    from ui.views.client_view import render_client_view
    st.markdown(f"<style>{pathlib.Path('ui/styles.css').read_text()}</style>", unsafe_allow_html=True)
    render_client_view(_client_token)
    st.stop()

st.markdown(f"<style>{pathlib.Path('ui/styles.css').read_text()}</style>", unsafe_allow_html=True)
render_user_badge()
render_onboarding_tour()
render_onboarding_button()
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

# ── Tab navigation (landing page buttons can deep-link here) ─────────────────
_TAB_NAMES = ["Hjem", "Selskapsøk", "Portefølje", "Fornyelser", "Dokumenter", "Videoer", "Avtaler", "Finans", "Kunnskapsbase", "⚙️ Admin"]
_TAB_GOTO  = {"search": 1, "portfolio": 2, "renewals": 3, "documents": 4, "videos": 5, "sla": 6, "finans": 7, "knowledge": 8, "admin": 9}

_default_tab = _TAB_GOTO.get(st.session_state.pop("_goto_tab", None), 0)

(
    tab_landing, tab_search, tab_portfolio, tab_renewals, tab_docs,
    tab_videos, tab_sla, tab_finans, tab_knowledge, tab_admin
) = st.tabs(_TAB_NAMES)

# Programmatic tab navigation — st.tabs() has no index param, so we click via JS
if _default_tab > 0:
    import streamlit.components.v1 as _stc
    _stc.html(
        f"""<script>
        (function() {{
            var tabs = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
            if (tabs && tabs[{_default_tab}]) tabs[{_default_tab}].click();
        }})();
        </script>""",
        height=0,
    )

with tab_landing:
    render_landing_tab()

with tab_search:
    render_search_tab()

with tab_portfolio:
    render_portfolio_tab()

with tab_renewals:
    render_renewals_tab()

with tab_docs:
    render_documents_tab()

with tab_videos:
    render_videos_tab()

with tab_sla:
    render_sla_tab()

with tab_finans:
    render_financial_tab()

with tab_knowledge:
    render_knowledge_tab()

with tab_admin:
    render_admin_tab()
