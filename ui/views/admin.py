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

    st.markdown("---")
    _render_crm_seed()
    st.markdown("---")
    _render_data_controls()


def _render_crm_seed() -> None:
    st.markdown("#### CRM demo-data")
    st.caption(
        "Oppretter realistiske forsikringsavtaler, skader og aktiviteter for demo-selskapene "
        "slik at Fornyelser, CRM-faner og dashboardet viser ekte data."
    )
    if st.button("Seed CRM demo-data", key="seed_crm_btn", use_container_width=True, type="primary"):
        with st.spinner("Oppretter demo CRM-data…"):
            try:
                r = requests.post(f"{API_BASE}/admin/seed-crm-demo", timeout=30)
                if r.ok:
                    d = r.json()
                    st.success(
                        f"✅ Ferdig — {d['policies_created']} avtaler, "
                        f"{d['claims_created']} skader, "
                        f"{d['activities_created']} aktiviteter opprettet."
                    )
                else:
                    st.error(f"Feil: {r.text}")
            except Exception as e:
                st.error(str(e))


def _render_data_controls() -> None:
    st.markdown("#### Datahåndtering")

    col_demo, col_reset = st.columns(2)

    with col_demo:
        st.markdown("**Last inn demo-data**")
        st.caption(
            "Oppretter 'Demo Portefølje' med 8 store norske selskaper, "
            "henter BRREG-data og starter PDF-ekstraksjon i bakgrunnen."
        )
        if st.button("▶ Last inn demo", key="admin_demo_tab", use_container_width=True, type="primary"):
            with st.spinner("Henter selskapsdata..."):
                try:
                    r = requests.post(f"{API_BASE}/admin/demo", timeout=60)
                    if r.ok:
                        d = r.json()
                        st.success(
                            f"✅ Demo klar — '{d.get('portfolio_name')}' opprettet med "
                            f"{d.get('companies')} selskaper."
                        )
                    else:
                        st.error(f"Feil: {r.text}")
                except Exception as e:
                    st.error(str(e))

    with col_reset:
        st.markdown("**Nullstill innsamlet data**")
        st.caption(
            "Sletter selskapsdata, regnskapshistorikk og porteføljer. "
            "Videoer, dokumenter og kunnskapsbasen beholdes."
        )
        if st.button("🔄 Nullstill innsamlet data", key="admin_reset_tab", use_container_width=True, type="secondary"):
            st.session_state["confirm_admin_reset_tab"] = True

    if st.session_state.get("confirm_admin_reset_tab"):
        st.warning("⚠️ Dette sletter alle selskaper, regnskapsdata og porteføljer. Er du sikker?")
        c1, c2 = st.columns(2)
        if c1.button("Ja, nullstill", key="admin_reset_confirm_tab", type="primary"):
            with st.spinner("Nullstiller..."):
                try:
                    requests.delete(f"{API_BASE}/admin/reset", timeout=30)
                except Exception:
                    pass
            st.session_state.pop("confirm_admin_reset_tab", None)
            st.rerun()
        if c2.button("Avbryt", key="admin_reset_cancel_tab"):
            st.session_state.pop("confirm_admin_reset_tab", None)
            st.rerun()

    st.markdown("---")
    st.markdown("**🇳🇴 Norges Topp 100 — full finansiell innhenting**")
    st.caption(
        "Slår opp alle ~100 største norske selskaper i BRREG, henter profiler og risikoscore, "
        "og kjører AI-agenten (Claude/Gemini) for å finne årsrapport-PDF-er fra IR-sidene. "
        "Tar 30–90 minutter totalt."
    )
    if st.button("🚀 Hent finansdata for Norges Topp 100", key="admin_top100_tab", use_container_width=True, type="primary"):
        with st.spinner("Slår opp selskaper i BRREG..."):
            try:
                r = requests.post(f"{API_BASE}/admin/seed-norway-top100", timeout=60)
                if r.ok:
                    d = r.json()
                    st.success(
                        f"✅ Startet — {d.get('pdf_agent_queued')} selskaper i kø for PDF-innhenting. "
                        f"Portefølje: '{d.get('portfolio_name')}'."
                    )
                else:
                    st.error(f"Feil: {r.text}")
            except Exception as e:
                st.error(str(e))

    st.markdown("---")
    st.markdown("**📧 Porteføljedigest — e-postvarsel**")
    st.caption(
        "Sender e-post med aktive vekstalerts på tvers av alle porteføljer "
        "til broker-kontaktadressen konfigurert i Innstillinger."
    )
    if st.button("Send porteføljedigest", key="admin_digest_tab", use_container_width=True):
        with st.spinner("Sender digest-e-post…"):
            try:
                r = requests.post(f"{API_BASE}/admin/portfolio-digest", timeout=30)
                if r.ok:
                    d = r.json()
                    st.success(
                        f"✅ Sendt til {d['recipient']} — {d['emails_sent']} e-poster "
                        f"({d['portfolios_checked']} porteføljer sjekket)."
                    )
                else:
                    st.error(f"Feil: {r.status_code} — {r.json().get('detail', r.text)}")
            except Exception as e:
                st.error(str(e))

    if st.button("Send aktivitetspåminnelser", key="admin_activity_reminders", use_container_width=True):
        with st.spinner("Sjekker forfallsdatoer og sender påminnelse…"):
            try:
                r = requests.post(f"{API_BASE}/admin/activity-reminders", timeout=30)
                if r.ok:
                    d = r.json()
                    if d.get("sent"):
                        st.success(
                            f"✅ Sendt til {d['recipient']} — "
                            f"{d['overdue']} forfalt, {d['due_today']} forfaller i dag."
                        )
                    else:
                        st.info("Ingen forfallne oppgaver i dag.")
                else:
                    st.error(f"Feil: {r.status_code} — {r.json().get('detail', r.text)}")
            except Exception as e:
                st.error(str(e))
