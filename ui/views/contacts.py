"""Render contact persons section for a company profile."""
import requests
import streamlit as st

from ui.config import API_BASE, T, get_auth_headers


def render_contacts_section(orgnr: str) -> None:
    with st.expander("👤 Kontaktpersoner", expanded=False):
        _render_contact_list(orgnr)
        st.divider()
        _render_add_contact_form(orgnr)


def _render_contact_list(orgnr: str) -> None:
    try:
        resp = requests.get(f"{API_BASE}/org/{orgnr}/contacts", headers=get_auth_headers(), timeout=8)
        contacts = resp.json() if resp.ok else []
    except Exception:
        contacts = []

    if not contacts:
        st.caption("Ingen kontaktpersoner registrert.")
        return

    for c in contacts:
        col_info, col_del = st.columns([5, 1])
        with col_info:
            badge = " ⭐ Primær" if c.get("is_primary") else ""
            st.markdown(f"**{c['name']}**{badge}")
            if c.get("title"):
                st.caption(c["title"])
            details = " · ".join(filter(None, [c.get("email"), c.get("phone")]))
            if details:
                st.caption(details)
        with col_del:
            if st.button("🗑", key=f"del_contact_{c['id']}", help="Slett kontakt"):
                requests.delete(f"{API_BASE}/org/{orgnr}/contacts/{c['id']}", headers=get_auth_headers(), timeout=8)
                st.rerun()


def _render_add_contact_form(orgnr: str) -> None:
    with st.form(f"add_contact_{orgnr}", clear_on_submit=True):
        st.markdown("**Legg til kontaktperson**")
        col1, col2 = st.columns(2)
        name  = col1.text_input("Navn *")
        title = col2.text_input("Tittel")
        email = col1.text_input("E-post")
        phone = col2.text_input("Telefon")
        is_primary = st.checkbox("Sett som primærkontakt")
        notes = st.text_area("Notater", height=60)
        if st.form_submit_button("Lagre kontakt") and name:
            payload = {
                "name": name, "title": title or None, "email": email or None,
                "phone": phone or None, "is_primary": is_primary, "notes": notes or None,
            }
            r = requests.post(f"{API_BASE}/org/{orgnr}/contacts", json=payload, headers=get_auth_headers(), timeout=8)
            if r.status_code == 201:
                st.success("Kontaktperson lagret!")
                st.rerun()
            else:
                st.error(f"Feil: {r.text}")
