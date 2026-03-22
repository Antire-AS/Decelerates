"""Render claims tracking section for a company profile."""
from datetime import date

import requests
import streamlit as st

from ui.config import API_BASE

_STATUS_ICON = {
    "open":      "🔵",
    "in_review": "🟡",
    "settled":   "🟢",
    "rejected":  "🔴",
}

_STATUS_LABEL = {
    "open": "Åpen", "in_review": "Under behandling",
    "settled": "Avgjort", "rejected": "Avvist",
}


def render_claims_section(orgnr: str, policies: list) -> None:
    with st.expander("🔥 Skader og krav", expanded=False):
        _render_claims_list(orgnr)
    with st.expander("➕ Registrer skade", expanded=False):
        _render_add_claim_form(orgnr, policies)


def _render_claims_list(orgnr: str) -> None:
    try:
        resp = requests.get(f"{API_BASE}/org/{orgnr}/claims", timeout=8)
        claims = resp.json() if resp.ok else []
    except Exception:
        claims = []

    if not claims:
        st.caption("Ingen registrerte skader.")
        return

    for c in claims:
        col_info, col_status, col_del = st.columns([4, 2, 1])
        with col_info:
            label = c.get("claim_number") or f"Skade #{c['id']}"
            st.markdown(f"**{label}**")
            parts = []
            if c.get("incident_date"):
                parts.append(f"Hendelse: {c['incident_date']}")
            if c.get("estimated_amount_nok"):
                parts.append(f"Estimert: kr {c['estimated_amount_nok']:,.0f}")
            if c.get("settled_amount_nok"):
                parts.append(f"Oppgjort: kr {c['settled_amount_nok']:,.0f}")
            st.caption(" · ".join(parts))
        with col_status:
            icon = _STATUS_ICON.get(c.get("status", ""), "⚪")
            label = _STATUS_LABEL.get(c.get("status", ""), c.get("status", ""))
            st.caption(f"{icon} {label}")
        with col_del:
            if st.button("🗑", key=f"del_claim_{c['id']}", help="Slett skade"):
                requests.delete(f"{API_BASE}/org/{orgnr}/claims/{c['id']}", timeout=8)
                st.rerun()


def _render_add_claim_form(orgnr: str, policies: list) -> None:
    if not policies:
        st.caption("Ingen forsikringsavtaler å knytte skaden til. Registrer en avtale først.")
        return

    policy_options = {
        f"{p['insurer']} — {p['product_type']} ({p.get('policy_number') or 'uten nr'})": p["id"]
        for p in policies
    }

    with st.form(f"add_claim_{orgnr}", clear_on_submit=True):
        policy_label = st.selectbox("Forsikringsavtale *", list(policy_options.keys()))
        col1, col2 = st.columns(2)
        claim_number   = col1.text_input("Skadenummer")
        status         = col2.selectbox("Status", ["open", "in_review", "settled", "rejected"],
                                        format_func=lambda s: _STATUS_LABEL.get(s, s))
        incident_date  = col1.date_input("Hendelsesdato", value=None)
        reported_date  = col2.date_input("Meldt dato", value=None)
        estimated      = col1.number_input("Estimert beløp (kr)", min_value=0.0, step=10_000.0)
        insurer_contact = col2.text_input("Kontakt hos forsikringsselskap")
        description    = st.text_area("Beskrivelse", height=80)
        notes          = st.text_area("Notater", height=60)

        if st.form_submit_button("Registrer skade"):
            payload = {
                "policy_id": policy_options[policy_label],
                "claim_number": claim_number or None, "status": status,
                "incident_date": incident_date.isoformat() if incident_date else None,
                "reported_date": reported_date.isoformat() if reported_date else None,
                "estimated_amount_nok": estimated if estimated > 0 else None,
                "insurer_contact": insurer_contact or None,
                "description": description or None, "notes": notes or None,
            }
            r = requests.post(f"{API_BASE}/org/{orgnr}/claims", json=payload, timeout=8)
            if r.status_code == 201:
                st.success("Skade registrert!")
                st.rerun()
            else:
                st.error(f"Feil: {r.text}")
