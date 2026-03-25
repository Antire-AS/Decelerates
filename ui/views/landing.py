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


def _fetch_recent_companies() -> list:
    try:
        r = requests.get(f"{API_BASE}/companies", params={"limit": 5, "sort_by": "navn"}, timeout=6)
        return r.json() if r.ok else []
    except Exception:
        return []


def render_landing_tab() -> None:
    user = get_user()
    name = (user.get("name") or user.get("email") or "Bruker") if user else "Bruker"
    st.markdown(f"### Velkommen, {name}")

    data = _fetch_dashboard()
    has_crm = data is not None and data.get("total_active_policies", 0) > 0

    # ── Key metrics row ───────────────────────────────────────────────────────
    if data is not None:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Fornyelser neste 30 dager",
            data["renewals_30d"],
            help=f"kr {data['premium_at_risk_30d']:,.0f} i premie",
        )
        c2.metric("Aktive avtaler", data["total_active_policies"])
        c3.metric("Åpne skader", data["open_claims"])
        c4.metric("Aktiviteter forfalt", data["activities_due"])

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
                    "— gå til **Fornyelser** for detaljer."
                )
        with col_renewals:
            if data["renewals_30d"] > 0:
                st.warning(
                    f"🔔 **{data['renewals_30d']} avtale(r)** forfaller innen 30 dager. "
                    f"kr {data['premium_at_risk_30d']:,.0f} i premie er til fornyelse."
                )
            elif has_crm:
                st.success("Ingen avtaler forfaller de neste 30 dagene.")

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
                    f"<span style='color:#999;font-size:12px'>"
                    f" — {a.get('created_by','?')}{orgnr_label}</span>",
                    unsafe_allow_html=True,
                )

    # ── Companies in database ─────────────────────────────────────────────────
    if not has_crm:
        companies = _fetch_recent_companies()
        if companies:
            st.markdown("---")
            st.markdown("#### Selskaper i databasen")
            _RISK_BADGE = {None: "–", **{i: ("🟢 Lav" if i <= 3 else "🟡 Moderat" if i <= 7 else "🔴 Høy")
                                         for i in range(1, 16)}}
            cols = st.columns([3, 2, 2, 1])
            cols[0].markdown("**Selskap**")
            cols[1].markdown("**Bransje**")
            cols[2].markdown("**Kommune**")
            cols[3].markdown("**Risiko**")
            for c in companies:
                row = st.columns([3, 2, 2, 1])
                row[0].write(c.get("navn") or c.get("orgnr"))
                row[1].caption((c.get("naeringskode1_beskrivelse") or "")[:30])
                row[2].caption(c.get("kommune") or "–")
                score = c.get("risk_score")
                row[3].caption(_RISK_BADGE.get(score, "🔴 Høy"))

    if not has_crm:
        st.markdown("---")
        st.info(
            "**Kom i gang:** Gå til **⚙️ Admin** og trykk **Seed CRM demo-data** "
            "for å fylle opp Fornyelser, skader og aktiviteter med realistiske testdata."
        )

    st.markdown("---")
    _render_quickstart()


def _render_quickstart() -> None:
    st.markdown("#### Hurtignavigering")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("🔍 Selskapsøk", width="stretch", type="primary"):
            st.session_state["_goto_tab"] = "search"
            st.rerun()
    with c2:
        if st.button("🔔 Fornyelser", width="stretch"):
            st.session_state["_goto_tab"] = "renewals"
            st.rerun()
    with c3:
        if st.button("📁 Portefølje", width="stretch"):
            st.session_state["_goto_tab"] = "portfolio"
            st.rerun()
    with c4:
        if st.button("📄 Dokumenter", width="stretch"):
            st.session_state["_goto_tab"] = "documents"
            st.rerun()
