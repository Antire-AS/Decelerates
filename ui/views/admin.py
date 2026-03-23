"""Admin tab — user and role management."""
import requests
import streamlit as st

from ui.config import API_BASE, get_auth_headers

ROLES = ["admin", "broker", "viewer"]


def render_admin_tab() -> None:
    st.subheader("⚙️ Brukere og tilganger")

    headers = get_auth_headers()

    try:
        me_resp = requests.get(f"{API_BASE}/users/me", headers=headers, timeout=8)
        me = me_resp.json() if me_resp.ok else {}
    except Exception:
        me = {}

    if me:
        st.caption(
            f"Logget inn som: **{me.get('name', me.get('email', '?'))}** "
            f"— {me.get('email', '')}"
        )

    try:
        resp = requests.get(f"{API_BASE}/users", headers=headers, timeout=8)
        if resp.status_code == 401:
            st.warning("Du må være logget inn for å se brukere.")
            return
        users = resp.json() if resp.ok else []
    except Exception as e:
        st.error(f"Kunne ikke hente brukere: {e}")
        return

    if not users:
        st.info("Ingen brukere funnet.")
        return

    st.markdown(f"**{len(users)} brukere i firmaet**")
    st.markdown("---")

    hdr_name, hdr_email, hdr_role, hdr_action = st.columns([3, 4, 2, 1])
    hdr_name.markdown("**Navn**")
    hdr_email.markdown("**E-post**")
    hdr_role.markdown("**Rolle**")

    for u in users:
        col_name, col_email, col_role, col_save = st.columns([3, 4, 2, 1])
        col_name.write(u.get("name", "–"))
        col_email.caption(u.get("email", "–"))
        current_role = u.get("role", "broker")
        new_role = col_role.selectbox(
            "Rolle",
            ROLES,
            index=ROLES.index(current_role) if current_role in ROLES else 1,
            key=f"role_{u['id']}",
            label_visibility="collapsed",
        )
        if col_save.button("Lagre", key=f"save_{u['id']}"):
            if new_role == current_role:
                st.toast("Ingen endring.")
            else:
                try:
                    r = requests.put(
                        f"{API_BASE}/users/{u['id']}/role",
                        json={"role": new_role},
                        headers=headers,
                        timeout=8,
                    )
                    if r.ok:
                        st.toast(f"Rolle oppdatert til {new_role}.")
                        st.rerun()
                    elif r.status_code == 403:
                        st.error("Kun admin kan endre roller.")
                    else:
                        st.error(f"Feil: {r.text}")
                except Exception as e:
                    st.error(str(e))
