"""Render activity timeline / CRM feed for a company profile."""
import requests
import streamlit as st

from ui.config import API_BASE, get_auth_headers

_TYPE_ICON = {
    "call": "📞", "email": "📧", "meeting": "🤝",
    "note": "📝", "task": "✅",
}
_TYPE_LABEL = {
    "call": "Samtale", "email": "E-post", "meeting": "Møte",
    "note": "Notat", "task": "Oppgave",
}


def render_activity_feed(orgnr: str) -> None:
    with st.expander("📅 Aktiviteter og notater", expanded=False):
        _render_add_form(orgnr)
        st.divider()
        _render_timeline(orgnr)


def _render_timeline(orgnr: str) -> None:
    try:
        resp = requests.get(f"{API_BASE}/org/{orgnr}/activities", headers=get_auth_headers(), timeout=8)
        activities = resp.json() if resp.ok else []
    except Exception:
        activities = []

    if not activities:
        st.caption("Ingen aktiviteter registrert.")
        return

    for a in activities:
        icon  = _TYPE_ICON.get(a.get("activity_type", ""), "📌")
        label = _TYPE_LABEL.get(a.get("activity_type", ""), a.get("activity_type", ""))
        ts    = (a.get("created_at") or "")[:10]
        completed_badge = " ✓" if a.get("completed") else ""

        col_content, col_actions = st.columns([5, 1])
        with col_content:
            st.markdown(f"{icon} **{a['subject']}**{completed_badge}  "
                        f"<small style='color:#888'>{label} · {ts} · {a.get('created_by_email','')}</small>",
                        unsafe_allow_html=True)
            if a.get("body"):
                st.caption(a["body"])
            if a.get("due_date") and not a.get("completed"):
                st.caption(f"⏰ Frist: {a['due_date']}")
        with col_actions:
            if not a.get("completed") and a.get("activity_type") == "task":
                if st.button("✓", key=f"complete_act_{a['id']}", help="Merk som fullført"):
                    requests.put(f"{API_BASE}/org/{orgnr}/activities/{a['id']}",
                                 json={"completed": True}, headers=get_auth_headers(), timeout=8)
                    st.rerun()
            if st.button("🗑", key=f"del_act_{a['id']}", help="Slett"):
                requests.delete(f"{API_BASE}/org/{orgnr}/activities/{a['id']}", headers=get_auth_headers(), timeout=8)
                st.rerun()


def _render_add_form(orgnr: str) -> None:
    with st.form(f"add_activity_{orgnr}", clear_on_submit=True):
        col1, col2 = st.columns(2)
        atype   = col1.selectbox("Type", list(_TYPE_LABEL.keys()),
                                 format_func=lambda k: f"{_TYPE_ICON[k]} {_TYPE_LABEL[k]}")
        subject = col2.text_input("Emne *")
        body    = st.text_area("Detaljer", height=80)
        due_date = st.date_input("Frist (kun for oppgaver)", value=None)

        if st.form_submit_button("Legg til aktivitet") and subject:
            payload = {
                "activity_type": atype, "subject": subject,
                "body": body or None,
                "due_date": due_date.isoformat() if due_date else None,
            }
            r = requests.post(f"{API_BASE}/org/{orgnr}/activities", json=payload, headers=get_auth_headers(), timeout=8)
            if r.status_code == 201:
                st.success("Aktivitet lagret!")
                st.rerun()
            else:
                st.error(f"Feil: {r.text}")
