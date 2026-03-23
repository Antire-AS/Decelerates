"""Admin tab — user and role management, data exports."""
import io
from datetime import date

import pandas as pd
import requests
import streamlit as st

from ui.config import API_BASE, get_auth_headers

ROLES = ["admin", "broker", "viewer"]


def _render_exports(headers: dict) -> None:
    st.markdown("#### Eksporter data")
    col_r, col_p = st.columns(2)

    with col_r:
        if st.button("Hent fornyelsesrapport (Excel)", use_container_width=True):
            try:
                resp = requests.get(
                    f"{API_BASE}/renewals", params={"days": 365},
                    headers=headers, timeout=10,
                )
                renewals = resp.json() if resp.ok else []
                if renewals:
                    df = pd.DataFrame([{
                        "Orgnr": r.get("orgnr"), "Forsikringsselskap": r.get("insurer"),
                        "Produkt": r.get("product_type"), "Premie (kr)": r.get("annual_premium_nok"),
                        "Fornyelsesdato": r.get("renewal_date"), "Dager igjen": r.get("days_to_renewal"),
                        "Status": r.get("status"),
                    } for r in renewals])
                    buf = io.BytesIO()
                    df.to_excel(buf, index=False, sheet_name="Fornyelser")
                    st.download_button(
                        "⬇️ Last ned", data=buf.getvalue(),
                        file_name=f"fornyelser_{date.today()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                else:
                    st.info("Ingen fornyelser funnet.")
            except Exception as e:
                st.error(str(e))

    with col_p:
        if st.button("Hent premievolum (Excel)", use_container_width=True):
            try:
                resp = requests.get(f"{API_BASE}/policies", headers=headers, timeout=10)
                policies = resp.json() if resp.ok else []
                if policies:
                    df = pd.DataFrame([{
                        "Orgnr": p.get("orgnr"), "Forsikringsselskap": p.get("insurer"),
                        "Produkt": p.get("product_type"), "Avtalenr": p.get("policy_number"),
                        "Premie (kr)": p.get("annual_premium_nok"),
                        "Forsikringssum (kr)": p.get("coverage_amount_nok"),
                        "Startdato": p.get("start_date"), "Fornyelsesdato": p.get("renewal_date"),
                        "Status": p.get("status"),
                    } for p in policies])
                    buf = io.BytesIO()
                    df.to_excel(buf, index=False, sheet_name="Avtaleoversikt")
                    st.download_button(
                        "⬇️ Last ned", data=buf.getvalue(),
                        file_name=f"avtaleoversikt_{date.today()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                else:
                    st.info("Ingen avtaler funnet.")
            except Exception as e:
                st.error(str(e))


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

    st.markdown("---")
    _render_exports(headers)
    st.markdown("---")
    st.markdown("#### Brukere")
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
