"""Portfolio tab: previously analysed companies overview."""
from datetime import date as _date, timedelta as _td

import requests
import streamlit as st
import pandas as pd

from ui.config import API_BASE


def render_portfolio_tab() -> None:
    st.subheader("Previously analysed companies")

    try:
        port_resp = requests.get(f"{API_BASE}/companies", params={"limit": 200}, timeout=10)
        port_resp.raise_for_status()
        companies = port_resp.json()
    except Exception as e:
        st.error(f"Failed to load portfolio: {e}")
        companies = []

    try:
        _sla_resp = requests.get(f"{API_BASE}/sla", timeout=8)
        _all_slas = _sla_resp.json() if _sla_resp.ok else []
    except Exception:
        _all_slas = []

    if not companies:
        st.info("No companies in portfolio yet. Search and view a company profile to add it here.")
        return

    df = pd.DataFrame(companies)

    _scores = df["risk_score"].dropna() if "risk_score" in df.columns else pd.Series([], dtype=float)
    _high_risk = int((_scores >= 8).sum())
    _avg_score = round(float(_scores.mean()), 1) if len(_scores) else 0
    _active_slas = sum(1 for s in _all_slas if s.get("status") == "active")

    _m1, _m2, _m3, _m4 = st.columns(4)
    _m1.metric("Selskaper", len(companies))
    _m2.metric("Gj.snitt risikoscore", _avg_score)
    _m3.metric("Høyrisikoselskaper", _high_risk)
    _m4.metric("Aktive avtaler (SLA)", _active_slas)

    # ── Renewal alerts ─────────────────────────────────────
    _renewals = []
    for _s in _all_slas:
        _sd = _s.get("start_date")
        if not _sd:
            continue
        try:
            _renewal = _date.fromisoformat(_sd[:10]) + _td(days=365)
            _days_left = (_renewal - _date.today()).days
            if 0 <= _days_left <= 90:
                _renewals.append((_s, _renewal, _days_left))
        except Exception:
            pass

    if _renewals:
        with st.expander(f"⚠️ Fornyelser innen 90 dager ({len(_renewals)} avtale(r))", expanded=True):
            for _s, _renewal, _days_left in sorted(_renewals, key=lambda x: x[2]):
                st.warning(
                    f"**{_s.get('client_navn', _s.get('client_orgnr', '?'))}** "
                    f"— fornyelse {_renewal.strftime('%d.%m.%Y')} "
                    f"({_days_left} dager)"
                )

    def _risk_badge(score):
        if score is None:
            return "–"
        if score <= 3:
            return "🟢 Lav"
        if score <= 7:
            return "🟡 Moderat"
        if score <= 11:
            return "🔴 Høy"
        return "🚨 Svært høy"

    display_cols = {
        "orgnr": "Orgnr",
        "navn": "Company",
        "organisasjonsform_kode": "Form",
        "kommune": "Municipality",
        "naeringskode1_beskrivelse": "Industry",
        "regnskapsår": "Year",
        "omsetning": "Revenue (MNOK)",
        "egenkapitalandel": "Equity ratio %",
        "risk_score": "Risk score",
    }
    df_display = df[[c for c in display_cols if c in df.columns]].copy()
    df_display.rename(columns=display_cols, inplace=True)

    if "Revenue (MNOK)" in df_display.columns:
        df_display["Revenue (MNOK)"] = (df_display["Revenue (MNOK)"] / 1_000_000).round(1)
    if "Equity ratio %" in df_display.columns:
        df_display["Equity ratio %"] = (df_display["Equity ratio %"] * 100).round(1)

    if "Risk score" in df_display.columns:
        df_display.insert(0, "Risikonivå", df["risk_score"].apply(_risk_badge))
        df_display = df_display.sort_values("Risk score", ascending=False, na_position="last")

    st.dataframe(df_display, use_container_width=True, hide_index=True)

    with st.expander("Åpne selskapsprofil"):
        _company_names = [f"{c['navn']} ({c['orgnr']})" for c in companies]
        _selected_name = st.selectbox("Velg selskap", _company_names, key="portfolio_quickload")
        if st.button("Åpne profil", key="portfolio_load_btn"):
            _idx = _company_names.index(_selected_name)
            st.session_state["selected_orgnr"] = companies[_idx]["orgnr"]
            st.session_state["show_results"] = False
            st.info("Bytt til **Selskapsøk**-fanen for å se profilen.")

    col_left, col_right = st.columns(2)

    with col_left:
        if "risk_score" in df.columns and df["risk_score"].notna().any():
            st.markdown("#### Risk score by company")
            risk_df = (
                df[df["risk_score"].notna()]
                .set_index("navn")[["risk_score"]]
                .rename(columns={"risk_score": "Risk score"})
                .sort_values("Risk score", ascending=False)
                .head(20)
            )
            st.bar_chart(risk_df)

    with col_right:
        if "omsetning" in df.columns and df["omsetning"].notna().any():
            st.markdown("#### Revenue comparison (MNOK)")
            rev_df = (
                df[df["omsetning"].notna()]
                .set_index("navn")[["omsetning"]]
                .rename(columns={"omsetning": "Revenue (MNOK)"})
            )
            rev_df["Revenue (MNOK)"] = (rev_df["Revenue (MNOK)"] / 1_000_000).round(1)
            rev_df = rev_df.sort_values("Revenue (MNOK)", ascending=False).head(20)
            st.bar_chart(rev_df)

    st.caption(f"{len(companies)} companies analysed. Data from BRREG public registry.")
