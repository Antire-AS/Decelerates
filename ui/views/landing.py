"""Landing page — first tab shown after login.

Shows a welcome message, live stats, and quick-start actions.
"""
import streamlit as st

from ui.config import API_BASE
from ui.auth import get_user, is_manager


def _fetch_stats() -> dict:
    """Return portfolio count, total companies, and knowledge chunk count."""
    import requests

    stats = {"portfolios": 0, "companies": 0, "chunks": 0}
    try:
        r = requests.get(f"{API_BASE}/portfolio", timeout=5)
        if r.ok:
            portfolios = r.json()
            stats["portfolios"] = len(portfolios)
            # sum companies across all portfolios via a second call if needed
    except Exception:
        pass
    try:
        r = requests.get(f"{API_BASE}/knowledge/index/stats", timeout=5)
        if r.ok:
            data = r.json()
            stats["chunks"] = data.get("total_chunks", 0)
    except Exception:
        pass
    try:
        r = requests.get(f"{API_BASE}/companies", timeout=5)
        if r.ok:
            data = r.json()
            stats["companies"] = len(data.get("companies", []))
    except Exception:
        pass
    return stats


def render_landing_tab() -> None:
    user = get_user()

    # ── Welcome greeting ──────────────────────────────────────────────────────
    if user:
        name = user.get("name") or user.get("email") or "Bruker"
        st.markdown(f"### Velkommen, {name} 👋")
    else:
        st.markdown("### Velkommen til Broker Accelerator")

    st.markdown(
        "Din digitale arbeidsflate for due diligence, risikovurdering og "
        "forsikringsrådgivning — drevet av AI og norske dataregistre."
    )

    st.markdown("---")

    # ── Live stats ────────────────────────────────────────────────────────────
    stats = _fetch_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Porteføljer", stats["portfolios"])
    c2.metric("Selskaper analysert", stats["companies"])
    c3.metric("Kunnskapsbase", f'{stats["chunks"]:,} chunks')

    st.markdown("---")

    # ── Feature cards ─────────────────────────────────────────────────────────
    st.markdown("#### Hva kan du gjøre?")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div style="background:#fff;border:1px solid #D0CBC3;border-top:3px solid #4A6FA5;
                        border-radius:6px;padding:1rem 1.1rem;">
            <b>🔍 Selskapsøk & Risiko</b><br>
            <span style="font-size:0.85rem;color:#5A5248;">Søk i Brønnøysund, hent regnskap,
            beregn risikoscore og se styremedlemmer — alt på ett sted.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div style="background:#fff;border:1px solid #D0CBC3;border-top:3px solid #4A6FA5;
                        border-radius:6px;padding:1rem 1.1rem;">
            <b>📁 Portefølje & Analyse</b><br>
            <span style="font-size:0.85rem;color:#5A5248;">Bygg porteføljer, sammenlign
            selskaper og still AI spørsmål på tvers av hele porteføljen.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div style="background:#fff;border:1px solid #D0CBC3;border-top:3px solid #4A6FA5;
                        border-radius:6px;padding:1rem 1.1rem;">
            <b>📚 Kunnskap & Lovverk</b><br>
            <span style="font-size:0.85rem;color:#5A5248;">Chat med AI om norsk
            forsikringslovgivning, kursvideoer og interne dokumenter.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Quick-start buttons ───────────────────────────────────────────────────
    st.markdown("#### Kom i gang")
    qa, qb = st.columns(2)
    with qa:
        if st.button("🔍 Søk etter et selskap", use_container_width=True, type="primary"):
            st.session_state["_goto_tab"] = "search"
            st.rerun()
    with qb:
        if st.button("📁 Åpne Portefølje", use_container_width=True):
            st.session_state["_goto_tab"] = "portfolio"
            st.rerun()

    # ── Manager admin section ─────────────────────────────────────────────────
    if is_manager():
        st.markdown("---")
        st.markdown("#### 🔑 Admin")
        st.caption("Kun synlig for brukere med Manager-rolle.")
        ma, mb = st.columns(2)
        with ma:
            if st.button("🌱 Last inn demodata", use_container_width=True):
                st.session_state["_goto_tab"] = "portfolio"
                st.rerun()
        with mb:
            if st.button("📊 Norges Topp 100", use_container_width=True):
                st.session_state["_goto_tab"] = "portfolio"
                st.rerun()
