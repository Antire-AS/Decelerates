"""Landing dashboard — first tab shown after login."""
import requests
import streamlit as st

from ui.config import API_BASE, get_auth_headers
from ui.auth import get_user


def _fetch_dashboard() -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/dashboard", headers=get_auth_headers(), timeout=8)
        return r.json() if r.ok else None
    except Exception:
        return None


def render_landing_tab() -> None:
    user = get_user()
    name = (user.get("name") or user.get("email") or "Bruker") if user else "Bruker"
    st.markdown(f"### Velkommen, {name}")

    data = _fetch_dashboard()

    if data is None:
        _render_quickstart()
        return

    # ── Key metrics row ───────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Fornyelser neste 30 dager",
        data["renewals_30d"],
        help=f"kr {data['premium_at_risk_30d']:,.0f} i premie",
    )
    c2.metric("Aktive avtaler", data["total_active_policies"])
    c3.metric("Åpne skader", data["open_claims"])
    c4.metric(
        "Aktiviteter forfalt",
        data["activities_due"],
        delta=None,
    )

    # ── Premium book ──────────────────────────────────────────────────────────
    st.markdown("---")
    col_book, col_renewals = st.columns(2)

    with col_book:
        st.metric(
            "Samlet premievolum",
            f"kr {data['total_premium_book']:,.0f}",
            help="Sum av årspremier på alle aktive forsikringsavtaler",
        )
        if data["renewals_90d"] > 0:
            st.caption(
                f"⚠️ {data['renewals_90d']} avtale(r) forfaller innen 90 dager "
                f"— gå til **Fornyelser** for detaljer."
            )

    with col_renewals:
        if data["renewals_30d"] > 0:
            st.warning(
                f"🔔 **{data['renewals_30d']} avtale(r)** forfaller innen 30 dager. "
                f"kr {data['premium_at_risk_30d']:,.0f} i premie er til fornyelse."
            )
        else:
            st.success("Ingen avtaler forfaller de neste 30 dagene.")

    # ── Recent activity feed ──────────────────────────────────────────────────
    recent = data.get("recent_activities", [])
    if recent:
        st.markdown("---")
        st.markdown("#### Siste aktiviteter")
        _TYPE_ICON = {"call": "📞", "email": "📧", "meeting": "🤝", "note": "📝", "task": "✅"}
        for a in recent:
            icon = _TYPE_ICON.get(a.get("type", ""), "•")
            done = "~~" if a.get("completed") else ""
            orgnr_label = f" · {a['orgnr']}" if a.get("orgnr") else ""
            st.markdown(
                f"{icon} {done}{a['subject']}{done}"
                f"<span style='color:#999;font-size:12px'> — {a.get('created_by','?')}{orgnr_label}</span>",
                unsafe_allow_html=True,
            )

    st.markdown("---")
    _render_quickstart()


def _render_quickstart() -> None:
    st.markdown("#### Hurtignavigering")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("🔍 Selskapsøk", use_container_width=True, type="primary"):
            st.session_state["_goto_tab"] = "search"
            st.rerun()
    with c2:
        if st.button("🔔 Fornyelser", use_container_width=True):
            st.session_state["_goto_tab"] = "renewals"
            st.rerun()
    with c3:
        if st.button("📁 Portefølje", use_container_width=True):
            st.session_state["_goto_tab"] = "portfolio"
            st.rerun()
    with c4:
        if st.button("📄 Dokumenter", use_container_width=True):
            st.session_state["_goto_tab"] = "documents"
            st.rerun()
