"""Render policy register section for a company profile."""
from datetime import date

import requests
import streamlit as st

from ui.config import API_BASE, get_auth_headers

_PRODUCT_TYPES = [
    "Yrkesskade", "Ansvarsforsikring", "Eiendomsforsikring", "Cyberforsikring",
    "Transportforsikring", "D&O-forsikring", "Nøkkelpersonforsikring",
    "Kredittforsikring", "Reiseforsikring", "Annet",
]

_STATUS_OPTIONS = ["active", "pending", "expired", "cancelled"]


def _days_badge(renewal_date_str) -> str:
    if not renewal_date_str:
        return "–"
    try:
        d = date.fromisoformat(renewal_date_str)
        days = (d - date.today()).days
        if days < 0:
            return f"🔴 Utløpt ({abs(days)}d siden)"
        if days <= 30:
            return f"🟠 {days} dager"
        if days <= 90:
            return f"🟡 {days} dager"
        return f"🟢 {days} dager"
    except Exception:
        return renewal_date_str


def render_policies_section(orgnr: str) -> None:
    with st.expander("📋 Forsikringsavtaler", expanded=True):
        _render_policy_list(orgnr)
    with st.expander("➕ Registrer forsikringsavtale", expanded=False):
        _render_add_policy_form(orgnr)


def _render_policy_list(orgnr: str) -> None:
    try:
        resp = requests.get(f"{API_BASE}/org/{orgnr}/policies", headers=get_auth_headers(), timeout=8)
        policies = resp.json() if resp.ok else []
    except Exception:
        policies = []

    if not policies:
        st.caption("Ingen forsikringsavtaler registrert.")
        return

    for p in policies:
        col_info, col_renewal, col_del = st.columns([4, 2, 1])
        with col_info:
            st.markdown(f"**{p['insurer']}** — {p['product_type']}")
            details = []
            if p.get("policy_number"):
                details.append(f"Avtalenr: {p['policy_number']}")
            if p.get("annual_premium_nok"):
                details.append(f"Premie: kr {p['annual_premium_nok']:,.0f}")
            if p.get("document_url"):
                details.append(f"[📄 Avtaledokument]({p['document_url']})")
            st.markdown(" · ".join(details) if details else "")
        with col_renewal:
            st.caption(_days_badge(p.get("renewal_date")))
        with col_del:
            if st.button("🗑", key=f"del_policy_{p['id']}", help="Slett avtale"):
                requests.delete(f"{API_BASE}/org/{orgnr}/policies/{p['id']}", headers=get_auth_headers(), timeout=8)
                st.rerun()


def _render_add_policy_form(orgnr: str) -> None:
    with st.form(f"add_policy_{orgnr}", clear_on_submit=True):
        col1, col2 = st.columns(2)
        insurer      = col1.text_input("Forsikringsselskap *")
        product_type = col2.selectbox("Produkttype *", _PRODUCT_TYPES)
        policy_number = col1.text_input("Avtalenummer")
        status        = col2.selectbox("Status", _STATUS_OPTIONS)
        premium = col1.number_input("Årspremie (kr)", min_value=0.0, step=1000.0)
        coverage = col2.number_input("Forsikringssum (kr)", min_value=0.0, step=100_000.0)
        start_date   = col1.date_input("Startdato", value=None)
        renewal_date = col2.date_input("Fornyelsesdato", value=None)
        notes = st.text_area("Notater", height=60)
        document_url = st.text_input("Dokument-URL (valgfritt)", placeholder="https://...")
        if st.form_submit_button("Lagre avtale") and insurer:
            payload = {
                "insurer": insurer, "product_type": product_type,
                "policy_number": policy_number or None, "status": status,
                "annual_premium_nok": premium if premium > 0 else None,
                "coverage_amount_nok": coverage if coverage > 0 else None,
                "start_date": start_date.isoformat() if start_date else None,
                "renewal_date": renewal_date.isoformat() if renewal_date else None,
                "notes": notes or None,
                "document_url": document_url or None,
            }
            r = requests.post(f"{API_BASE}/org/{orgnr}/policies", json=payload, headers=get_auth_headers(), timeout=8)
            if r.status_code == 201:
                st.success("Forsikringsavtale lagret!")
                st.rerun()
            else:
                st.error(f"Feil: {r.text}")
