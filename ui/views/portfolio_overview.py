"""Portfolio overview — all-companies dashboard with risk distribution and industry breakdown."""
from datetime import date as _date, timedelta as _td

import pandas as pd
import streamlit as st

from ui.views.portfolio_helpers import _fetch, _risk_badge


def _render_overview(companies: list, all_slas: list) -> None:
    scores = [c["risk_score"] for c in companies if c.get("risk_score") is not None]
    high_risk = sum(1 for s in scores if s >= 8)
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    active_slas = sum(1 for s in all_slas if s.get("status") == "active")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Selskaper analysert", len(companies))
    m2.metric("Gj.snitt risikoscore", avg_score)
    m3.metric("Høyrisikoselskaper", high_risk)
    m4.metric("Aktive SLA-avtaler", active_slas)

    # Renewal alerts
    renewals = []
    for s in all_slas:
        sd = s.get("start_date")
        if not sd:
            continue
        try:
            renewal = _date.fromisoformat(sd[:10]) + _td(days=365)
            days_left = (renewal - _date.today()).days
            if 0 <= days_left <= 90:
                renewals.append((s, renewal, days_left))
        except Exception:
            pass
    if renewals:
        with st.expander(f"⚠️ Fornyelser innen 90 dager ({len(renewals)} avtale(r))", expanded=True):
            for s, renewal, days_left in sorted(renewals, key=lambda x: x[2]):
                st.warning(
                    f"**{s.get('client_navn', s.get('client_orgnr', '?'))}** "
                    f"— fornyelse {renewal.strftime('%d.%m.%Y')} ({days_left} dager)"
                )

    df = pd.DataFrame(companies)

    # ── Risk distribution breakdown ───────────────────────────────────────────
    st.markdown("---")
    tbl_col, chart_col = st.columns([3, 2])

    with tbl_col:
        st.markdown("#### Alle analyserte selskaper")
        display_cols = {
            "orgnr": "Orgnr", "navn": "Selskap", "kommune": "Kommune",
            "naeringskode1_beskrivelse": "Bransje", "regnskapsår": "År",
            "risk_score": "Risikoscore",
        }
        df_disp = df[[c for c in display_cols if c in df.columns]].copy()
        df_disp.rename(columns=display_cols, inplace=True)
        if "Risikoscore" in df_disp.columns:
            df_disp.insert(0, "Risikonivå", df["risk_score"].apply(_risk_badge))
            df_disp = df_disp.sort_values("Risikoscore", ascending=False, na_position="last")
        st.dataframe(df_disp, width="stretch", hide_index=True)

    with chart_col:
        st.markdown("#### Risikofordeling")
        buckets = {"🟢 Lav (1–3)": 0, "🟡 Moderat (4–7)": 0, "🔴 Høy (8–11)": 0, "🚨 Svært høy (12+)": 0, "Ingen data": 0}
        for s in df.get("risk_score", pd.Series(dtype=float)):
            if s is None or (isinstance(s, float) and pd.isna(s)):
                buckets["Ingen data"] += 1
            elif s <= 3:
                buckets["🟢 Lav (1–3)"] += 1
            elif s <= 7:
                buckets["🟡 Moderat (4–7)"] += 1
            elif s <= 11:
                buckets["🔴 Høy (8–11)"] += 1
            else:
                buckets["🚨 Svært høy (12+)"] += 1
        risk_df = pd.DataFrame({"Nivå": list(buckets.keys()), "Selskaper": list(buckets.values())})
        risk_df = risk_df[risk_df["Selskaper"] > 0]
        st.dataframe(risk_df, width="stretch", hide_index=True)
        st.bar_chart(risk_df.set_index("Nivå")["Selskaper"], height=180)

    # ── Industry + top risk (same row) ───────────────────────────────────────
    st.markdown("---")
    ind_col, risk_col = st.columns(2)

    with ind_col:
        if "naeringskode1_beskrivelse" in df.columns and df["naeringskode1_beskrivelse"].notna().any():
            st.markdown("#### Bransjefordeling")
            ind_counts = (
                df[df["naeringskode1_beskrivelse"].notna()]
                .groupby("naeringskode1_beskrivelse")
                .size()
                .reset_index(name="Antall")
                .rename(columns={"naeringskode1_beskrivelse": "Bransje"})
                .sort_values("Antall", ascending=False)
                .head(10)
            )
            st.dataframe(ind_counts, width="stretch", hide_index=True)

    with risk_col:
        if "risk_score" in df.columns and df["risk_score"].notna().any():
            st.markdown("#### Topp 15 — høyest risiko")
            st.bar_chart(
                df[df["risk_score"].notna()].set_index("navn")[["risk_score"]]
                .rename(columns={"risk_score": "Score"})
                .sort_values("Score", ascending=False).head(15)
            )

    # ── Revenue by industry + top revenue (same row) ──────────────────────────
    if "sum_driftsinntekter" in df.columns and df["sum_driftsinntekter"].notna().any():
        st.markdown("---")
        rev_ind_col, rev_top_col = st.columns(2)

        with rev_ind_col:
            if "naeringskode1_beskrivelse" in df.columns and df["naeringskode1_beskrivelse"].notna().any():
                st.markdown("#### Omsetning per bransje (MNOK)")
                rev_ind = (
                    df[df["sum_driftsinntekter"].notna() & df["naeringskode1_beskrivelse"].notna()]
                    .groupby("naeringskode1_beskrivelse")["sum_driftsinntekter"]
                    .sum()
                    .div(1_000_000)
                    .round(1)
                    .reset_index()
                    .rename(columns={"naeringskode1_beskrivelse": "Bransje", "sum_driftsinntekter": "MNOK"})
                    .sort_values("MNOK", ascending=False)
                    .head(10)
                )
                st.dataframe(rev_ind, width="stretch", hide_index=True)
                st.bar_chart(rev_ind.set_index("Bransje")["MNOK"], height=200)

        with rev_top_col:
            st.markdown("#### Topp 15 — størst omsetning")
            rev = df[df["sum_driftsinntekter"].notna()].copy()
            rev["MNOK"] = (rev["sum_driftsinntekter"] / 1_000_000).round(1)
            st.bar_chart(rev.set_index("navn")[["MNOK"]].sort_values("MNOK", ascending=False).head(15))
